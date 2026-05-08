from enum import Enum


class RunLifecycleEvents(str, Enum):
    """
    Defines all possible events that can trigger state transitions in the run lifecycle.
    """

    # Lifecycle progression events
    RUN_REQUESTED = "run_requested"
    RUN_VALIDATED = "run_validated"
    RUN_INITIALIZED = "run_initialized"
    RUN_CONFIRMED_BY_OPERATOR = "run_confirmed_by_operator"
    RUN_TRACKING_STARTED = "run_tracking_started"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    # Operational deviation events
    RUN_REJECTED = "run_rejected"
    RUN_CANCELLED = "run_cancelled"
    RUN_INTERRUPTED = "run_interrupted"
    RUN_SHORT_TURNED = "run_short_turned"
    RUN_TRACKING_LOST = "run_tracking_lost"
    RUN_TRACKING_RESTORED = "run_tracking_restored"
    RUN_TRACKING_EXPIRED = "run_tracking_expired"


"""
RUN_REQUESTED = a POST /runs request happened (an implicit run request)
RUN_VALIDATED = all GTFS checks passed
RUN_INITIALIZED = system state was updated
RUN_CONFIRMED_BY_OPERATOR = the operator (driver, dispatcher) re-confirmed the run
RUN_TRACKING_STARTED = GPS pings are detected and valid
RUN_STARTED = the run actually started (vehicle is moving along a valid path)
RUN_COMPLETED = the vehicle arrived at the final stop

RUN_REJECTED = validation or initialization failed
RUN_CANCELLED = the run was cancelled by the operator or the system before it started
RUN_INTERRUPTED = the run was interrupted after it started, either by the operator or the system
RUN_SHORT_TURNED = the run was short-turned
RUN_TRACKING_LOST = the run tracking was lost
RUN_TRACKING_RESTORED = the run tracking was restored
RUN_TRACKING_EXPIRED = the run tracking expired (e.g. no telemetry for a long time)
"""
