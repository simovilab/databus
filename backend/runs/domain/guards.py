from typing import Any, TYPE_CHECKING
from datetime import datetime, timezone
from django.utils.timezone import now
from runs.models import Run
from runs.services.exceptions import RunLifecycleError
import redis

if TYPE_CHECKING:
    from runs.domain.transitions import Transition

r = redis.Redis(host="state", port=6379, db=0)

TELEMETRY_GRACE_S = 60
TELEMETRY_EXPIRY_S = 300


def _parse_last_seen(payload: dict[str, Any]) -> datetime | None:
    raw = payload.get("last_seen_at")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


class RunLifecycleGuards:
    @staticmethod
    def is_gtfs_valid(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        from feed.models import Feed, Route, Trip, Shape

        route_id = payload.get("route_id")
        trip_id = payload.get("trip_id")
        direction_id = payload.get("direction_id")
        shape_id = payload.get("shape_id")
        schedule_relationship = payload.get("schedule_relationship")

        errors: dict[str, str] = {}

        if not route_id:
            errors["route_id"] = "route_id is required"
        if not trip_id:
            errors["trip_id"] = "trip_id is required"
        if direction_id not in [0, 1]:
            errors["direction_id"] = f"direction_id must be 0 or 1, got '{direction_id}'"
        if not shape_id:
            errors["shape_id"] = "shape_id is required"
        if not schedule_relationship:
            errors["schedule_relationship"] = "schedule_relationship is required"
        elif schedule_relationship != "SCHEDULED":
            errors["schedule_relationship"] = (
                f"schedule_relationship '{schedule_relationship}' is not valid"
            )

        if errors:
            raise RunLifecycleError(errors)

        feed = Feed.objects.filter(is_current=True).first()
        if not feed:
            raise RunLifecycleError({"feed": "No current GTFS feed found"})

        lookup_errors: dict[str, str] = {}

        if not Route.objects.filter(feed=feed, route_id=route_id).exists():
            lookup_errors["route_id"] = (
                f"route_id '{route_id}' not found in current GTFS feed"
            )

        trip = Trip.objects.filter(feed=feed, trip_id=trip_id).first()
        if not trip:
            lookup_errors["trip_id"] = (
                f"trip_id '{trip_id}' not found in current GTFS feed"
            )
        elif trip.direction_id != direction_id:
            lookup_errors["direction_id"] = (
                f"direction_id '{direction_id}' does not match trip '{trip_id}'"
            )
        elif shape_id and trip.shape_id != shape_id:
            lookup_errors["shape_id"] = (
                f"shape_id '{shape_id}' does not match trip '{trip_id}'"
            )

        if lookup_errors:
            raise RunLifecycleError(lookup_errors)

        return True

    @staticmethod
    def is_vehicle_available(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        vehicle_id = payload.get("vehicle_id") or (
            run.vehicle.values_list("id", flat=True).first()
        )
        if not vehicle_id:
            return True
        existing = r.get(f"vehicle:{vehicle_id}:current_run")
        if existing and existing.decode() != str(run.id):
            raise RunLifecycleError(
                {"vehicle_id": f"Vehicle '{vehicle_id}' is already assigned to run {existing.decode()}"}
            )
        return True

    @staticmethod
    def is_trip_available(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        trip_id = payload.get("trip_id") or run.trip_id
        if not trip_id:
            return True
        existing = r.get(f"trip:{trip_id}:current_run")
        if existing and existing.decode() != str(run.id):
            raise RunLifecycleError(
                {"trip_id": f"Trip '{trip_id}' is already assigned to run {existing.decode()}"}
            )
        return True

    @staticmethod
    def is_operator_available(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        operator_id = payload.get("operator_id") or (
            run.operator.values_list("id", flat=True).first()
        )
        if not operator_id:
            return True
        existing = r.get(f"operator:{operator_id}:current_run")
        if existing and existing.decode() != str(run.id):
            raise RunLifecycleError(
                {"operator_id": f"Operator '{operator_id}' is already assigned to run {existing.decode()}"}
            )
        return True

    @staticmethod
    def is_vehicle_tracked(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        return bool(r.sismember("runs:tracking", str(run.id)))

    @staticmethod
    def is_run_validated(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        return True

    @staticmethod
    def is_vehicle_moving(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        return float(payload.get("speed", 0)) > 0.5

    # ------------------------------------------------------------------
    # Cancellation / interruption / short-turn authority guards
    # ------------------------------------------------------------------

    @staticmethod
    def is_cancellation_authorized(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        actor_role = payload.get("actor_role", "")
        if actor_role == "system":
            return True
        if actor_role in ("dispatcher", "operator"):
            return True
        raise RunLifecycleError(
            {"actor_role": f"actor_role '{actor_role}' is not authorized to cancel runs"}
        )

    @staticmethod
    def is_interruption_authorized(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        actor_role = payload.get("actor_role", "")
        if actor_role in ("system", "dispatcher", "operator"):
            return True
        raise RunLifecycleError(
            {"actor_role": f"actor_role '{actor_role}' is not authorized to interrupt runs"}
        )

    @staticmethod
    def is_short_turn_authorized(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        actor_role = payload.get("actor_role", "")
        if actor_role in ("dispatcher", "system"):
            return True
        raise RunLifecycleError(
            {"actor_role": f"actor_role '{actor_role}' must be 'dispatcher' or 'system' to short-turn"}
        )

    @staticmethod
    def is_short_turn_geometrically_valid(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        from feed.models import Feed, StopTime

        short_turn_stop_id = payload.get("short_turn_stop_id")
        if not short_turn_stop_id:
            raise RunLifecycleError({"short_turn_stop_id": "short_turn_stop_id is required"})

        trip_id = run.trip_id
        if not trip_id:
            raise RunLifecycleError({"trip_id": "Run has no trip_id"})

        feed = Feed.objects.filter(is_current=True).first()
        if not feed:
            raise RunLifecycleError({"feed": "No current GTFS feed found"})

        stop_times = StopTime.objects.filter(feed=feed, trip_id=trip_id).order_by("stop_sequence")
        if not stop_times.exists():
            raise RunLifecycleError({"trip_id": f"No stop times found for trip '{trip_id}'"})

        terminal = stop_times.last()
        stop_ids = list(stop_times.values_list("stop_id", flat=True))

        if short_turn_stop_id not in stop_ids:
            raise RunLifecycleError(
                {"short_turn_stop_id": f"Stop '{short_turn_stop_id}' not on trip '{trip_id}'"}
            )
        if short_turn_stop_id == terminal.stop_id:
            raise RunLifecycleError(
                {"short_turn_stop_id": "Short-turn stop cannot be the terminal stop"}
            )
        return True

    # ------------------------------------------------------------------
    # Telemetry freshness guards
    # ------------------------------------------------------------------

    @staticmethod
    def is_telemetry_stale(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        last_seen = _parse_last_seen(payload)
        if last_seen is None:
            last_seen = run.last_event_at
        if last_seen is None:
            return True
        staleness = (now() - last_seen).total_seconds()
        return staleness > TELEMETRY_GRACE_S

    @staticmethod
    def is_telemetry_fresh(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        last_seen = _parse_last_seen(payload)
        if last_seen is None:
            last_seen = run.last_event_at
        if last_seen is None:
            return False
        staleness = (now() - last_seen).total_seconds()
        return staleness <= TELEMETRY_GRACE_S

    @staticmethod
    def is_telemetry_grace_period_exceeded(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        last_seen = _parse_last_seen(payload)
        if last_seen is None:
            last_seen = run.last_event_at
        if last_seen is None:
            return True
        staleness = (now() - last_seen).total_seconds()
        return staleness > TELEMETRY_EXPIRY_S

    # ------------------------------------------------------------------
    # Completion guard
    # ------------------------------------------------------------------

    @staticmethod
    def is_at_terminal_stop(
        run: Run, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        from feed.models import Feed, StopTime

        stop_id = payload.get("stop_id")
        if not stop_id:
            raise RunLifecycleError({"stop_id": "stop_id is required"})

        trip_id = run.trip_id
        if not trip_id:
            raise RunLifecycleError({"trip_id": "Run has no trip_id"})

        feed = Feed.objects.filter(is_current=True).first()
        if not feed:
            raise RunLifecycleError({"feed": "No current GTFS feed found"})

        terminal = (
            StopTime.objects.filter(feed=feed, trip_id=trip_id)
            .order_by("-stop_sequence")
            .first()
        )
        if not terminal:
            raise RunLifecycleError({"trip_id": f"No stop times found for trip '{trip_id}'"})

        if stop_id != terminal.stop_id:
            raise RunLifecycleError(
                {"stop_id": f"Stop '{stop_id}' is not the terminal stop '{terminal.stop_id}'"}
            )
        return True


class RunProgressGuards:
    @staticmethod
    def telemetry_lost(run: Run, payload: dict[str, Any], now: datetime) -> bool:
        return True
