from typing import Any, TYPE_CHECKING
from django.utils.timezone import now
from runs.models import Run, RunLifecycleEvent
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
    def persist_lifecycle_event(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Append an immutable audit record to RunLifecycleEvent."""
        RunLifecycleEvent.objects.create(  # type: ignore[attr-defined]
            run=run,
            event_type=transition.event.value,
            from_state=transition.from_state.value,
            to_state=transition.to_state.value,
            payload=payload,
            timestamp=now(),
        )
        return True

    @staticmethod
    def update_run_lifecycle_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Persist the new lifecycle state on the Run row."""
        run.run_lifecycle_state = transition.to_state
        run.save()
        return True

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

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    @staticmethod
    def publish_run_rejected(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runSubmissionRejected to the AMQP exchange.

        TODO: call publish_event("runSubmissionRejected", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_run_cancelled(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runLifecycleCancelled to the AMQP exchange.

        TODO: call publish_event("runLifecycleCancelled", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_run_interrupted(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runLifecycleInterrupted to the AMQP exchange.

        TODO: call publish_event("runLifecycleInterrupted", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_run_short_turned(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runLifecycleShortTurned to the AMQP exchange.

        TODO: call publish_event("runLifecycleShortTurned", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_tracking_lost(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runTrackingLost to the AMQP exchange.

        TODO: call publish_event("runTrackingLost", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_tracking_restored(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runTrackingRestored to the AMQP exchange.

        TODO: call publish_event("runTrackingRestored", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder

    @staticmethod
    def publish_run_completed(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Publish runLifecycleCompleted to the AMQP exchange.

        TODO: call publish_event("runLifecycleCompleted", {"run_id": str(run.id), **payload})
        """
        return True  # TODO placeholder
