from typing import Any, TYPE_CHECKING
from runs.models import Run
import redis

if TYPE_CHECKING:
    from runs.domain import Transition

r = redis.Redis(host="state", port=6379, db=0)


class RunLifecycleActions:
    """
    Ordering convention: every transition should list persist_lifecycle_event
    first so the audit record is written before any external side-effects. State
    is saved last via update_run_lifecycle_state so the Run row always reflects
    the final outcome of a fully-executed transition.
    """

    @staticmethod
    def update_system_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Write run metadata to run:{run.id} hash and claim vehicle/operator/trip keys."""
        vehicle_id = (
            payload.get("vehicle_id")
            or run.vehicle.values_list("id", flat=True).first()
        )
        operator_id = (
            payload.get("operator_id")
            or run.operator.values_list("id", flat=True).first()
        )
        run_key = f"run:{run.id}"
        mapping: dict[str, str] = {
            "run_id": str(run.id),
            "route_id": run.route_id or "",
            "trip_id": run.trip_id or "",
            "direction_id": "" if run.direction_id is None else str(run.direction_id),
            "shape_id": run.shape_id or "",
            "schedule_relationship": run.schedule_relationship or "",
            # Use transition.to_state because the action fires before _update_run_lifecycle_state
            "run_lifecycle_state": transition.to_state.value,
        }
        if vehicle_id:
            mapping["vehicle"] = str(vehicle_id)
        if operator_id:
            mapping["operator"] = str(operator_id)
        if run.start_date:
            mapping["start_date"] = run.start_date.strftime("%Y%m%d")
        if run.start_time:
            total_seconds = int(run.start_time.total_seconds())
            h, rem = divmod(total_seconds, 3600)
            m, s = divmod(rem, 60)
            mapping["start_time"] = f"{h:02d}:{m:02d}:{s:02d}"

        pipe = r.pipeline()
        pipe.hset(run_key, mapping=mapping)

        # Claim assignment keys so availability guards have a signal to read
        if vehicle_id:
            pipe.set(f"vehicle:{vehicle_id}:current_run", str(run.id))
        if operator_id:
            pipe.set(f"operator:{operator_id}:current_run", str(run.id))
        if run.trip_id:
            pipe.set(f"trip:{run.trip_id}:current_run", str(run.id))

        # Write vehicle metadata so the GTFS-RT builders can populate VehicleDescriptor
        if vehicle_id:
            from operations.models import Vehicle as VehicleModel

            try:
                v = VehicleModel.objects.get(id=vehicle_id)
                vehicle_meta: dict[str, str] = {
                    "id": str(v.id),
                    "label": v.label or str(v.id),
                }
                if v.license_plate:
                    vehicle_meta["license_plate"] = v.license_plate
                if v.wheelchair_accessible:
                    vehicle_meta["wheelchair_accessible"] = v.wheelchair_accessible
                pipe.hset(f"vehicle:{vehicle_id}:metadata", mapping=vehicle_meta)
            except Exception:
                pass

        pipe.execute()
        return True

    # ------------------------------------------------------------------
    # Redis set mutations
    # ------------------------------------------------------------------

    @staticmethod
    def sync_lifecycle_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Keep the Redis run hash's run_lifecycle_state in sync with the DB transition."""
        r.hset(f"run:{run.id}", "run_lifecycle_state", transition.to_state.value)
        return True

    @staticmethod
    def add_to_tracking_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        r.sadd("runs:tracking", str(run.id))
        return True

    @staticmethod
    def remove_from_tracking_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        r.srem("runs:tracking", str(run.id))
        return True

    @staticmethod
    def add_to_in_progress_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        r.sadd("runs:in_progress", str(run.id))
        return True

    @staticmethod
    def remove_from_in_progress_set(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        r.srem("runs:in_progress", str(run.id))
        return True

    @staticmethod
    def remove_from_system_state(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        pipe = r.pipeline()
        pipe.delete(f"run:{run.id}")
        pipe.srem("runs:tracking", str(run.id))
        pipe.srem("runs:in_progress", str(run.id))
        pipe.execute()
        return True

    # ------------------------------------------------------------------
    # Resource release
    # ------------------------------------------------------------------

    @staticmethod
    def release_resources(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Free vehicle, operator, and trip assignment keys."""
        vehicle_id = run.vehicle.values_list("id", flat=True).first()
        operator_id = run.operator.values_list("id", flat=True).first()
        keys_to_delete = []
        if vehicle_id:
            keys_to_delete.append(f"vehicle:{vehicle_id}:current_run")
        if operator_id:
            keys_to_delete.append(f"operator:{operator_id}:current_run")
        if run.trip_id:
            keys_to_delete.append(f"trip:{run.trip_id}:current_run")
        if keys_to_delete:
            r.delete(*keys_to_delete)
        return True
