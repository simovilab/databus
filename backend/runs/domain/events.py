from enum import Enum


class RunLifecycleEvents(str, Enum):
    """
    Defines all possible events that can trigger state transitions in the run lifecycle.
    """

    # Lifecycle progression events
    RUN_REQUESTED = "run_requested"
    VALIDATE_RUN = "validate_run"
    INITIALIZE_RUN = "initialize_run"
    RUN_CONFIRMED_BY_OPERATOR = "run_confirmed_by_operator"
    RUN_TRACKING_STARTED = "run_tracking_started"
    RUN_STARTED = "run_started"
    COMPLETE_RUN = "complete_run"
    # Operational deviation events
    RUN_REJECTED = "run_rejected"
    CANCEL_RUN = "cancel_run"
    INTERRUPT_RUN = "interrupt_run"
    SHORT_TURN_RUN = "short_turn_run"
    RUN_TRACKING_LOST = "run_tracking_lost"
    RUN_TRACKING_RESTORED = "run_tracking_restored"
    RUN_TRACKING_EXPIRED = "run_tracking_expired"


"""
RUN_REQUESTED = a "POST /create-run" API call request happened (an implicit run request)
VALIDATE_RUN = apply the transition guards to check GTFS consistency
INITIALIZE_RUN = execute actions to update the system state
RUN_CONFIRMED_BY_OPERATOR = the operator (driver, dispatcher) re-confirmed the run
RUN_TRACKING_STARTED = GPS pings are detected and valid
RUN_STARTED = the run actually started (vehicle is moving along a valid path)
COMPLETE_RUN = manual or automatic request to complete a successful run (e.g. vehicle reached the end of the route or the run was completed by the operator)

RUN_REJECTED = validation or initialization failed
CANCEL_RUN = a cancellation request by the operator (driver, administrator, dispatcher) or the system before it started
INTERRUPT_RUN = a manual or automatic request to interrupt the run after it started, either by the operator or the system (possible activation of an alert!)
SHORT_TURN_RUN = a manual request to short-turn the run
RUN_TRACKING_LOST = the run tracking was lost (automatic, async)
RUN_TRACKING_RESTORED = the run tracking was restored (automatic, async)
RUN_TRACKING_EXPIRED = the run tracking expired (e.g. no telemetry for a long time) (automatic, async)
"""
