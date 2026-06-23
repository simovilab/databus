from dataclasses import dataclass
from typing import Callable, List

from .actions import RunProgressActions
from .guards import RunProgressGuards
from .states import RunProgressStates
from .events import RunProgressEvents


@dataclass
class Transition:
    """Represents a state transition in the run lifecycle."""

    from_state: RunProgressStates
    event: RunProgressEvents
    to_state: RunProgressStates
    guards: List[Callable]
    actions: List[Callable]


TRANSITIONS = [
    # ------------------------------------------------------------------
    # Registration: REQUESTED → VALIDATED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.REQUESTED,
        event=RunProgressEvents.VALIDATE_RUN,
        to_state=RunProgressStates.VALIDATED,
        guards=[
            RunProgressGuards.is_gtfs_valid,
            RunProgressGuards.is_trip_available,
            RunProgressGuards.is_vehicle_available,
            RunProgressGuards.is_operator_available,
        ],
        actions=[],
    ),
    # Registration rejected at validation stage
    Transition(
        from_state=RunProgressStates.REQUESTED,
        event=RunProgressEvents.RUN_REJECTED,
        to_state=RunProgressStates.CANCELLED,
        guards=[],
        actions=[],
    ),
    # ------------------------------------------------------------------
    # Initialization: VALIDATED → INITIALIZED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.VALIDATED,
        event=RunProgressEvents.INITIALIZE_RUN,
        to_state=RunProgressStates.INITIALIZED,
        guards=[
            RunProgressGuards.is_run_validated,
        ],
        actions=[
            RunProgressActions.update_system_state,
        ],
    ),
    # Initialization failed after validation passed
    Transition(
        from_state=RunProgressStates.VALIDATED,
        event=RunProgressEvents.RUN_REJECTED,
        to_state=RunProgressStates.CANCELLED,
        guards=[],
        actions=[
            RunProgressActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Operator confirmation: INITIALIZED → CONFIRMED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.INITIALIZED,
        event=RunProgressEvents.RUN_CONFIRMED_BY_OPERATOR,
        to_state=RunProgressStates.CONFIRMED,
        guards=[],
        actions=[
            RunProgressActions.sync_lifecycle_state,
        ],
    ),
    # Cancelled before operator confirmation
    Transition(
        from_state=RunProgressStates.INITIALIZED,
        event=RunProgressEvents.RUN_REJECTED,
        to_state=RunProgressStates.CANCELLED,
        guards=[
            RunProgressGuards.is_cancellation_authorized,
        ],
        actions=[
            RunProgressActions.remove_from_system_state,
            RunProgressActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Tracking started: CONFIRMED → TRACKING
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.CONFIRMED,
        event=RunProgressEvents.RUN_TRACKING_STARTED,
        to_state=RunProgressStates.TRACKING,
        guards=[
            RunProgressGuards.is_vehicle_tracked,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.add_to_tracking_set,
        ],
    ),
    # Cancelled after confirmation but before tracking
    Transition(
        from_state=RunProgressStates.CONFIRMED,
        event=RunProgressEvents.CANCEL_RUN,
        to_state=RunProgressStates.CANCELLED,
        guards=[
            RunProgressGuards.is_cancellation_authorized,
        ],
        actions=[
            RunProgressActions.remove_from_system_state,
            RunProgressActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Run started: TRACKING → IN_PROGRESS
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.TRACKING,
        event=RunProgressEvents.RUN_STARTED,
        to_state=RunProgressStates.IN_PROGRESS,
        guards=[
            RunProgressGuards.is_vehicle_moving,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.add_to_in_progress_set,
        ],
    ),
    # Cancelled while tracking (before run started)
    Transition(
        from_state=RunProgressStates.TRACKING,
        event=RunProgressEvents.CANCEL_RUN,
        to_state=RunProgressStates.CANCELLED,
        guards=[
            RunProgressGuards.is_cancellation_authorized,
        ],
        actions=[
            RunProgressActions.remove_from_tracking_set,
            RunProgressActions.remove_from_system_state,
            RunProgressActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # In progress: deviation events
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.IN_PROGRESS,
        event=RunProgressEvents.RUN_TRACKING_LOST,
        to_state=RunProgressStates.NO_SIGNAL,
        guards=[
            RunProgressGuards.is_telemetry_stale,
        ],
        actions=[
            # Keep the run in `runs:tracking` so scan_stale_runs can fire
            # RUN_TRACKING_EXPIRED later. The set is the work queue, not a
            # status flag — only fully-terminal transitions should remove from it.
            RunProgressActions.sync_lifecycle_state,
        ],
    ),
    Transition(
        from_state=RunProgressStates.IN_PROGRESS,
        event=RunProgressEvents.RUN_INTERRUPTED,
        to_state=RunProgressStates.INTERRUPTED,
        guards=[
            RunProgressGuards.is_interruption_authorized,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.remove_from_tracking_set,
            RunProgressActions.remove_from_in_progress_set,
            RunProgressActions.release_resources,
        ],
    ),
    Transition(
        from_state=RunProgressStates.IN_PROGRESS,
        event=RunProgressEvents.RUN_SHORT_TURNED,
        to_state=RunProgressStates.SHORT_TURNED,
        guards=[
            RunProgressGuards.is_short_turn_authorized,
            RunProgressGuards.is_short_turn_geometrically_valid,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.remove_from_tracking_set,
            RunProgressActions.remove_from_in_progress_set,
            RunProgressActions.release_resources,
        ],
    ),
    Transition(
        from_state=RunProgressStates.IN_PROGRESS,
        event=RunProgressEvents.RUN_COMPLETED,
        to_state=RunProgressStates.COMPLETED,
        guards=[
            RunProgressGuards.is_at_terminal_stop,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.remove_from_tracking_set,
            RunProgressActions.remove_from_in_progress_set,
            RunProgressActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # No signal: recovery or expiry
    # ------------------------------------------------------------------
    Transition(
        from_state=RunProgressStates.NO_SIGNAL,
        event=RunProgressEvents.RUN_TRACKING_RESTORED,
        to_state=RunProgressStates.IN_PROGRESS,
        guards=[
            RunProgressGuards.is_telemetry_fresh,
            RunProgressGuards.is_vehicle_tracked,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.add_to_tracking_set,
            RunProgressActions.add_to_in_progress_set,
        ],
    ),
    Transition(
        from_state=RunProgressStates.NO_SIGNAL,
        event=RunProgressEvents.RUN_TRACKING_EXPIRED,
        to_state=RunProgressStates.CANCELLED,
        guards=[
            RunProgressGuards.is_telemetry_grace_period_exceeded,
        ],
        actions=[
            RunProgressActions.sync_lifecycle_state,
            RunProgressActions.remove_from_tracking_set,
            RunProgressActions.remove_from_in_progress_set,
            RunProgressActions.release_resources,
        ],
    ),
]
