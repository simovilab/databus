"""Pure unit tests for the progress FSM definition (no Django/Redis)."""

import pytest

from runs.domain.progress.states import RunProgressStates
from runs.domain.progress.events import RunProgressEvents
from runs.domain.progress import transitions as progress_transitions


def test_progress_has_exactly_three_gtfsrt_states():
    values = {s.value for s in RunProgressStates}
    assert values == {"IN_TRANSIT_TO", "INCOMING_AT", "STOPPED_AT"}


def test_progress_events_are_one_per_status_no_lifecycle_leftovers():
    values = {e.value for e in RunProgressEvents}
    assert values == {"vehicle_in_transit", "vehicle_incoming", "vehicle_stopped"}
    # The old copied lifecycle events must be gone.
    for name in ("RUN_REQUESTED", "VALIDATE_RUN", "RUN_STARTED", "COMPLETE_RUN"):
        assert not hasattr(RunProgressEvents, name)


@pytest.mark.parametrize(
    "from_state,event,to_state",
    [
        (RunProgressStates.IN_TRANSIT_TO, RunProgressEvents.VEHICLE_INCOMING, RunProgressStates.INCOMING_AT),
        (RunProgressStates.IN_TRANSIT_TO, RunProgressEvents.VEHICLE_STOPPED, RunProgressStates.STOPPED_AT),
        (RunProgressStates.INCOMING_AT, RunProgressEvents.VEHICLE_STOPPED, RunProgressStates.STOPPED_AT),
        (RunProgressStates.INCOMING_AT, RunProgressEvents.VEHICLE_IN_TRANSIT, RunProgressStates.IN_TRANSIT_TO),
        (RunProgressStates.STOPPED_AT, RunProgressEvents.VEHICLE_IN_TRANSIT, RunProgressStates.IN_TRANSIT_TO),
    ],
)
def test_expected_transitions_exist(from_state, event, to_state):
    matches = [
        t
        for t in progress_transitions.TRANSITIONS
        if t.from_state == from_state and t.event == event
    ]
    assert len(matches) == 1, f"missing transition {from_state}-{event}->{to_state}"
    assert matches[0].to_state == to_state


def test_no_self_transitions_defined():
    # Repeated same-status pings are handled by the detector (change-only),
    # so the table should never define a from==to transition.
    for t in progress_transitions.TRANSITIONS:
        assert t.from_state != t.to_state


def test_every_transition_guards_run_is_in_progress():
    from runs.domain.progress.guards import RunProgressGuards

    for t in progress_transitions.TRANSITIONS:
        assert RunProgressGuards.is_run_in_progress in t.guards
