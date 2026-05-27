from runs.domain.lifecycle import TRANSITIONS


class TransitionRegistry:
    def find(self, state, event):
        return [t for t in TRANSITIONS if t.from_state == state and t.event == event]
