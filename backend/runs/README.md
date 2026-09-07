# Run

`runs` owns the run lifecycle FSM, the detectors that drive it from telemetry,
map-matching/ETA progression, and the Redis telemetry contracts shared with
`realtime_engine` and `schedule_engine`.

## Run lifecycle states

`runs/domain/lifecycle/states.py` (`RunLifecycleStates`):

`Requested`, `Validated`, `Initialized`, `Confirmed`, `Tracking`,
`In Progress`, `No Signal`, `Completed`, `Cancelled`, `Interrupted`,
`Short Turned`.

## Run lifecycle events

`runs/domain/lifecycle/events.py` (`RunLifecycleEvents`) — REST commands and
telemetry-detected facts that drive transitions between the states above:

- `RUN_REQUESTED` = a "POST /create-run" API call request happened (an implicit run request)
- `VALIDATE_RUN` = apply the transition guards checking GTFS validity (route/trip/shape/schedule_relationship against the current feed) and resource availability (vehicle/trip/operator not already claimed by another run)
- `INITIALIZE_RUN` = execute actions to update the system state, gated by `is_run_validated` — a real revalidation guard that re-checks resource availability and re-confirms the run's trip against whichever GTFS feed is current *now* (closes the race window against a nightly `build_schedule` feed rotation between VALIDATE_RUN and INITIALIZE_RUN)
- `RUN_CONFIRMED_BY_OPERATOR` = the operator (driver, dispatcher) re-confirmed the run
- `RUN_TRACKING_STARTED` = GPS pings are detected and valid
- `RUN_STARTED` = the run actually started (vehicle is moving along a valid path; guard `is_vehicle_moving` checks reported speed > 0.5 m/s)
- `RUN_COMPLETED` = manual or automatic request to complete a successful run (e.g. vehicle reached the end of the route or the run was completed by the operator); guard `is_at_terminal_stop` checks the reported `stop_id` against the trip's last `stop_time`

- `RUN_REJECTED` = validation or initialization failed
- `CANCEL_RUN` = a cancellation request by the operator (driver, administrator, dispatcher) or the system before it started
- `RUN_INTERRUPTED` = a manual or automatic request to interrupt the run after it started, either by the operator or the system (possible activation of an alert!)
- `RUN_SHORT_TURNED` = a manual request to short-turn the run
- `RUN_TRACKING_LOST` = the run tracking was lost (automatic, async)
- `RUN_TRACKING_RESTORED` = the run tracking was restored (automatic, async)
- `RUN_TRACKING_EXPIRED` = the run tracking expired (e.g. no telemetry for a long time) (automatic, async)

## `domain/lifecycle` — the table-driven FSM

- `states.py` / `events.py` — the enums above.
- `transitions.py` — the static `TRANSITIONS` table: each entry is a
  `(from_state, event) -> (to_state, guards, actions)` `Transition`. Also
  exposes `target_state_for_event`, used by
  `realtime_engine.tasks.run_lifecycle_event` to tell an idempotent re-fire
  (a detection that lost a race and the run already reached the target
  state) apart from a genuine invalid transition.
- `guards.py` — `RunLifecycleGuards`, pure-ish predicate functions
  `(run, transition, payload) -> bool` that either return a verdict or raise
  `RunLifecycleError` with field-level detail. Includes GTFS validity
  (`is_gtfs_valid`), resource-claim checks (`is_vehicle_available`,
  `is_trip_available`, `is_operator_available`), the `is_run_validated`
  revalidation guard, authorization checks for cancel/interrupt/short-turn,
  and telemetry-freshness guards (`is_telemetry_stale`, `is_telemetry_fresh`,
  `is_telemetry_grace_period_exceeded`) built on the shared thresholds in
  `runs.domain.detection.thresholds`.
- `actions.py` — `RunLifecycleActions`, the Redis side-effects a successful
  transition performs: writing/clearing the `run:<id>` hash and its
  `run:<id>:trip` GTFS-RT projection, claiming/releasing
  `vehicle|operator|trip:<id>:current_run` assignment keys, and maintaining
  the `runs:tracking` / `runs:in_progress` sets.
- Submodules are lazy-loaded via `__getattr__` in `__init__.py` so importing
  `runs.domain.lifecycle` doesn't eagerly pull in the Redis/Django-touching
  `actions`/`guards` modules.

## `domain/detection` — telemetry/staleness → lifecycle events

Detectors are pure functions of state + one signal; a dispatch layer wires
them to Redis and the Celery lifecycle task.

