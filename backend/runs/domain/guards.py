from typing import Any
from datetime import datetime
from runs.models import Run
from runs.services.exceptions import RunLifecycleError
import redis

r = redis.Redis(host="state", port=6379, db=0)

# Thresholds for telemetry freshness checks. Move to Django settings when stabilised.
TELEMETRY_GRACE_S = 60
TELEMETRY_EXPIRY_S = 300


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
        return bool(r.sismember("runs:tracking", str(run.id)))

    @staticmethod
    def is_run_in_progress(run: Run, payload: dict[str, Any]) -> bool:
        return bool(r.sismember("runs:in_progress", str(run.id)))

    @staticmethod
    def is_system_state_updated(run: Run, payload: dict[str, Any]) -> bool:
        return True

    @staticmethod
    def is_vehicle_moving(run: Run, payload: dict[str, Any]) -> bool:
        return payload["speed"] > 5

    # ------------------------------------------------------------------
    # Rejection guards
    # ------------------------------------------------------------------

    @staticmethod
    def is_validation_failure_recorded(run: Run, payload: dict[str, Any]) -> bool:
        """GTFS or business-rule validation failed before the run was initialized.

        Required payload keys:
            rejection_reason (str): human-readable reason for rejection

        TODO: verify the rejection_reason is present and non-empty so the audit
        log is always meaningful.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_initialization_failure_recorded(run: Run, payload: dict[str, Any]) -> bool:
        """System-state initialization failed after GTFS validation passed.

        Required payload keys:
            rejection_reason (str): human-readable reason for the failure

        TODO: verify the rejection_reason is present and non-empty.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_confirmation_failure_recorded(run: Run, payload: dict[str, Any]) -> bool:
        """Operator or system confirmation step failed for a CONFIRMED run.

        Required payload keys:
            rejection_reason (str): human-readable reason for the failure

        TODO: verify the rejection_reason is present and non-empty.
        """
        return True  # TODO placeholder

    # ------------------------------------------------------------------
    # Cancellation / interruption / short-turn authority guards
    # ------------------------------------------------------------------

    @staticmethod
    def is_cancellation_authorized(run: Run, payload: dict[str, Any]) -> bool:
        """The actor requesting cancellation has authority over this run.

        Required payload keys:
            actor_id (UUID): the user or system identifier
            actor_role (str): one of {"operator", "dispatcher", "system"}
            reason (str): free-text justification persisted in the audit log

        TODO: cross-check that actor_id has dispatcher role OR is the assigned
        operator on this run. System-initiated cancellations always pass.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_interruption_authorized(run: Run, payload: dict[str, Any]) -> bool:
        """The actor requesting interruption has authority over this run.

        Required payload keys:
            actor_id (UUID): the user or system identifier
            actor_role (str): one of {"operator", "dispatcher", "system"}
            reason (str): free-text justification persisted in the audit log

        TODO: same authority logic as is_cancellation_authorized; interruption
        may additionally require a minimum run duration (e.g. > 2 minutes
        in progress) to distinguish from an accidental start.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_short_turn_authorized(run: Run, payload: dict[str, Any]) -> bool:
        """The actor requesting short-turn has dispatcher-level authority.

        Required payload keys:
            actor_id (UUID)
            actor_role (str): must be "dispatcher" or "system"
            short_turn_stop_id (str): the stop at which the run will terminate early
            reason (str): free-text justification

        TODO: verify actor_role is "dispatcher" or "system" (operators cannot
        self-authorize a short-turn unilaterally).
        """
        return True  # TODO placeholder

    @staticmethod
    def is_short_turn_geometrically_valid(run: Run, payload: dict[str, Any]) -> bool:
        """The short-turn stop lies on the run's shape and before the terminal stop.

        Required payload keys:
            short_turn_stop_id (str): the stop at which the run terminates early

        TODO: look up the stop sequence for run.trip_id, confirm
        short_turn_stop_id appears in it, and confirm it is not the last stop
        (which would be a normal completion, not a short-turn).
        """
        return True  # TODO placeholder

    # ------------------------------------------------------------------
    # Telemetry freshness guards
    # ------------------------------------------------------------------

    @staticmethod
    def is_telemetry_stale(run: Run, payload: dict[str, Any]) -> bool:
        """No telemetry has been received for longer than TELEMETRY_GRACE_S seconds.

        Required payload keys:
            last_seen_at (datetime | ISO-8601 str): timestamp of last received ping

        TODO: parse last_seen_at from payload and compare against utcnow().
        Fall back to run.last_event_at if last_seen_at is absent.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_telemetry_fresh(run: Run, payload: dict[str, Any]) -> bool:
        """A valid telemetry ping has been received within TELEMETRY_GRACE_S seconds.

        Required payload keys:
            last_seen_at (datetime | ISO-8601 str): timestamp of last received ping

        TODO: inverse of is_telemetry_stale — same implementation, negated result.
        """
        return True  # TODO placeholder

    @staticmethod
    def is_telemetry_grace_period_exceeded(run: Run, payload: dict[str, Any]) -> bool:
        """No telemetry for longer than TELEMETRY_EXPIRY_S seconds (hard expiry).

        Required payload keys:
            last_seen_at (datetime | ISO-8601 str): timestamp of last received ping

        TODO: same as is_telemetry_stale but uses TELEMETRY_EXPIRY_S threshold.
        Triggers an INTERRUPTED transition rather than a NO_SIGNAL one.
        """
        return True  # TODO placeholder

    # ------------------------------------------------------------------
    # Completion guard
    # ------------------------------------------------------------------

    @staticmethod
    def is_at_terminal_stop(run: Run, payload: dict[str, Any]) -> bool:
        """The vehicle has reached the last stop of the scheduled trip.

        Required payload keys:
            stop_id (str): the stop the vehicle just arrived at

        TODO: look up the stop sequence for run.trip_id in the GTFS feed,
        find the stop with the highest stop_sequence, and compare its
        stop_id against payload["stop_id"].
        """
        return True  # TODO placeholder


class RunProgressGuards:
    @staticmethod
    def telemetry_lost(run: Run, payload: dict[str, Any], now: datetime) -> bool:
        # TODO: implement once Run has a last_seen_at timestamp field
        return True  # TODO placeholder
