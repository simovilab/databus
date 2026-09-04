"""Look up FSM transitions for a given run lifecycle state and event."""

from runs.domain.lifecycle import TRANSITIONS, RunLifecycleEvents, Transition


class TransitionRegistry:
    """Query the static TRANSITIONS table for candidate run lifecycle transitions."""

    def find(self, state: str | None, event: RunLifecycleEvents) -> list[Transition]:
        """Return the transitions whose from_state and event match, in table order.

        `state` accepts a plain string because callers pass the Run model's raw
        `run_lifecycle_state` CharField value; `RunLifecycleStates` is itself a
        `str` subclass so the `==` comparison against `Transition.from_state`
        works for either a raw string or an enum member.
        """
        return [t for t in TRANSITIONS if t.from_state == state and t.event == event]