- `lifecycle_detectors.py` — evaluated per incoming telemetry message:
  `RunTrackingStartedDetector` (any telemetry while `Confirmed`),
  `RunStartedDetector` (`Tracking` + `position.speed > 0.5` m/s),
  `RunTrackingRestoredDetector` (any telemetry while `No Signal`),
  `RunCompletedDetector` (`In Progress` + `progression` leaf reporting
  `STOPPED_AT` with a `stop_id`).
- `periodic_detectors.py` — evaluated by the periodic staleness scan:
  `RunTrackingLostDetector` (`In Progress`, `60 s < staleness ≤ 600 s`),
  `RunTrackingExpiredDetector` (`No Signal`, `staleness > 600 s`). Thresholds
  come from the single source `thresholds.py`
  (`TELEMETRY_GRACE_S = 60`, `TELEMETRY_EXPIRY_S = 600`) — previously these
  lived duplicated in `realtime_engine/tasks.py` (300 s) and
  `runs/domain/lifecycle/guards.py` (600 s) and disagreed; both now import
  from here.
- `registry.py` — ordered `TELEMETRY_DETECTORS` / `PERIODIC_DETECTORS` lists;
  the planner fires at most one event per FSM per evaluation (first match).
- `dispatch.py` — pure planners (`plan_telemetry_events`, `plan_scan_events`,
  unit-testable, no I/O) plus impure wrappers (`detect_from_telemetry`,
  `detect_from_scan`) that read run state from Redis, seed `runs:tracking`
  membership for `run_tracking_started`/`run_tracking_restored`, and queue
  the fired event onto `realtime_engine.tasks.run_lifecycle_event`.
  `realtime_engine/mqtt.py` and `scan_stale_runs` call only the wrappers.

## `domain/progression` — map-matching + ETA

- `compute.py` / `producer.py` — server-side stop-status: `produce_stop_status`
  (called from `realtime_engine.tasks.process_position_update` after every
  position write) reads the latest position + run hash, delegates to
  `compute_stop_status` for real GPS→polyline map-matching (projects onto the
  cached shape geometry, picks the upcoming stop, applies `STOPPED_AT` /
  `INCOMING_AT` / `IN_TRANSIT_TO` radius rules with a monotonic
  stop-sequence floor), and writes `run:<id>:vehicle_stop_status`. Falls back
  to `IN_TRANSIT_TO` + carry-forward of the previous state on any exception
  (missing shape, ORM error, bad payload) — this producer must never raise.
- `stop_times.py` — `produce_stop_times` derives and writes
  `run:<id>:stop_time_updates` (TTL 60 s). Calls the ETA estimator through a
  **lazy import seam** — `gtfs_eta.eta_service.estimator` and
  `gtfs_eta.feature_engineering.spatial` are imported inside the function,
  not at module scope, so Django/Celery startup stays clean even when the
  editable `gtfs-eta` path dependency isn't fully set up. No predictions
  (e.g. no trained model) leaves the last-good projection to expire via TTL
  rather than overwriting it.
- `geo.py` / `shapes.py` — pure geometry helpers (`haversine_m`,
  `project_point_to_polyline`) and cached GTFS shape-geometry loading.

## `domain/telemetry` — Redis key parsers/writers

`keys.py` is the single source of truth for every Redis key template used
across `runs`, `realtime_engine`, and `schedule_engine` — no other module
should hardcode these strings. Each entity module (`position.py`,
`occupancy.py`, `vehicle_stop_status.py`, `stop_time_updates.py`, `trip.py`,
`congestion_level.py`) defines the field-name constants, a `from_redis` /
`validate_for_write` (or `to_redis`) pair, and documents its producer and
consumer. `congestion_level.py` is a stub — the key is reserved, no producer
exists yet.

## `services/lifecycle.py` — driving the FSM

`RunLifecycleService.process_event(event, payload)`:

1. Loads the `Run` named by `payload["run_id"]`.
2. Looks up candidate transitions via `services/registry.py`'s
   `TransitionRegistry.find(state, event)`.
3. Runs each candidate's guards; on the first fully-passing candidate,
   executes its actions, updates `Run.run_lifecycle_state`/`last_event_at`,
   and publishes the transition as a domain event via `messages.publisher`
   to the durable `databus.events` topic exchange (routing key
   `runs.lifecycle.<event>`) — fire-and-forget; broker errors are logged and
   swallowed, never raised into the lifecycle path.
4. Persists an immutable `RunLifecycleTransition` audit record (guards +
   actions results) for every attempt, successful or not.
5. Raises `RunLifecycleError` (with the full attempt history) if no
   candidate transition succeeds.

Called from `realtime_engine.tasks.run_lifecycle_event`, which treats a
`RunLifecycleError` where the run already reached the event's target state
as a benign idempotent re-fire (logged as a warning), not a failure.
