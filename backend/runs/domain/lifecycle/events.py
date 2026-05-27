from enum import Enum


class RunLifecycleEvents(str, Enum):
    """
    Defines all possible events that can trigger state transitions in the run lifecycle.
    """

    # Lifecycle progression events
    RUN_REQUESTED = "run_requested"  # initial: record creation puts run in REQUESTED
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
