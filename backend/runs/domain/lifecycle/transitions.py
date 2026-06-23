from dataclasses import dataclass
from typing import Callable, List

from .actions import RunLifecycleActions
from .guards import RunLifecycleGuards
from .states import RunLifecycleStates
from .events import RunLifecycleEvents


@dataclass
class Transition:
    """Represents a state transition in the run lifecycle."""

    from_state: RunLifecycleStates
    event: RunLifecycleEvents
    to_state: RunLifecycleStates
    guards: List[Callable]
    actions: List[Callable]


TRANSITIONS = [
    # ------------------------------------------------------------------
    # Registration: REQUESTED → VALIDATED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.REQUESTED,
        event=RunLifecycleEvents.VALIDATE_RUN,
        to_state=RunLifecycleStates.VALIDATED,
        guards=[
            RunLifecycleGuards.is_gtfs_valid,
            RunLifecycleGuards.is_trip_available,
            RunLifecycleGuards.is_vehicle_available,
            RunLifecycleGuards.is_operator_available,
        ],
        actions=[],
    ),
    # Registration rejected at validation stage
    Transition(
        from_state=RunLifecycleStates.REQUESTED,
        event=RunLifecycleEvents.RUN_REJECTED,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[],
        actions=[],
    ),
    # ------------------------------------------------------------------
    # Initialization: VALIDATED → INITIALIZED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.VALIDATED,
        event=RunLifecycleEvents.INITIALIZE_RUN,
        to_state=RunLifecycleStates.INITIALIZED,
        guards=[
            RunLifecycleGuards.is_run_validated,
        ],
        actions=[
            RunLifecycleActions.update_system_state,
        ],
    ),
    # Initialization failed after validation passed
    Transition(
        from_state=RunLifecycleStates.VALIDATED,
        event=RunLifecycleEvents.RUN_REJECTED,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[],
        actions=[
            RunLifecycleActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Operator confirmation: INITIALIZED → CONFIRMED
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.INITIALIZED,
        event=RunLifecycleEvents.RUN_CONFIRMED_BY_OPERATOR,
        to_state=RunLifecycleStates.CONFIRMED,
        guards=[],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
        ],
    ),
    # Cancelled before operator confirmation
    Transition(
        from_state=RunLifecycleStates.INITIALIZED,
        event=RunLifecycleEvents.RUN_REJECTED,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[
            RunLifecycleGuards.is_cancellation_authorized,
        ],
        actions=[
            RunLifecycleActions.remove_from_system_state,
            RunLifecycleActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Tracking started: CONFIRMED → TRACKING
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.CONFIRMED,
        event=RunLifecycleEvents.RUN_TRACKING_STARTED,
        to_state=RunLifecycleStates.TRACKING,
        guards=[
            RunLifecycleGuards.is_vehicle_tracked,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.add_to_tracking_set,
        ],
    ),
    # Cancelled after confirmation but before tracking
    Transition(
        from_state=RunLifecycleStates.CONFIRMED,
        event=RunLifecycleEvents.CANCEL_RUN,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[
            RunLifecycleGuards.is_cancellation_authorized,
        ],
        actions=[
            RunLifecycleActions.remove_from_system_state,
            RunLifecycleActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # Run started: TRACKING → IN_PROGRESS
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.TRACKING,
        event=RunLifecycleEvents.RUN_STARTED,
        to_state=RunLifecycleStates.IN_PROGRESS,
        guards=[
            RunLifecycleGuards.is_vehicle_moving,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.add_to_in_progress_set,
        ],
    ),
    # Cancelled while tracking (before run started)
    Transition(
        from_state=RunLifecycleStates.TRACKING,
        event=RunLifecycleEvents.CANCEL_RUN,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[
            RunLifecycleGuards.is_cancellation_authorized,
        ],
        actions=[
            RunLifecycleActions.remove_from_tracking_set,
            RunLifecycleActions.remove_from_system_state,
            RunLifecycleActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # In progress: deviation events
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.IN_PROGRESS,
        event=RunLifecycleEvents.RUN_TRACKING_LOST,
        to_state=RunLifecycleStates.NO_SIGNAL,
        guards=[
            RunLifecycleGuards.is_telemetry_stale,
        ],
        actions=[
            # Keep the run in `runs:tracking` so scan_stale_runs can fire
            # RUN_TRACKING_EXPIRED later. The set is the work queue, not a
            # status flag — only fully-terminal transitions should remove from it.
            RunLifecycleActions.sync_lifecycle_state,
        ],
    ),
    Transition(
        from_state=RunLifecycleStates.IN_PROGRESS,
        event=RunLifecycleEvents.RUN_INTERRUPTED,
        to_state=RunLifecycleStates.INTERRUPTED,
        guards=[
            RunLifecycleGuards.is_interruption_authorized,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.remove_from_tracking_set,
            RunLifecycleActions.remove_from_in_progress_set,
            RunLifecycleActions.release_resources,
        ],
    ),
    Transition(
        from_state=RunLifecycleStates.IN_PROGRESS,
        event=RunLifecycleEvents.RUN_SHORT_TURNED,
        to_state=RunLifecycleStates.SHORT_TURNED,
        guards=[
            RunLifecycleGuards.is_short_turn_authorized,
            RunLifecycleGuards.is_short_turn_geometrically_valid,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.remove_from_tracking_set,
            RunLifecycleActions.remove_from_in_progress_set,
            RunLifecycleActions.release_resources,
        ],
    ),
    Transition(
        from_state=RunLifecycleStates.IN_PROGRESS,
        event=RunLifecycleEvents.RUN_COMPLETED,
        to_state=RunLifecycleStates.COMPLETED,
        guards=[
            RunLifecycleGuards.is_at_terminal_stop,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.remove_from_tracking_set,
            RunLifecycleActions.remove_from_in_progress_set,
            RunLifecycleActions.release_resources,
        ],
    ),
    # ------------------------------------------------------------------
    # No signal: recovery or expiry
    # ------------------------------------------------------------------
    Transition(
        from_state=RunLifecycleStates.NO_SIGNAL,
        event=RunLifecycleEvents.RUN_TRACKING_RESTORED,
        to_state=RunLifecycleStates.IN_PROGRESS,
        guards=[
            RunLifecycleGuards.is_telemetry_fresh,
            RunLifecycleGuards.is_vehicle_tracked,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.add_to_tracking_set,
            RunLifecycleActions.add_to_in_progress_set,
        ],
    ),
    Transition(
        from_state=RunLifecycleStates.NO_SIGNAL,
        event=RunLifecycleEvents.RUN_TRACKING_EXPIRED,
        to_state=RunLifecycleStates.CANCELLED,
        guards=[
            RunLifecycleGuards.is_telemetry_grace_period_exceeded,
        ],
        actions=[
            RunLifecycleActions.sync_lifecycle_state,
            RunLifecycleActions.remove_from_tracking_set,
            RunLifecycleActions.remove_from_in_progress_set,
            RunLifecycleActions.release_resources,
        ],
    ),
]
