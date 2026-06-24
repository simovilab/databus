---
icon: lucide/split
description: The command vs detected-fact distinction in Databús — which lifecycle events are operator-driven, which are telemetry-inferred, and the history of the run_completed rename.
---

# Commands vs detected facts

This is the most important conceptual distinction in the Databús run lifecycle. Every lifecycle event is either a **command** — an intentional act by a human or system actor — or a **detected fact** — something the platform inferred from evidence. Getting this distinction right matters for how you reason about run state, who is responsible for it, and how you debug unexpected transitions.

## Commands

A command is an explicit, synchronous request from an operator, dispatcher, or the REST API. It arrives via HTTP and is processed immediately on the Django request thread by `RunLifecycleService`.

**Command events:**

| Event | Trigger | Actor |
|---|---|---|
| `validate_run` | `POST /api/create-run/` | System (automatic on creation) |
| `initialize_run` | `POST /api/create-run/` | System (automatic on creation) |
| `run_confirmed_by_operator` | `POST /api/runs/<run_id>/update/` with `RUN_CONFIRMED` | Operator or dispatcher |
| `cancel_run` | `POST /api/runs/<run_id>/update/` with `CANCEL_RUN` | Operator, dispatcher, or system |
| `run_interrupted` | `POST /api/runs/<run_id>/update/` with `RUN_INTERRUPTED` | Operator, dispatcher, or system |
| `run_short_turned` | `POST /api/runs/<run_id>/update/` with `RUN_SHORT_TURNED` | Dispatcher or system |

See [Interfaces → REST API](../interfaces/rest-api.md) for the full request/response shapes of these endpoints.

Commands are validated by guards synchronously. If a guard fails, the HTTP request returns an error and no state change occurs.

## Detected facts

A detected fact is an event inferred by the detection layer after observing telemetry. Detected facts are **asynchronous** — they are produced by `detect_from_telemetry` or `detect_from_scan` inside Celery tasks, not on the HTTP thread.

**Detected-fact events:**

| Event | Detector | Trigger |
|---|---|---|
| `run_tracking_started` | `RunTrackingStartedDetector` | `Confirmed` run + any valid telemetry ping |
| `run_started` | `RunStartedDetector` | `Tracking` run + `position.speed > 0.5` m/s |
| `run_tracking_restored` | `RunTrackingRestoredDetector` | `No Signal` run + any valid telemetry ping |
| `run_completed` | `RunCompletedDetector` | `In Progress` run + server-computed `STOPPED_AT` at a stop |
| `run_tracking_lost` | `RunTrackingLostDetector` | `In Progress` + staleness > 60 s (periodic scan) |
| `run_tracking_expired` | `RunTrackingExpiredDetector` | `No Signal` + staleness > 600 s (periodic scan) |

Detected facts fire via the same `run_lifecycle_event` Celery task as commands, but with `actor_role = "system"` in the payload.

## The `run_completed` rename (commit `54e23f3`)

The event was previously named `complete_run` — a verb phrase that reads like a command. It was renamed to `run_completed` — a past-tense fact phrase — because completion is **detected**, not commanded.

The old name implied that an operator explicitly tells the system "the run is done." The current design detects completion automatically: `RunCompletedDetector` fires `run_completed` when the server-computed `vehicle_stop_status` reports `current_status == "STOPPED_AT"` at a stop, and the `is_at_terminal_stop` guard then confirms that stop is the terminal stop of the trip.

!!! note "Manual completion still uses the same event"
    If an operator manually marks a run as completed via the REST API, the same `run_completed` event is fired — but this time sourced from the HTTP thread rather than from the detection layer. The event is a fact in both cases; the mechanism of discovery differs.

## Why this matters

The distinction shapes where you look when debugging:

- A run that never reached `Tracking` despite the vehicle moving: check the **command** path — did `RUN_CONFIRMED_BY_OPERATOR` arrive? Did the REST API call succeed?
- A run stuck in `Tracking` despite pings arriving: check the **detection** path — is `RunStartedDetector` firing? Is speed being parsed correctly from the MQTT payload?
- A run stuck in `In Progress` past the terminal stop: check `RunCompletedDetector` — is the server-computed `vehicle_stop_status` actually reporting `STOPPED_AT`? Is `is_at_terminal_stop` passing?

## The `run_completed` detection path after progression moved server-side (commit `ae36cc8`)

An earlier version computed `vehicle_stop_status` at the edge and sent it as a `progression` MQTT leaf. When progression moved server-side (the edge now only sends `position` and `occupancy`), `RunCompletedDetector` stopped firing because the `progression` leaf was no longer arriving from MQTT.

Commit `ae36cc8` restored detection by re-feeding the server-computed `vehicle_stop_status` back into `detect_from_telemetry` with `leaf="progression"` inside the `process_position_update` Celery task. The full flow is:

```text
MQTT position ping
    → HSET vehicle:<id>:position
    → process_position_update.delay(run_id, vehicle_id)
        → produce_stop_status()           # server-side map-matching
        → detect_from_telemetry(run_id, vehicle_id, "progression", computed_stop_status)
            → RunCompletedDetector.detect() if state == "In Progress" and STOPPED_AT
                → run_lifecycle_event.delay("run_completed", {..., "stop_id": ...})
                    → RunLifecycleService.process_event()
                        → is_at_terminal_stop guard
                        → transition to Completed
```

See [detection.md](detection.md) for the detection layer internals and [../data-flow/server-processing.md](../data-flow/server-processing.md) for the full `process_position_update` flow.
