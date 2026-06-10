"""Staleness-triggered detectors that feed the lifecycle FSM.

These are evaluated by the periodic ``scan_stale_runs`` task rather than on an
incoming message, so their signature takes ``staleness_s`` (seconds since the run
was last seen) instead of telemetry. Thresholds come from the single source in
:mod:`runs.domain.detection.thresholds`.
"""

from __future__ import annotations

from typing import Any

from runs.domain.lifecycle.states import RunLifecycleStates
from runs.domain.lifecycle.events import RunLifecycleEvents
from runs.domain.detection.result import DetectionResult
from runs.domain.detection.thresholds import TELEMETRY_GRACE_S, TELEMETRY_EXPIRY_S

FSM = "lifecycle"


class RunTrackingLostDetector:
    """In-progress run gone quiet past the grace window (but not yet expired)."""

    fsm = FSM

    def detect(
        self, run_state: str, staleness_s: float, payload: dict[str, Any]
    ) -> DetectionResult | None:
        if (
            run_state == RunLifecycleStates.IN_PROGRESS.value
            and TELEMETRY_GRACE_S < staleness_s <= TELEMETRY_EXPIRY_S
        ):
            return DetectionResult(
                self.fsm, RunLifecycleEvents.RUN_TRACKING_LOST, {"actor_role": "system"}
            )
        return None


class RunTrackingExpiredDetector:
    """No-signal run quiet beyond the expiry window ⇒ cancel."""

    fsm = FSM

    def detect(
        self, run_state: str, staleness_s: float, payload: dict[str, Any]
    ) -> DetectionResult | None:
        if (
            run_state == RunLifecycleStates.NO_SIGNAL.value
            and staleness_s > TELEMETRY_EXPIRY_S
        ):
            return DetectionResult(
                self.fsm,
                RunLifecycleEvents.RUN_TRACKING_EXPIRED,
                {"actor_role": "system"},
            )
        return None
