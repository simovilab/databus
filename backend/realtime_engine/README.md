# realtime_engine

Celery worker (queue `realtime_engine`) that ingests vehicle telemetry (MQTT
push + HTTP poll), runs detection/progression on it, and drives the run
lifecycle FSM. It is the **sole writer of the real-time Redis state**
(`vehicle:*`, `run:*`, `runs:*`) — `schedule_engine` only ever reads it.

## MQTT consumer: Celery bootstep approach

The MQTT consumer (`mqtt.py`) runs inside the realtime-engine worker as a
Celery `bootsteps.StartStopStep`. It starts when the worker boots and shuts
down when the worker shuts down. paho's `loop_start()` runs the network loop
in its own background thread, so it does not block Celery task execution.

The bootstep is registered globally in `databus/celery.py` but gated by the
`MQTT_CONSUMER_ENABLED` env var. Only the `realtime-engine` compose service
sets it to `true`; other workers (schedule-engine, beat) skip the bootstep so
the broker doesn't see duplicate subscribers.

**Why a bootstep instead of a separate service?**
The dedicated `realtime-consumer` service was an early choice that traded
operational simplicity for separation-of-concerns at a scale the demo doesn't
need. paho's network loop already runs in its own thread, so colocating it
with the Celery worker doesn't starve task execution. The bootstep avoids an
extra container, Dockerfile target, and bind-mount on the backend tree.

## Topic subscriptions

```
transit/vehicle/+/position    QoS 0
transit/vehicle/+/occupancy   QoS 0
```

