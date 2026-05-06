from dataclasses import dataclass
from typing import Callable, List
from .guards import has_valid_gtfs
from .events import RUN_VALIDATED
from runs.domain.states import RunStatus


@dataclass
class Transition:
    from_state: str
    event: str
    to_state: str
    guards: List[Callable]


TRANSITIONS = [
    Transition(
        from_state="REQUESTED",
        event=RUN_VALIDATED,
        to_state="VALIDATED",
        guards=[has_valid_gtfs],
    ),
]


def validate_transition_states_exist() -> None:
    defined_states = set(RunStatus.__members__.keys())
    referenced_states = {t.from_state for t in TRANSITIONS} | {
        t.to_state for t in TRANSITIONS
    }
    unknown_states = sorted(referenced_states - defined_states)

    assert not unknown_states, "Unknown run state(s) in TRANSITIONS: " + ", ".join(
        unknown_states
    )


validate_transition_states_exist()
