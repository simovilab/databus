from typing import Any
from datetime import datetime
from runs.models import Run
from runs.services.exceptions import RunLifecycleError
import redis

r = redis.Redis(host="state", port=6379, db=0)


class RunLifecycleGuards:
    @staticmethod
    def is_gtfs_valid(run: Run, payload: dict[str, Any]) -> bool:
        """
        Checks in the database that the GTFS data in the payload is valid.

        This is a placeholder implementation.
        """
        route_id = payload.get("route_id")
        trip_id = payload.get("trip_id")
        direction_id = payload.get("direction_id")
        shape_id = payload.get("shape_id")
        schedule_relationship = payload.get("schedule_relationship")
        errors: dict[str, str] = {}
        if not route_id:
            errors["route_id"] = "route_id is required"
        elif route_id != "valid":
            errors["route_id"] = (
                f"route_id '{route_id}' was not found in the current GTFS feed"
            )
        if not trip_id:
            errors["trip_id"] = "trip_id is required"
        elif trip_id != "valid":
            errors["trip_id"] = (
                f"trip_id '{trip_id}' was not found in the current GTFS feed"
            )
        if direction_id not in [0, 1]:
            errors["direction_id"] = (
                f"direction_id must be 0 or 1, got '{direction_id}'"
            )
        if not shape_id:
            errors["shape_id"] = "shape_id is required"
        elif shape_id != "valid":
            errors["shape_id"] = (
                f"shape_id '{shape_id}' was not found in the current GTFS feed"
            )
        if not schedule_relationship:
            errors["schedule_relationship"] = "schedule_relationship is required"
        elif schedule_relationship != "SCHEDULED":
            errors["schedule_relationship"] = (
                f"schedule_relationship '{schedule_relationship}' is not valid"
            )
        if errors:
            raise RunLifecycleError(errors)
        return True

    @staticmethod
    def is_vehicle_available(run: Run, payload: dict[str, Any]) -> bool:
        """
        Checks in system state (Redis) that the vehicle is not already assigned to another run at the same time.

        This is a placeholder implementation.
        """
        return True

    @staticmethod
    def is_trip_available(run: Run, payload: dict[str, Any]) -> bool:
        """
        Checks in system state (Redis) that the trip is not already assigned to another run at the same time.

        This is a placeholder implementation.
        """
        return True

    @staticmethod
    def is_operator_available(run: Run, payload: dict[str, Any]) -> bool:
        """
        Checks in system state (Redis) that the operator is not already assigned to another run at the same time.

        This is a placeholder implementation.
        """
        return True

    @staticmethod
    def is_vehicle_tracked(run: Run, payload: dict[str, Any]) -> bool:
        return r.sismember("runs:tracking", str(run.id))

    @staticmethod
    def is_run_in_progress(run: Run, payload: dict[str, Any]) -> bool:
        return r.sismember("runs:in_progress", str(run.id))

    @staticmethod
    def is_system_state_updated(run: Run, payload: dict[str, Any]) -> bool:
        return True

    @staticmethod
    def is_vehicle_moving(run: Run, payload: dict[str, Any]) -> bool:
        return payload["speed"] > 5


class RunProgressGuards:
    @staticmethod
    def telemetry_lost(run: Run, payload: dict[str, Any], now: datetime) -> bool:
        return (now - run.last_seen_at).seconds > 60
