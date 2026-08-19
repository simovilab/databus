from typing import Any
from django.utils.timezone import now
from messages.publisher import publish_event
from runs.domain.lifecycle import RunLifecycleEvents
from runs.domain.lifecycle import RunLifecycleStates
from runs.domain.lifecycle import Transition
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
                "current_state": run.run_lifecycle_state,
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
        first_guard_error: RunLifecycleError | None = None
        for guard in transition.guards:
            try:
                passed = guard(run, transition, payload)
            except RunLifecycleError as exc:
                passed = False
                if first_guard_error is None:
                    first_guard_error = exc
            is_valid = is_valid and passed
            guards[guard.__name__] = passed
        if not is_valid and first_guard_error is not None:
            raise first_guard_error
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
        self._publish_run_lifecycle_transition(run, transition, payload)
        return transition.to_state, actions

    def _update_run_lifecycle_state(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> None:
        run.run_lifecycle_state = transition.to_state
        run.last_event_at = now()
        run.save()

    def _publish_run_lifecycle_transition(
        self, run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> None:
        """Publish the completed transition as a run lifecycle domain event (fire-and-forget)."""
        data: dict[str, Any] = {}
        vehicle_id = payload.get("vehicle_id") or run.vehicle.values_list(
            "id", flat=True
        ).first()
        if vehicle_id:
            data["vehicle_id"] = str(vehicle_id)
        if run.trip_id:
            data["trip_id"] = run.trip_id
        if run.route_id:
            data["route_id"] = run.route_id
        publish_event(
            event=transition.event.value,
            run_id=run.id,
            from_state=transition.from_state.value,
            to_state=transition.to_state.value,
            data=data,
        )

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
