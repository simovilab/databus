# Run

## Run lifecycle states

- `RUN_REQUESTED` = a "POST /create-run" API call request happened (an implicit run request)
- `VALIDATE_RUN` = apply the transition guards to check GTFS consistency
- `INITIALIZE_RUN` = execute actions to update the system state
- `RUN_CONFIRMED_BY_OPERATOR` = the operator (driver, dispatcher) re-confirmed the run
- `RUN_TRACKING_STARTED` = GPS pings are detected and valid
- `RUN_STARTED` = the run actually started (vehicle is moving along a valid path)
- `RUN_COMPLETED` = manual or automatic request to complete a successful run (e.g. vehicle reached the end of the route or the run was completed by the operator)

- `RUN_REJECTED` = validation or initialization failed
- `CANCEL_RUN` = a cancellation request by the operator (driver, administrator, dispatcher) or the system before it started
- `RUN_INTERRUPTED` = a manual or automatic request to interrupt the run after it started, either by the operator or the system (possible activation of an alert!)
- `RUN_SHORT_TURNED` = a manual request to short-turn the run
- `RUN_TRACKING_LOST` = the run tracking was lost (automatic, async)
- `RUN_TRACKING_RESTORED` = the run tracking was restored (automatic, async)
- `RUN_TRACKING_EXPIRED` = the run tracking expired (e.g. no telemetry for a long time) (automatic, async)
