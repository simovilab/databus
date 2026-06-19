---
icon: lucide/key
---

# Redis State Keys

Canonical reference for every Redis key used by Databús. No other module
should hardcode these key strings — they are all defined in
`backend/runs/domain/telemetry/keys.py` and imported from there.

!!! tip "Namespace rule"
    `vehicle:<id>:*` — written by the edge (MQTT consumer).
    `run:<id>:*` and `runs:*` — written by the server (lifecycle actions, progression step).

---

## Vehicle-keyed keys (`vehicle:<id>:*`)

These keys hold data that originated from the vehicle's on-board equipment and
arrived via MQTT. The realtime-engine writes them; the schedule-engine reads
them.

### `vehicle:<vehicle_id>:position`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.position_key(vehicle_id)` |
| Writer | MQTT consumer (`realtime_engine/mqtt.py`) |
| Reader | `schedule_engine/tasks.py::build_vehicle_positions`, `build_trip_updates` |
| TTL | None (lives until run cleanup) |

**Fields:**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `latitude` | float | Yes | WGS-84 decimal degrees |
| `longitude` | float | Yes | WGS-84 decimal degrees |
| `bearing` | float | No | Degrees clockwise from north |
| `speed` | float | No | Metres per second |
| `odometer` | float | No | Metres |
| `timestamp` | int | No | Unix epoch seconds; lifted to VP-level by the feed builder |

---

### `vehicle:<vehicle_id>:occupancy`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.occupancy_key(vehicle_id)` |
| Writer | MQTT consumer (`realtime_engine/mqtt.py`) |
| Reader | `schedule_engine/tasks.py::build_vehicle_positions` |
| TTL | None |

**Fields:**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `occupancy_status` | str (enum) | Yes | Server-bucketed; edge value discarded (see below) |
| `occupancy_percentage` | int | No | Raw percentage from edge |
| `occupancy_count` | int | No | Raw passenger count from edge |

!!! warning "Server policy: `occupancy_status` is recomputed"
    The edge device may send an `occupancy_status` value, but the MQTT
    consumer discards it and recomputes it server-side using
    `occupancy.classify_status(occupancy_percentage)`. Only the percentage is
    trusted from the edge; the enum assignment is a server policy decision.

    Thresholds (`backend/runs/domain/telemetry/occupancy.py`):

    | Percentage | `occupancy_status` |
    | --- | --- |
    | `None` | `NO_DATA_AVAILABLE` |
    | `< 20` | `MANY_SEATS_AVAILABLE` |
    | `< 50` | `FEW_SEATS_AVAILABLE` |
    | `< 80` | `STANDING_ROOM_ONLY` |
    | `>= 80` | `FULL` |

    The remaining GTFS values (`EMPTY`, `CRUSHED_STANDING_ROOM_ONLY`,
    `NOT_ACCEPTING_PASSENGERS`, `NOT_BOARDABLE`) require product input before
    threshold ranges can be assigned.

---

### `vehicle:<vehicle_id>:metadata`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.metadata_key(vehicle_id)` |
| Writer | Lifecycle action (`runs/domain/lifecycle/actions.py`) on run start |
| Reader | `schedule_engine/tasks.py::build_vehicle_positions`, `build_trip_updates` |
| TTL | None |

**Fields:**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | str | Yes | Vehicle identifier |
| `label` | str | Yes | Human-readable label |
| `license_plate` | str | No | |
| `wheelchair_accessible` | str | No | GTFS wheelchair_accessible enum |

---

### `vehicle:<vehicle_id>:current_run`

| Attribute | Value |
| --- | --- |
| Redis type | String |
| Function | `keys.current_run_key(vehicle_id)` |
| Writer | Lifecycle action on run start |
| Reader | MQTT consumer (to route incoming telemetry to the correct run) |
| TTL | None (cleared by run cleanup) |

Holds the `run_id` (UUID string) of the run currently assigned to this
vehicle. The MQTT consumer reads this on every incoming message to determine
which run-keyed keys to update.

---

## Run-keyed keys (`run:<id>:*`)

These keys hold data that the server computes and maintains. They are the
canonical source for GTFS-RT feed building.

### `run:<run_id>`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.run_key(run_id)` |
| Writer | Lifecycle action |
| Reader | Feed builders, detection layer |
| TTL | None (explicit cleanup on run end) |

**Fields (non-exhaustive):**

| Field | Notes |
| --- | --- |
| `trip_id` | GTFS trip_id |
| `route_id` | GTFS route_id |
| `direction_id` | GTFS direction_id |
| `shape_id` | GTFS shape_id (used for map-matching geometry) |
| `schedule_relationship` | GTFS schedule_relationship enum |
| `start_time` | HH:MM:SS |
| `start_date` | YYYYMMDD |
| `vehicle` | vehicle_id |
| `operator` | operator_id |
| `run_lifecycle_state` | Current FSM state (see [lifecycle states](../runs/lifecycle-states.md)) |

The `run:<id>:trip` hash is the GTFS-RT-shaped projection of the trip subset
of this hash.

---

### `run:<run_id>:trip`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.trip_key(run_id)` |
| Writer | Lifecycle action |
| Reader | Feed builders |
| TTL | None |

**Fields:**

