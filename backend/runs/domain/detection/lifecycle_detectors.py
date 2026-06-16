"""Telemetry-triggered detectors that feed the lifecycle FSM.

Each ``detect`` is a pure function of the run's current lifecycle state and a
single incoming telemetry message. It returns a :class:`DetectionResult` to fire,
or ``None``. Heuristics here are intentionally simple and expected to change.
"""

from typing import Any

from runs.domain.lifecycle.states import RunLifecycleStates
from runs.domain.lifecycle.events import RunLifecycleEvents
from runs.domain.detection.result import DetectionResult

FSM = "lifecycle"

# Speed (m/s) above which a tracked vehicle is considered to have started moving.
MIN_MOVING_SPEED = 0.5


class RunTrackingStartedDetector:
    """Confirmed run + first telemetry of any kind ⇒ tracking has begun."""

    fsm = FSM

    def detect(
        self, run_state: str, leaf: str, data: dict[str, Any], payload: dict[str, Any]
    ) -> DetectionResult | None:
        if run_state == RunLifecycleStates.CONFIRMED.value:
            return DetectionResult(self.fsm, RunLifecycleEvents.RUN_TRACKING_STARTED)
        return None


class RunStartedDetector:
    """Tracking run + a position ping showing movement ⇒ the run has started."""

    fsm = FSM

    def detect(
        self, run_state: str, leaf: str, data: dict[str, Any], payload: dict[str, Any]
    ) -> DetectionResult | None:
        if run_state == RunLifecycleStates.TRACKING.value and leaf == "position":
            if float(data.get("speed", 0) or 0) > MIN_MOVING_SPEED:
                return DetectionResult(self.fsm, RunLifecycleEvents.RUN_STARTED)
        return None


class RunTrackingRestoredDetector:
    """No-signal run + any fresh telemetry ⇒ tracking restored."""

    fsm = FSM

    def detect(
        self, run_state: str, leaf: str, data: dict[str, Any], payload: dict[str, Any]
    ) -> DetectionResult | None:
        if run_state == RunLifecycleStates.NO_SIGNAL.value:
            return DetectionResult(self.fsm, RunLifecycleEvents.RUN_TRACKING_RESTORED)
        return None


class RunCompletedDetector:
    """In-progress run reporting STOPPED_AT a stop ⇒ candidate completion.

    The terminal-stop check is the FSM guard's job (``is_at_terminal_stop``); the
    detector only surfaces the candidate event and forwards the ``stop_id``.
    """

    fsm = FSM

    def detect(
        self, run_state: str, leaf: str, data: dict[str, Any], payload: dict[str, Any]
    ) -> DetectionResult | None:
        if run_state == RunLifecycleStates.IN_PROGRESS.value and leaf == "progression":
            stop_id = data.get("stop_id")
            if data.get("current_status") == "STOPPED_AT" and stop_id:
                return DetectionResult(
                    self.fsm, RunLifecycleEvents.RUN_COMPLETED, {"stop_id": stop_id}
                )
        return None


class RunInterruptedDetector:
    pass


class RunShortTurnedDetector:
    pass
