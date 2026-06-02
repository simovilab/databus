"""Telemetry-triggered detector that feeds the progress FSM.

The progress FSM tracks the vehicle's GTFS-RT ``current_status`` during a run.
The detector trusts the reported status (simple heuristic, expected to change)
and only emits an event when the status actually *changes* from the run's current
progress state — repeated identical statuses are absorbed here so the FSM never
needs self-transitions.
"""

from __future__ import annotations

from typing import Any

from runs.domain.progress.states import RunProgressStates
from runs.domain.progress.events import RunProgressEvents
from runs.domain.detection.result import DetectionResult

FSM = "progress"

# Reported GTFS-RT status → progress event that moves the FSM into that status.
_STATUS_TO_EVENT = {
    RunProgressStates.IN_TRANSIT_TO.value: RunProgressEvents.VEHICLE_IN_TRANSIT.value,
    RunProgressStates.INCOMING_AT.value: RunProgressEvents.VEHICLE_INCOMING.value,
    RunProgressStates.STOPPED_AT.value: RunProgressEvents.VEHICLE_STOPPED.value,
}


class VehicleStatusDetector:
    """Progression ping with a new ``current_status`` ⇒ progress event.

    ``run_state`` here is the run's current *progress* state (the dispatcher
    passes the state matching this detector's ``fsm``).
    """

    fsm = FSM

    @staticmethod
    def detect(
        run_state: str, leaf: str, data: dict[str, Any], payload: dict[str, Any]
    ) -> DetectionResult | None:
        if leaf != "progression":
            return None
        status = data.get("current_status")
        event = _STATUS_TO_EVENT.get(status)
        if event is None:
            return None  # unknown / missing status
        if status == run_state:
            return None  # no change
        extra = {
            "stop_id": data.get("stop_id"),
            "current_stop_sequence": data.get("current_stop_sequence"),
        }
        return DetectionResult(FSM, event, extra)