`progression` is intentionally **not** subscribed — it's decommissioned
server-side (the simulator may still publish it, but the consumer ignores
any leaf it doesn't recognize). Server-side stop status is computed instead
by `runs.domain.progression.producer.produce_stop_status` (real GPS→polyline
map-matching), triggered from `process_position_update` after every position
write. The `data` leaf (static vehicle metadata) is not subscribed here
either — it's written to Redis by `RunLifecycleActions.update_system_state`
when a run is initialized.

## Ingestion pipeline (`mqtt.py`)

For each incoming message on `position` or `occupancy`, `_handle_telemetry`:

1. Drops the message if the vehicle has no `vehicle:<id>:current_run` key
   (no active run assigned).
2. `position`: validates and writes `vehicle:<id>:position`, then enqueues
   `realtime_engine.tasks.process_position_update` — heavy work (map-matching,
   ETA projection, detection) runs off the MQTT network thread.
3. `occupancy`: discards any edge-sent `occupancy_status` and recomputes it
   server-side from the raw percentage (`occupancy.classify_status`), then
   writes `vehicle:<id>:occupancy`.
4. Updates `runs:last_seen:<run_id>` synchronously (never delayed by queue
   latency) so staleness detection stays accurate even under a slow worker.
5. For `occupancy` only, runs `detect_from_telemetry` inline (cheap; and
   `RunTrackingStartedDetector`/`RunTrackingRestoredDetector` match any
   leaf, so occupancy pings must still be able to drive those transitions).
   `position`-leaf detection happens asynchronously inside
   `process_position_update` instead.

### `process_position_update(run_id, vehicle_id)` (queue `realtime_engine`)

Re-reads the latest `vehicle:<id>:position` from Redis (idempotent,
last-write-wins; no retries — a retried tick is stale, the next ping
recovers). In order:

1. `produce_stop_status` — server-side map-matching, writes
   `run:<id>:vehicle_stop_status`.
2. If a stop status was computed, re-feeds it into
   `detect_from_telemetry(run_id, vehicle_id, "progression", ...)` —
   this is what fires `RunCompletedDetector` now that raw `progression`
   telemetry is no longer consumed.
3. `produce_stop_times` — ETA stop-time-updates projection, writes
   `run:<id>:stop_time_updates`.
4. `detect_from_telemetry(run_id, vehicle_id, "position", ...)` — position-leaf
   detection (`RunStartedDetector`, `RunTrackingStartedDetector`, etc.).

Each step is wrapped independently in `try/except`, logged, and never
propagated — one failing step doesn't block the others.

## `run_lifecycle_event` task (queue `realtime_engine`)

Dispatches a fired event to `RunLifecycleService.process_event`. A
`RunLifecycleError` is treated two ways:

- If the run has **already reached the event's target state**
  (`target_state_for_event`) — a benign idempotent re-fire (a detector's
  dispatch lost a race against an in-flight transition for the same run) —
  logged as a `WARNING`, not an error.
- Otherwise — a genuine invalid transition — logged with `logger.exception`.

## `fetch_positions` task (queue `realtime_engine`, `soft_time_limit=25`)

Polls active HTTP telemetry sources every **10 s** (Celery Beat,
`options={"expires": 10}` — a task that couldn't even start within its own
10 s cycle is revoked rather than queuing up behind a slow source):

1. Builds the in-service vehicle-id set from every `vehicle:<id>:current_run`
   key — the same gate the MQTT consumer uses, so poller and consumer agree
   on which vehicles count. (Gating on `runs:in_progress` instead would
   deadlock a `CONFIRMED` run, since it only reaches `IN_PROGRESS` once
   telemetry proves it's moving — delivering that telemetry is this task's
   job.)
2. Queries `ACTIVE` sensors with `provides_position=True` and
   `source_type` in `("http", "both")`.
3. Pre-fetch filters out any sensor whose own `equipment.vehicle` isn't in
   the in-service set, to avoid paying the HTTP cost of every active sensor
   on every tick. (Caveat: a fleet endpoint like NavSat can return readings
   for vehicles other than the sensor's own — those are only caught by the
   post-fetch filter, so an out-of-service sensor's fleet endpoint is
   skipped entirely rather than partially used.)
4. Fetches each remaining sensor independently (own try/except; one failing
   source can't sink the rest), keeps only in-service vehicles' readings
   (post-fetch filter), and publishes survivors on
   `transit/vehicle/<id>/position` via `MqttPublisher`.

`soft_time_limit=25` bounds a single pathological source (e.g. a host that
hangs on every request): on `SoftTimeLimitExceeded` the task logs and
returns early instead of propagating.

## `scan_stale_runs` task (queue `realtime_engine`)

Runs every **30 s** via Celery Beat. Computes each tracked run's staleness
and hands it to `runs.domain.detection.dispatch.detect_from_scan`, which
evaluates the periodic detectors in `runs.domain.detection.periodic_detectors`
against the shared thresholds in `runs.domain.detection.thresholds`:

- `IN_PROGRESS` + `60 s < staleness ≤ 600 s` → `run_tracking_lost`
- `NO_SIGNAL` + `staleness > 600 s` → `run_tracking_expired`

(`TELEMETRY_GRACE_S = 60`, `TELEMETRY_EXPIRY_S = 600` —
`runs/domain/detection/thresholds.py`. These were previously duplicated and
disagreeing — 300 s here vs. 600 s in the lifecycle guards — both now import
the same constants.)

## `sources/` — pluggable HTTP telemetry adapter registry

`sources/base.py` defines the `SourceAdapter` protocol
(`fetch(sensor) -> list[(vehicle_id, payload)]`) and a tiny
`register(kind)` / `get_adapter(kind)` registry, kept dependency-free
(no Django, no requests, no paho) so adapters are unit-testable without I/O.
`sources/http_json.py` registers the generic `"http"` adapter — driven
entirely by a `Sensor`'s `source_http_url` + `source_json_mapping` fields, no
per-provider code needed for JSON-over-HTTP feeds that fit the mapping
schema. HTTP requests use a **5 s timeout**
(`DEFAULT_TIMEOUT_S`). `sources/publisher.py`'s `MqttPublisher` republishes
fetched readings onto the same `transit/vehicle/<id>/position` topic the
MQTT consumer subscribes to.

## Environment variables

| Var                     | Default            | Purpose                                                       |
| ----------------------- | ------------------ | ------------------------------------------------------------- |
| `MQTT_CONSUMER_ENABLED` | `false`            | Master switch; set `true` only on the realtime-engine worker. |
| `MQTT_HOST`             | `telemetry-broker` | Broker hostname (resolved inside compose).                    |
| `MQTT_PORT`             | `1883`             | Broker port.                                                  |
| `REDIS_HOST`            | `state`            | Redis hostname.                                               |
| `REDIS_PORT`            | `6379`             | Redis port.                                                   |
