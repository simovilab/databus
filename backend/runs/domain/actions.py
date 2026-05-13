from typing import Any, TYPE_CHECKING
from django.utils.timezone import now
from runs.models import Run
import redis

if TYPE_CHECKING:
    from runs.domain.transitions import Transition

r = redis.Redis(host="state", port=6379, db=0)


class RunLifecycleActions:
    """
    Defines the possible actions that can be taken during a run's lifecycle.

    Ordering convention: every transition should list persist_lifecycle_event
    first so the audit record is written before any external side-effects. State
    is saved last via update_run_lifecycle_state so the Run row always reflects
    the final outcome of a fully-executed transition.
    """

    # ------------------------------------------------------------------
    # Core (implemented)
    # ------------------------------------------------------------------

    @staticmethod
    def update_system_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Write run data to the Redis hash so other services can read system state.

        TODO: serialize relevant run fields into run:{run.id} hash key.
        """
        return True  # TODO placeholder

    # ------------------------------------------------------------------
    # Redis set mutations
    # ------------------------------------------------------------------

    @staticmethod
    def add_to_tracking_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Add run to the runs:tracking Redis set.

        TODO: r.sadd("runs:tracking", str(run.id))
        """
        return True  # TODO placeholder

    @staticmethod
    def remove_from_tracking_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Remove run from the runs:tracking Redis set.

        TODO: r.srem("runs:tracking", str(run.id))
        """
        return True  # TODO placeholder

    @staticmethod
    def add_to_in_progress_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Add run to the runs:in_progress Redis set.

        TODO: r.sadd("runs:in_progress", str(run.id))
        """
        return True  # TODO placeholder

    @staticmethod
    def remove_from_in_progress_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Remove run from the runs:in_progress Redis set.

        TODO: r.srem("runs:in_progress", str(run.id))
        """
        return True  # TODO placeholder

    @staticmethod
    def remove_from_system_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Delete the run:{id} hash and remove from all Redis sets.

        TODO: pipeline r.delete("run:{run.id}"), srem from tracking and
        in_progress sets, and any other membership keys.
        """
        return True  # TODO placeholder

    # ------------------------------------------------------------------
    # Resource release
    # ------------------------------------------------------------------

    @staticmethod
    def release_resources(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Free the vehicle and operator so they can be assigned to another run.

        TODO: clear the "currently assigned" Redis keys for run.vehicle and
        run.operator so is_vehicle_available / is_operator_available guards
        pass for future runs using the same assets.
        """
        return True  # TODO placeholder


    

