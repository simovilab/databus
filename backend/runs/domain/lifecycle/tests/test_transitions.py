"""Unit tests for ``target_state_for_event``.

Used by ``realtime_engine.tasks.run_lifecycle_event`` to recognize an
idempotent event re-fire (the run already reached the event's target state
via a race-winning duplicate detection) versus a genuinely invalid
transition. Pure function over the ``TRANSITIONS`` table — no Redis/DB.
"""

import pytest

from runs.domain.lifecycle.events import RunLifecycleEvents
from runs.domain.lifecycle.states import RunLifecycleStates
from runs.domain.lifecycle.transitions import target_state_for_event


@pytest.mark.parametrize(
    "event,expected",
    [
        (RunLifecycleEvents.VALIDATE_RUN, RunLifecycleStates.VALIDATED),
        (RunLifecycleEvents.INITIALIZE_RUN, RunLifecycleStates.INITIALIZED),
        (
            RunLifecycleEvents.RUN_CONFIRMED_BY_OPERATOR,
            RunLifecycleStates.CONFIRMED,
        ),
        (RunLifecycleEvents.RUN_TRACKING_STARTED, RunLifecycleStates.TRACKING),
        (RunLifecycleEvents.RUN_STARTED, RunLifecycleStates.IN_PROGRESS),
        (RunLifecycleEvents.RUN_COMPLETED, RunLifecycleStates.COMPLETED),
        (RunLifecycleEvents.RUN_TRACKING_RESTORED, RunLifecycleStates.IN_PROGRESS),
        (RunLifecycleEvents.RUN_TRACKING_LOST, RunLifecycleStates.NO_SIGNAL),
        (RunLifecycleEvents.RUN_TRACKING_EXPIRED, RunLifecycleStates.CANCELLED),
        (RunLifecycleEvents.RUN_INTERRUPTED, RunLifecycleStates.INTERRUPTED),
        (RunLifecycleEvents.RUN_SHORT_TURNED, RunLifecycleStates.SHORT_TURNED),
        # Appears from three different from_states but always lands CANCELLED
        # — still unambiguous.
        (RunLifecycleEvents.RUN_REJECTED, RunLifecycleStates.CANCELLED),
        (RunLifecycleEvents.CANCEL_RUN, RunLifecycleStates.CANCELLED),
    ],
)
def test_target_state_for_event_unambiguous(event, expected):
    assert target_state_for_event(event) == expected


def test_target_state_for_event_returns_none_when_event_has_no_transitions():
    # RUN_REQUESTED never appears in TRANSITIONS — REQUESTED is the model's
    # own default, not reached via a transition.
    assert target_state_for_event(RunLifecycleEvents.RUN_REQUESTED) is None
