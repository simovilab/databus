from dataclasses import dataclass
from typing import Callable, List

from .actions import RunProgressActions
from .guards import RunProgressGuards
from .states import RunProgressStates
from .events import RunProgressEvents


@dataclass
class Transition:
    """Represents a state transition in the progress FSM."""

    from_state: RunProgressStates
    event: RunProgressEvents
    to_state: RunProgressStates
    guards: List[Callable]
    actions: List[Callable]


# Standard per-stop cycle:
#   IN_TRANSIT_TO → INCOMING_AT → STOPPED_AT → IN_TRANSIT_TO (next stop)
# plus the common shortcuts vehicles report (arriving without an INCOMING_AT
# ping, or passing a stop they were incoming to without stopping).
#
# There are no from==to transitions: repeated identical statuses are absorbed by
# the detector (it only emits on a status *change*), so the FSM never needs to
# self-loop. Every transition is gated on the run being IN_PROGRESS.
_GUARDS = [RunProgressGuards.is_run_in_progress]
_ACTIONS = [
    RunProgressActions.sync_progress_state,
    RunProgressActions.persist_progress_event,
]


def _t(from_state, event, to_state) -> Transition:
    return Transition(
        from_state=from_state,
        event=event,
        to_state=to_state,
        guards=list(_GUARDS),
        actions=list(_ACTIONS),
    )


TRANSITIONS = [
    # Approaching / arriving at the current stop
    _t(RunProgressStates.IN_TRANSIT_TO, RunProgressEvents.VEHICLE_INCOMING, RunProgressStates.INCOMING_AT),
    _t(RunProgressStates.IN_TRANSIT_TO, RunProgressEvents.VEHICLE_STOPPED, RunProgressStates.STOPPED_AT),
    _t(RunProgressStates.INCOMING_AT, RunProgressEvents.VEHICLE_STOPPED, RunProgressStates.STOPPED_AT),
    # Departing toward the next stop
    _t(RunProgressStates.STOPPED_AT, RunProgressEvents.VEHICLE_IN_TRANSIT, RunProgressStates.IN_TRANSIT_TO),
    # Passed a stop it was incoming to without registering a stop
    _t(RunProgressStates.INCOMING_AT, RunProgressEvents.VEHICLE_IN_TRANSIT, RunProgressStates.IN_TRANSIT_TO),
    # Re-approaching after a stop (rare; e.g. layover re-report)
    _t(RunProgressStates.STOPPED_AT, RunProgressEvents.VEHICLE_INCOMING, RunProgressStates.INCOMING_AT),
]
