from typing import Any
from django.utils.timezone import now
from runs.domain.events import RunLifecycleEvents
from runs.domain.states import RunLifecycleStates
from runs.domain.transitions import Transition
from runs.services.registry import TransitionRegistry
from runs.services.exceptions import RunLifecycleError
from runs.models import Run, RunLifecycleTransition


class RunLifecycleService:
    def __init__(self) -> None:
        self.registry: TransitionRegistry = TransitionRegistry()

    def process_event(
        self, event: RunLifecycleEvents, payload: dict[str, Any]
    ) -> tuple[RunLifecycleStates, dict[str, bool], dict[str, bool]]:
        run = self._load_run(payload)
        candidates = self.registry.find(run.run_lifecycle_state, event)
        attempts: list[dict[str, Any]] = []
        for transition in candidates:
            is_valid, guards = self._check_guards(run, transition, payload)
            actions: dict[str, bool] = {}
            if is_valid:
                to_state, actions = self._apply_transition(run, transition, payload)
                self._persist_run_lifecycle_transition(run, transition, guards, actions)
                return to_state, guards, actions
            self._persist_run_lifecycle_transition(run, transition, guards, actions)
            attempts.append(
                {
                    "event_name": transition.event.value,
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "guards": guards,
                    "actions": actions,
                }
            )
        raise RunLifecycleError(
            {
                "detail": f"No valid transition for event '{event}' from state '{run.run_lifecycle_state}'.",
                "attempts": attempts,
            }
        )

    def _load_run(self, payload: dict[str, Any]) -> Run:
        run_id = payload.get("run_id")
        return Run.objects.get(id=run_id)

    def _check_guards(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> tuple[bool, dict[str, bool]]:
        guards = {}
        is_valid = True
        for guard in transition.guards:
            passed = guard(run, transition, payload)
            is_valid = is_valid and passed
            guards[guard.__name__] = passed
        return is_valid, guards

    def _execute_actions(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> dict[str, bool]:
        actions = {}
        for action in transition.actions:
            actions[action.__name__] = action(run, transition, payload)
        return actions

    def _apply_transition(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> tuple[RunLifecycleStates, dict[str, bool]]:
        try:
            actions = self._execute_actions(run, transition, payload)
        except RunLifecycleError as exc:
            raise RunLifecycleError({"detail": str(exc)}) from exc
        self._update_run_lifecycle_state(run, transition, payload)
        self._publish_run_lifecycle_transition(run, transition.to_state)
        return transition.to_state, actions

    def _update_run_lifecycle_state(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> bool:
        run.run_lifecycle_state = transition.to_state
        run.last_event_at = now()
        run.save()

    def _publish_run_lifecycle_transition(
        self, run: Run, new: RunLifecycleStates
    ) -> None:
        pass

    def _persist_run_lifecycle_transition(
        self,
        run: Run,
        transition: "Transition",
        guards: dict[str, bool],
        actions: dict[str, bool],
    ) -> None:
        """Append an immutable audit record to RunLifecycleEvent."""
        RunLifecycleTransition.objects.create(  # type: ignore[attr-defined]
            run=run,
            event_name=transition.event.value,
            from_state=transition.from_state.value,
            to_state=transition.to_state.value,
            guards=guards,
            actions=actions,
            timestamp=now(),
        )
        return None
