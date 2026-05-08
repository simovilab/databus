from typing import Any, TYPE_CHECKING
from runs.models import Run

if TYPE_CHECKING:
    from runs.domain.transitions import Transition


class RunLifecycleActions:
    """
    Defines the possible actions that can be taken during a run's lifecycle.
    """

    @staticmethod
    def update_run_lifecycle_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """
        Updates the run model in the database with the new lifecycle state in a transition.
        """
        new_state = transition.to_state
        run.run_lifecycle_state = new_state
        run.save()
        return True

    @staticmethod
    def update_system_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """
        Updates the working system state in memory based on the transition.
        """
        run = run
        transition = transition
        payload = payload
        return True
