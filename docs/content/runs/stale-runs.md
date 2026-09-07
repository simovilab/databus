---
icon: lucide/clock
---

# Stale-run scanning

The `scan_stale_runs` task is the periodic watchdog that detects when a tracked run has gone silent and drives it through the `IN_PROGRESS` → `No Signal` → `Cancelled` path automatically.

## What it does

Every 30 seconds (fired by Celery Beat), `scan_stale_runs` in `backend/realtime_engine/tasks.py`:

1. Reads all members of the `runs:tracking` Redis set.
2. For each run, reads `runs:last_seen:<run_id>` (ISO-8601 timestamp of last telemetry).
3. Computes `staleness = now() - last_seen` in seconds.
4. Calls `detect_from_scan(run_id, staleness, raw_last_seen)` from the detection layer.

```python
@shared_task(queue="realtime_engine")
def scan_stale_runs() -> str:
    from runs.domain.detection.dispatch import detect_from_scan

    run_ids = redis_client.smembers("runs:tracking")
    fired = 0
    for run_id in run_ids:
        raw_last_seen = redis_client.get(f"runs:last_seen:{run_id}")
        if not raw_last_seen:
            continue
        ...
        staleness = (now() - last_seen).total_seconds()
        fired += detect_from_scan(run_id, staleness, raw_last_seen)

    return f"scan_stale_runs: checked {len(run_ids)} runs, fired {fired} events"
```

The task returns a summary string that appears in Flower and Celery logs.

## Staleness thresholds

Defined in `backend/runs/domain/detection/thresholds.py`:

```python
TELEMETRY_GRACE_S = 60    # seconds
TELEMETRY_EXPIRY_S = 600  # seconds
```

| Condition | Event fired | Resulting state |
|---|---|---|
| `IN_PROGRESS` AND `60 < staleness <= 600` | `run_tracking_lost` | `No Signal` |
| `NO_SIGNAL` AND `staleness > 600` | `run_tracking_expired` | `Cancelled` |

The two-stage design gives the vehicle a grace window (60 s) to reconnect before the run enters `No Signal`, and then a longer window (up to 600 s total from last seen) before it is permanently cancelled.

## Why `runs:tracking` includes NO_SIGNAL runs

A run that transitions to `No Signal` stays in `runs:tracking`. The comment in `transitions.py` explains:

> Keep the run in `runs:tracking` so scan_stale_runs can fire `RUN_TRACKING_EXPIRED` later. The set is the work queue, not a status flag — only fully-terminal transitions should remove from it.

If a `No Signal` run were removed from `runs:tracking`, the scan would never see it again and could not fire `run_tracking_expired`. The terminal transitions (Completed, Interrupted, Short Turned, Cancelled) remove the run from the set via `remove_from_tracking_set`.

## Recovery: `RUN_TRACKING_RESTORED`

If a vehicle resumes sending telemetry while its run is in `No Signal`, the MQTT consumer path (via `process_position_update` → `detect_from_telemetry` → `RunTrackingRestoredDetector`) fires `run_tracking_restored`, which transitions the run back to `In Progress`. This happens on the Celery `realtime_engine` queue, not via the periodic scan.

## `runs:last_seen:<id>` key

The MQTT consumer updates this key on every incoming message:

```
runs:last_seen:<run_id>  →  Redis string, ISO-8601 timestamp
```

The scan reads it to compute staleness. If the key is missing (e.g. the run was registered but never received telemetry), `scan_stale_runs` skips that run with a `continue`.

## Beat schedule

`scan_stale_runs` is scheduled in `backend/databus/celery.py`:

```python
"scan-stale-runs-every-30s": {
    "task": "realtime_engine.tasks.scan_stale_runs",
    "schedule": timedelta(seconds=30),
},
```

It runs on the `realtime_engine` queue and is therefore processed by the `realtime-engine` Celery worker.

## Operational notes

**Under normal conditions:** most runs spend no time in `No Signal`. The 30-second scan period means detection of actual signal loss is delayed by up to 30 s beyond the 60-second grace window.

**Long silence gaps:** if a vehicle is in a tunnel or loses mobile coverage, `No Signal` provides a holding state that preserves the run record and Redis state. Recovery is automatic on the next ping.

**Expiry at 600 s:** a run that has been in `No Signal` for 10 minutes without any telemetry is considered abandoned and is cancelled with `actor_role = "system"`. This fires `run_tracking_expired` via `RunTrackingExpiredDetector`, which the FSM guard `is_telemetry_grace_period_exceeded` validates before executing the `Cancelled` transition.

For the run-state cleanup script (manual intervention), see [../operations/troubleshooting.md](../operations/troubleshooting.md).
