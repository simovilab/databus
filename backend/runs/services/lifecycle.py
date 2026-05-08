from typing import Any
from django.utils.timezone import now
from runs.domain.events import RunLifecycleEvents
from runs.domain.states import RunLifecycleStates
from runs.domain.transitions import Transition
from runs.services.registry import TransitionRegistry
from runs.services.exceptions import RunLifecycleError
from runs.models import Run


class RunLifecycleService:
    def __init__(self) -> None:
        self.registry: TransitionRegistry = TransitionRegistry()

    def process_event(
        self, event: RunLifecycleEvents, payload: dict[str, Any]
    ) -> RunLifecycleStates:
        run = self._load_run(payload)
        candidates = self.registry.find(run.run_lifecycle_state, event)
        print(
            f"Candidates for event '{event}' in state '{run.run_lifecycle_state}': {candidates}"
        )
        for transition in candidates:
            if self._check_guards(run, transition, payload):
                return self._apply_transition(run, transition, payload)
        raise RunLifecycleError(
            {
                "detail": f"No valid transition for event '{event}' from state '{run.run_lifecycle_state}'. Guards may have failed."
            }
        )

    def _load_run(self, payload: dict[str, Any]) -> Run:
        run_id = payload.get("run_id")
        return Run.objects.get(id=run_id)

    def _check_guards(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> bool:
        return all(guard(run, payload) for guard in transition.guards)

    def _execute_actions(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> None:
        for action in transition.actions:
            action(run, transition, payload)

    def _apply_transition(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> RunLifecycleStates:
        try:
            self._execute_actions(run, transition, payload)
        except RunLifecycleError as exc:
            raise RunLifecycleError({"detail": str(exc)}) from exc
        old_state = run.run_lifecycle_state
        run.run_lifecycle_state = transition.to_state
        run.last_event_at = now()
        run.save()
        self._publish_transition_event(run, old_state, transition.to_state)
        return transition.to_state

    def _publish_transition_event(
        self, run: Run, old: RunLifecycleStates, new: RunLifecycleStates
    ) -> None:
        pass
