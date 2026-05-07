from typing import Any
from datetime import datetime
from runs.models import Run


class RunLifecycleGuards:
    @staticmethod
    def has_valid_gtfs(run: Run, payload: dict[str, Any]) -> bool:
        return True

    @staticmethod
    def is_vehicle_available(run: Run, payload: dict[str, Any]) -> bool:
        return True

    @staticmethod
    def is_trip_available(run: Run, payload: dict[str, Any]) -> bool:
        return True

    @staticmethod
    def has_valid_telemetry(run: Run, payload: dict[str, Any]) -> bool:
        return payload["timestamp"] is not None

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
