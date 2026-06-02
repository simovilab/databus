class TransitionRegistry:
    """Finds candidate transitions for a (state, event) pair.

    Defaults to the lifecycle transition table for backwards compatibility; the
    progress service passes its own table. The transitions list is duck-typed —
    any object with ``from_state`` / ``event`` attributes works.
    """

    def __init__(self, transitions=None):
        if transitions is None:
            from runs.domain.lifecycle import TRANSITIONS

            transitions = TRANSITIONS
        self._transitions = transitions

    def find(self, state, event):
        return [
            t
            for t in self._transitions
            if t.from_state == state and t.event == event
        ]
