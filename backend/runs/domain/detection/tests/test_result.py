"""Pure unit tests for the detection result primitive and thresholds.

These tests intentionally avoid Django/Redis so they run under plain pytest.
"""

from runs.domain.detection.result import DetectionResult
from runs.domain.detection import thresholds


def test_detection_result_holds_fsm_event_and_payload():
    result = DetectionResult(fsm="lifecycle", event="run_started", extra_payload={"stop_id": "s1"})
    assert result.fsm == "lifecycle"
    assert result.event == "run_started"
    assert result.extra_payload == {"stop_id": "s1"}


def test_detection_result_defaults_to_empty_payload():
    result = DetectionResult(fsm="progress", event="vehicle_stopped")
    assert result.extra_payload == {}


def test_detection_result_is_immutable():
    result = DetectionResult(fsm="lifecycle", event="run_started")
    try:
        result.event = "other"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("DetectionResult should be frozen/immutable")


def test_thresholds_are_consistent_single_source():
    # Grace must be strictly less than expiry, and both positive.
    assert thresholds.TELEMETRY_GRACE_S > 0
    assert thresholds.TELEMETRY_EXPIRY_S > thresholds.TELEMETRY_GRACE_S
