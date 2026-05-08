from dataclasses import dataclass
from typing import Callable, List

from .actions import RunLifecycleActions
from .guards import RunLifecycleGuards
from .states import RunLifecycleStates
from .events import RunLifecycleEvents


@dataclass
class Transition:
    """
    Represents a state transition in the run lifecycle.
    """

    from_state: RunLifecycleStates
    event: RunLifecycleEvents
    to_state: RunLifecycleStates
    guards: List[Callable]
    actions: List[Callable]


TRANSITIONS = [
    Transition(
        from_state=RunLifecycleStates.REQUESTED,
        event=RunLifecycleEvents.RUN_REQUESTED,
        to_state=RunLifecycleStates.VALIDATED,
        guards=[
            RunLifecycleGuards.is_gtfs_valid,
            RunLifecycleGuards.is_trip_available,
            RunLifecycleGuards.is_vehicle_available,
            RunLifecycleGuards.is_operator_available,
        ],
        actions=[RunLifecycleActions.update_run_lifecycle_state],
    ),
    Transition(
        from_state=RunLifecycleStates.VALIDATED,
        event=RunLifecycleEvents.RUN_VALIDATED,
        to_state=RunLifecycleStates.INITIALIZED,
        guards=[
            RunLifecycleGuards.is_system_state_updated,
        ],
        actions=[
            RunLifecycleActions.update_system_state,
            RunLifecycleActions.update_run_lifecycle_state,
        ],
    ),
]
