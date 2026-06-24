---
icon: lucide/scan-search
description: The Databús detection layer — pure planners, impure wrappers, detector registry, telemetry and periodic detectors, and the tracking-seed mechanism.
---

# Detection layer

The detection layer converts raw telemetry signals and staleness observations into lifecycle FSM events. It sits between the MQTT consumer and the `run_lifecycle_event` Celery task.

All detection code lives in `backend/runs/domain/detection/`.

## Design: pure planners and impure wrappers

The detection layer is split into two tiers, defined in `dispatch.py`:

```text
Pure planners (no I/O, unit-testable)
    plan_telemetry_events(lifecycle_state, leaf, data, base_payload)
    plan_scan_events(lifecycle_state, staleness_s, payload)

Impure wrappers (read Redis, enqueue Celery tasks)
    detect_from_telemetry(run_id, vehicle_id, leaf, data)
    detect_from_scan(run_id, staleness_s, raw_last_seen)
```

The planners take the run's current lifecycle state and a message and return a list of `DetectionResult` objects. They perform no I/O and hold no references to Redis or Celery — they can be unit-tested with a plain function call.

The wrappers are called by the MQTT consumer and the stale-scan task respectively. They read the current lifecycle state from Redis (`hget run:<id> run_lifecycle_state`), build the base payload, call the pure planner, and then fire each result as a `run_lifecycle_event` Celery task.

## Detector registry

Defined in `backend/runs/domain/detection/registry.py`. Two ordered lists:

```python
TELEMETRY_DETECTORS = [
    RunTrackingStartedDetector(),
    RunStartedDetector(),
    RunTrackingRestoredDetector(),
    RunCompletedDetector(),
]

PERIODIC_DETECTORS = [
    RunTrackingLostDetector(),
    RunTrackingExpiredDetector(),
]
```

**At most one event per FSM per evaluation.** `plan_telemetry_events` tracks which FSMs have already fired (`fired_fsms: set[str]`) and skips any detector whose FSM has already produced a result. Since all current detectors share `fsm = "lifecycle"`, at most one lifecycle event fires per telemetry message.

Order matters within a single FSM: the first matching detector wins. The ordering `[TrackingStarted, Started, TrackingRestored, Completed]` means that if a `Confirmed` run receives its first ping (matching `RunTrackingStartedDetector`), the `RunStartedDetector` never gets to run for that message.

Adding a new detector is a one-line change to the registry list.

## Telemetry detectors (`lifecycle_detectors.py`)

### RunTrackingStartedDetector

**Condition:** `run_state == "Confirmed"`, any leaf.

**Fires:** `run_tracking_started`

The arrival of any valid telemetry from a confirmed run is sufficient to start tracking. No leaf-specific check needed.

### RunStartedDetector

**Condition:** `run_state == "Tracking"` AND `leaf == "position"` AND `speed > 0.5` m/s.

**Fires:** `run_started`

Only position pings carry speed. The 0.5 m/s threshold matches `MIN_MOVING_SPEED` and the `is_vehicle_moving` guard.

### RunTrackingRestoredDetector

**Condition:** `run_state == "No Signal"`, any leaf.

**Fires:** `run_tracking_restored`

Symmetrical to `RunTrackingStartedDetector`. Any fresh ping from a no-signal run means contact is restored.

### RunCompletedDetector

**Condition:** `run_state == "In Progress"` AND `leaf == "progression"` AND `current_status == "STOPPED_AT"` AND `stop_id` is present.

**Fires:** `run_completed` with `extra_payload = {"stop_id": stop_id}`

Note that the `leaf == "progression"` check does not mean the edge sends a `progression` MQTT topic. The `process_position_update` task feeds the server-computed `vehicle_stop_status` dict back into `detect_from_telemetry` with `leaf="progression"` explicitly. The actual MQTT consumer does not subscribe to a progression topic.

The terminal-stop check is **not** done here. It is deferred to the `is_at_terminal_stop` guard in the lifecycle FSM. This means `run_completed` fires whenever the vehicle is stopped at any stop — the guard rejects it if that stop is not the terminal stop. This separation keeps detectors simple and guards authoritative.

## Periodic detectors (`periodic_detectors.py`)

### RunTrackingLostDetector

**Condition:** `run_state == "In Progress"` AND `TELEMETRY_GRACE_S < staleness_s <= TELEMETRY_EXPIRY_S`

That is: staleness is between 60 s and 600 s.

**Fires:** `run_tracking_lost` with `actor_role = "system"`

### RunTrackingExpiredDetector

**Condition:** `run_state == "No Signal"` AND `staleness_s > TELEMETRY_EXPIRY_S`

That is: staleness exceeds 600 s.

**Fires:** `run_tracking_expired` with `actor_role = "system"`

## Staleness thresholds

Defined in `backend/runs/domain/detection/thresholds.py` — the single source of truth imported by both detectors and guards:

```python
TELEMETRY_GRACE_S = 60    # IN_PROGRESS + silent > 60 s  → NO_SIGNAL
TELEMETRY_EXPIRY_S = 600  # NO_SIGNAL + silent > 600 s   → CANCELLED
```

!!! note "Why a single thresholds module?"
    Previously the thresholds lived in two places that disagreed: `realtime_engine/tasks.py` used 300 s and `guards.py` used 600 s, so the periodic scan could fire `run_tracking_expired` in a window where the FSM guard would then reject it. Both now import from `thresholds.py`.

## The tracking seed

`detect_from_telemetry` has a special case for `run_tracking_started` and `run_tracking_restored`. The FSM guard `is_vehicle_tracked` checks `SISMEMBER runs:tracking <run_id>`, but the very arrival of telemetry is what justifies that membership. The dispatcher seeds the set before firing these events:

```python
_TRACKING_SEED_EVENTS = {"run_tracking_started", "run_tracking_restored"}

def _fire(result: DetectionResult, base_payload: dict) -> None:
    if result.event in _TRACKING_SEED_EVENTS:
        r.sadd("runs:tracking", base_payload["run_id"])
    run_lifecycle_event.delay(result.event, payload)
```

This mirrors the original inline behavior while keeping detectors pure.

## DetectionResult

```python
@dataclass(frozen=True)
class DetectionResult:
    fsm: str             # "lifecycle" — routing key for the target FSM
    event: str           # RunLifecycleEvents member value
    extra_payload: dict  # merged into base_payload before firing
```

## Lifecycle event trigger table

From `backend/realtime_engine/README.md`:

| Run state | Trigger condition | Event fired |
|---|---|---|
| `Confirmed` | Any valid ping received | `run_tracking_started` |
| `Tracking` | `position.speed > 0.5` m/s | `run_started` |
| `No Signal` | Any valid ping received | `run_tracking_restored` |
| `In Progress` | server-computed `STOPPED_AT` with `stop_id` | `run_completed` |
| `In Progress` | staleness > 60 s (periodic scan) | `run_tracking_lost` |
| `No Signal` | staleness > 600 s (periodic scan) | `run_tracking_expired` |

See [commands-vs-detections.md](commands-vs-detections.md) for the full commands/detections split, and [stale-runs.md](stale-runs.md) for the `scan_stale_runs` periodic task that drives the last two entries.
