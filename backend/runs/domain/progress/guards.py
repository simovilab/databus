"""Guards for the progress FSM.

Kept deliberately import-light: no top-level Django/model imports, so the FSM
definition can be imported and unit-tested without a configured Django app.
``run`` is duck-typed (anything with ``run_lifecycle_state``).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from runs.domain.lifecycle.states import RunLifecycleStates

if TYPE_CHECKING:
    from runs.domain.progress.transitions import Transition


class RunProgressGuards:
    @staticmethod
    def is_run_in_progress(
        run: Any, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Progress only advances while the run's lifecycle is IN_PROGRESS."""
        state = run.run_lifecycle_state
        # run_lifecycle_state may be an enum or its string value.
        value = getattr(state, "value", state)
        return value == RunLifecycleStates.IN_PROGRESS.value