| Field | Type | Required |
| --- | --- | --- |
| `trip_id` | str | Yes |
| `route_id` | str | Yes |
| `direction_id` | int | No |
| `schedule_relationship` | str | No |
| `start_time` | str (HH:MM:SS) | No |
| `start_date` | str (YYYYMMDD) | No |

This is a GTFS-RT TripDescriptor projection. The feed builder defaults
`schedule_relationship` to `SCHEDULED` when the field is absent.

---

### `run:<run_id>:vehicle_stop_status`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.stop_status_key(run_id)` |
| Writer | Server progression step (`runs/domain/progression/compute.py`) |
| Reader | Feed builders, `RunCompletedDetector` |
| TTL | None |

**Fields:**

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `current_status` | str (enum) | Yes | `INCOMING_AT`, `STOPPED_AT`, `IN_TRANSIT_TO` |
| `current_stop_sequence` | int | No | GTFS stop_sequence |
| `stop_id` | str | No | GTFS stop_id |

Run completion is detected when `current_status == STOPPED_AT` at a terminal
stop. See [Run lifecycle › Detection layer](../runs/detection.md).

---

### `run:<run_id>:congestion_level`

| Attribute | Value |
| --- | --- |
| Redis type | Hash |
| Function | `keys.congestion_key(run_id)` |
| Writer | Deferred — no producer yet; key reserved |
| Reader | Feed builders (tolerant: skipped when absent) |
| TTL | None |

**Fields:**

| Field | Type | Notes |
| --- | --- | --- |
| `congestion_level` | str (enum) | `UNKNOWN_CONGESTION_LEVEL`, `RUNNING_SMOOTHLY`, `STOP_AND_GO`, `CONGESTION`, `SEVERE_CONGESTION` |

!!! note "Deferred"
    A single bus's speed is a weak signal for congestion. An honest estimate
    requires fleet aggregation or a traffic feed. The key is reserved and the
    contract defined in `runs/domain/telemetry/congestion_level.py`, but no
    producer writes it yet. Feed builders read it tolerantly — absent hash
    means no `congestion_level` field in the GTFS-RT entity.

---

### `run:<run_id>:stop_time_updates`

| Attribute | Value |
| --- | --- |
| Redis type | **String** (JSON-encoded array) |
| Function | `keys.stop_time_updates_key(run_id)` |
| Writer | Stop-times producer (`runs/domain/progression/stop_times.py`) |
| Reader | `schedule_engine/builders.py::build_trip_update_entity` |
| TTL | Staleness TTL (set by producer; absent key = skip stop_time_update in feed) |

!!! warning "Not a hash"
    This key is a Redis **string** holding a JSON-encoded array. Do not
    use `HGETALL` on it — use `GET`. The other `run:<id>:*` keys are hashes;
    this one is the exception.

**Per-entry schema:**

```json
{
    "stop_sequence": 42,
    "stop_id": "STOP_ID",
    "arrival_time": 1718800000,
    "departure_time": 1718800000,
    "uncertainty": 60
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `stop_sequence` | int | GTFS stop_sequence |
| `stop_id` | str | GTFS stop_id |
| `arrival_time` | int | POSIX seconds |
| `departure_time` | int | POSIX seconds (equals arrival_time currently) |
| `uncertainty` | int | Seconds of uncertainty |

The feed builder treats a missing or empty value as "no stop_time_update
entries in this TripUpdate entity."

---

## Tracking and set keys (`runs:*`)

### `runs:last_seen:<run_id>`

| Attribute | Value |
| --- | --- |
| Redis type | String |
| Function | `keys.last_seen_key(run_id)` |
| Writer | MQTT consumer — written synchronously on every message |
| Reader | `scan_stale_runs` task |
| TTL | None |

Holds an ISO-8601 timestamp of the last telemetry received for this run.
Written synchronously (not via the Celery task queue) so staleness detection
is never delayed by queue latency.

Used by `scan_stale_runs` to trigger `run_tracking_lost` (> 60 s staleness
while `IN_PROGRESS`) and `run_tracking_expired` (> 300 s while `NO_SIGNAL`).

---

### `runs:tracking`

| Attribute | Value |
| --- | --- |
| Redis type | Set |
| Writer | Lifecycle action |
| Reader | `scan_stale_runs`, `RunTrackingStartedDetector` |
| TTL | None |

Set of `run_id` values for runs that have started receiving telemetry
(i.e., have reached `Tracking` state or beyond). Used as the scan target for
stale-run detection.

---

### `runs:in_progress`

| Attribute | Value |
| --- | --- |
| Redis type | Set |
| Writer | Lifecycle action |
| Reader | Feed builders (`build_vehicle_positions_feed`, `build_trip_updates_feed`) |
| TTL | None |

Set of `run_id` values for runs currently in `In Progress` state. The feed
builders iterate this set to determine which runs to include in the GTFS-RT
output.

---

## Decommissioned keys

The following keys appear in older documentation and must not be used:

| Old key | Replaced by |
| --- | --- |
| `vehicle:<id>:progression` | `run:<id>:vehicle_stop_status` (stop fields) + `run:<id>:congestion_level` |
| `vehicle:<id>:data` | `vehicle:<id>:metadata` |
| `run:{id}` (curly brace form) | `run:<id>` (angle bracket form) |

See `AGENTS.md §State Management` for the historical list (now superseded by
this page).
