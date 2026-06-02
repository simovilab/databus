"""Progress FSM service.

Mirrors :class:`RunLifecycleService` (load → find candidate transitions → check
guards → run actions) but for the progress FSM. Two deliberate differences:

* The current state lives in Redis (``run:{id}`` hash, ``run_progress_state``),
  not on the ``Run`` model — progress changes too frequently for a DB write per
  ping, and ``RunProgressEvent`` already provides the durable audit trail.
* State persistence is done by the transition's *actions*
  (``sync_progress_state`` + ``persist_progress_event``), so the service only
  orchestrates; it does not write the run row.
"""

from __future__ import annotations

import os
from typing import Any

import redis

from runs.domain.progress import TRANSITIONS, RunProgressStates
from runs.domain.progress.transitions import Transition
from runs.services.registry import TransitionRegistry
from runs.services.exceptions import RunLifecycleError
from runs.models import Run

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)

_DEFAULT_STATE = RunProgressStates.IN_TRANSIT_TO.value


class RunProgressService:
    def __init__(self) -> None:
        self.registry = TransitionRegistry(TRANSITIONS)

    def process_event(self, event, payload: dict[str, Any]):
        run = self._load_run(payload)
        state = self._current_state(run)
        candidates = self.registry.find(state, event)
        for transition in candidates:
            is_valid, guards = self._check_guards(run, transition, payload)
            if is_valid:
                self._execute_actions(run, transition, payload)
                return transition.to_state
            # guards failed → not a valid transition; keep trying candidates
        raise RunLifecycleError(
            {
                "detail": (
                    f"No valid progress transition for event '{event}' "
                    f"from state '{state}'."
                )
            }
        )

    def _load_run(self, payload: dict[str, Any]) -> Run:
        return Run.objects.get(id=payload.get("run_id"))

    def _current_state(self, run: Run) -> str:
        return r.hget(f"run:{run.id}", "run_progress_state") or _DEFAULT_STATE

    def _check_guards(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> tuple[bool, dict[str, bool]]:
        guards: dict[str, bool] = {}
        is_valid = True
        for guard in transition.guards:
            try:
                passed = guard(run, transition, payload)
            except RunLifecycleError:
                passed = False
            guards[guard.__name__] = passed
            is_valid = is_valid and passed
        return is_valid, guards

    def _execute_actions(
        self, run: Run, transition: Transition, payload: dict[str, Any]
    ) -> None:
        for action in transition.actions:
            action(run, transition, payload)
