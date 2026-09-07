---
icon: lucide/database
---

# State & persistence

Databús maintains two stores with different roles and lifetimes. Understanding which store is authoritative for what question is essential for debugging and for reasoning about race conditions.

## The two-store model

```
┌──────────────────────────────────────────────────────────────────┐
│  Redis (state)                                                   │
│  Authoritative real-time picture                                 │
│  Single writer: realtime-engine + orchestrator lifecycle actions │
│  Reader: schedule-engine (snapshots for GTFS-RT)                 │
└──────────────────────────────────────────────────────────────────┘
        │ on terminal transition: release_resources
        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PostgreSQL (database)                                           │
│  Durable domain history                                          │
│  Writer: orchestrator (domain), realtime-engine (traces)         │
│  Reader: orchestrator, analytics-engine (batch)                  │
└──────────────────────────────────────────────────────────────────┘
```

## Redis — authoritative real-time state

**Principle:** for any question about the current operational status of a run or vehicle, Redis is the answer. The PostgreSQL run row reflects the same state (written by FSM actions), but Redis is what the GTFS-RT builder and the detection layer actually read in the hot path.

**Single-writer rule:** the `realtime-engine` Celery worker is the sole writer of vehicle telemetry keys. Lifecycle FSM actions (in `backend/runs/domain/lifecycle/actions.py`), which run inside `run_lifecycle_event` tasks on the `realtime-engine`, are the sole writer of `run:<id>:*` keys and set membership keys. The `orchestrator` HTTP process does not write Redis directly in the current implementation — it triggers lifecycle events which are processed by the worker.

### Key namespaces

Two namespaces, two owners:

```
vehicle:<id>:*      — edge-sensed data (MQTT → realtime-engine)
run:<id>:*          — server-computed data (realtime-engine → FSM actions)
runs:*              — index sets and timestamps (realtime-engine)
```

#### Vehicle-keyed keys (edge-sensed)

| Key | Type | Fields | Writer |
|---|---|---|---|
| `vehicle:<id>:position` | Hash | `latitude`, `longitude`, `bearing?`, `speed?`, `odometer?`, `timestamp?` | MQTT consumer |
| `vehicle:<id>:occupancy` | Hash | `occupancy_percentage?`, `occupancy_count?`, `occupancy_status` | MQTT consumer |
| `vehicle:<id>:metadata` | Hash | `id`, `label`, `license_plate?`, `wheelchair_accessible?` | `update_system_state` action |
| `vehicle:<id>:current_run` | String | run_id | `update_system_state` action |

#### Run-keyed keys (server-computed)

| Key | Type | Fields | Writer |
|---|---|---|---|
| `run:<id>` | Hash | `run_id`, `route_id`, `trip_id`, `direction_id`, `shape_id`, `schedule_relationship`, `start_date`, `start_time`, `vehicle`, `operator`, `run_lifecycle_state` | `update_system_state` + `sync_lifecycle_state` actions |
| `run:<id>:trip` | Hash | `trip_id`, `route_id`, `direction_id?`, `schedule_relationship?`, `start_time?`, `start_date?` | `update_system_state` action |
| `run:<id>:vehicle_stop_status` | Hash | `current_status`, `current_stop_sequence?`, `stop_id?` | `produce_stop_status` (progression producer) |
| `run:<id>:congestion_level` | Hash | `congestion_level` | Producer TBD |
| `run:<id>:stop_time_updates` | String (JSON) | JSON array of stop-time-update entries | `produce_stop_times` (60 s staleness TTL) |

#### Index and timestamp keys

| Key | Type | Purpose | Writer |
|---|---|---|---|
| `runs:tracking` | Set | Scan work queue for `scan_stale_runs`, not a state flag (see note below) | `add_to_tracking_set` / `remove_from_tracking_set` actions |
| `runs:in_progress` | Set | Run IDs in `In Progress` **or** `No Signal` state (see note below) | `add_to_in_progress_set` / `remove_from_in_progress_set` actions |
| `runs:last_seen:<id>` | String | ISO-8601 timestamp of last telemetry | MQTT consumer |

!!! note "`runs:tracking` and `runs:in_progress` both outlive `run_tracking_lost`"
    The `IN_PROGRESS → NO_SIGNAL` transition (`run_tracking_lost`, `backend/runs/domain/lifecycle/transitions.py`) only runs `sync_lifecycle_state` — it does **not** call `remove_from_tracking_set` or `remove_from_in_progress_set`. A `No Signal` run therefore stays in both sets until it reaches a fully-terminal outcome: `run_tracking_expired` (→ Cancelled), `run_interrupted`, `run_short_turned`, or `run_completed`, all of which do remove it from both. This is deliberate — the code comment on the transition calls `runs:tracking` "the work queue, not a status flag": staying in the set is what lets `scan_stale_runs` later fire `run_tracking_expired` for that same run. One consequence: the GTFS-RT feed builders, which iterate `runs:in_progress`, will still emit an entity for a `No Signal` run (using its last-written Redis snapshot) until it is removed by one of the terminal transitions above.

!!! note "stop_time_updates is a string, not a hash"
    `run:<id>:stop_time_updates` is a Redis **string** key holding a JSON-encoded array, not a hash. It is written with a staleness TTL so a stalled producer lets it expire cleanly rather than serving stale arrival estimates. The GTFS-RT builder treats a missing or empty value as "skip stop_time_update entries."

See [../data-model/redis-keys.md](../data-model/redis-keys.md) for the full reference derived from `backend/runs/domain/telemetry/keys.py`.

## PostgreSQL — durable domain storage

PostgreSQL is the long-lived record of everything that happened. It is not used as a real-time coordination mechanism.

**Persisted by the orchestrator:**

- Run records with lifecycle state column (mirrors Redis `run_lifecycle_state`).
- GTFS schedule data (Agency, Route, Trip, StopTime, Shape, Calendar) via the `feed` app.
- Vehicle and operator records via the `operations` app.

**Persisted by the realtime-engine:**

- Operational traces (lifecycle event history).

**Persisted by the schedule-engine:**

- GTFS-RT blobs, retained approximately one year.

**Consumed by:**

- `orchestrator` — all domain reads (run lookup, GTFS validation in guards).
- `analytics-engine` — batch processing only, no real-time dependency.

## Authoritative answer per question

| Question | Authoritative source |
|---|---|
| What state is run X in right now? | Redis `run:<id>` → `run_lifecycle_state` |
| Where is vehicle V right now? | Redis `vehicle:<id>:position` |
| Is run X being tracked? | Redis `runs:tracking` (SISMEMBER) |
| How long has run X been quiet? | `now() - parse(runs:last_seen:<id>)` |
| What is the GTFS-RT feed content? | `backend/feed/files/*.pb` (rebuilt from Redis every 15 s) |
| What happened to run X historically? | PostgreSQL via `orchestrator` ORM |
| Which trip is assigned to run X? | Redis `run:<id>:trip` (GTFS-RT-shaped projection) |
