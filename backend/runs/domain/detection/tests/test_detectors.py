"""Pure unit tests for lifecycle detectors — no Django/Redis required.

Detectors are pure functions of (state, telemetry) → DetectionResult | None.
"""

import pytest

from runs.domain.lifecycle.states import RunLifecycleStates
from runs.domain.detection.lifecycle_detectors import (
    RunTrackingStartedDetector,
    RunStartedDetector,
    RunTrackingRestoredDetector,
    RunCompletedDetector,
)
from runs.domain.detection.periodic_detectors import (
    RunTrackingLostDetector,
    RunTrackingExpiredDetector,
)
from runs.domain.detection import thresholds

TRACKING = RunLifecycleStates.TRACKING.value
CONFIRMED = RunLifecycleStates.CONFIRMED.value
NO_SIGNAL = RunLifecycleStates.NO_SIGNAL.value
IN_PROGRESS = RunLifecycleStates.IN_PROGRESS.value


# --------------------------------------------------------------------------
# Lifecycle telemetry detectors
# --------------------------------------------------------------------------


def test_tracking_started_fires_on_any_telemetry_when_confirmed():
    res = RunTrackingStartedDetector().detect(CONFIRMED, "position", {}, {})
    assert res is not None
    assert res.fsm == "lifecycle"
    assert res.event == "run_tracking_started"


def test_tracking_started_silent_when_not_confirmed():
    assert RunTrackingStartedDetector().detect(TRACKING, "position", {}, {}) is None


@pytest.mark.parametrize(
    "speed,expected",
    [(0.0, None), (0.5, None), (0.51, "run_started"), (12.0, "run_started")],
)
def test_run_started_speed_boundary(speed, expected):
    res = RunStartedDetector().detect(TRACKING, "position", {"speed": speed}, {})
    assert (res.event if res else None) == expected


def test_run_started_ignores_non_position_leaf():
    assert (
        RunStartedDetector().detect(TRACKING, "progression", {"speed": 9}, {}) is None
    )


def test_run_started_silent_when_not_tracking():
    assert (
        RunStartedDetector().detect(IN_PROGRESS, "position", {"speed": 9}, {}) is None
    )


def test_tracking_restored_fires_when_no_signal():
    res = RunTrackingRestoredDetector().detect(NO_SIGNAL, "occupancy", {}, {})
    assert res is not None and res.event == "run_tracking_restored"


def test_completed_fires_on_stopped_at_with_stop_id():
    data = {"current_status": "STOPPED_AT", "stop_id": "TERM-1"}
    res = RunCompletedDetector().detect(IN_PROGRESS, "progression", data, {})
    assert res is not None
    assert res.event == "run_completed"
    assert res.extra_payload == {"stop_id": "TERM-1"}


def test_completed_silent_without_stop_id():
    data = {"current_status": "STOPPED_AT"}
    assert RunCompletedDetector().detect(IN_PROGRESS, "progression", data, {}) is None


def test_completed_silent_when_not_stopped():
    data = {"current_status": "IN_TRANSIT_TO", "stop_id": "X"}
    assert RunCompletedDetector().detect(IN_PROGRESS, "progression", data, {}) is None


# --------------------------------------------------------------------------
# Periodic (staleness) detectors
# --------------------------------------------------------------------------

GRACE = thresholds.TELEMETRY_GRACE_S
EXPIRY = thresholds.TELEMETRY_EXPIRY_S


@pytest.mark.parametrize(
    "staleness,state,expected",
    [
        (GRACE - 1, IN_PROGRESS, None),
        (GRACE + 1, IN_PROGRESS, "run_tracking_lost"),
        (EXPIRY, IN_PROGRESS, "run_tracking_lost"),
        (EXPIRY + 1, IN_PROGRESS, None),  # beyond expiry handled by expired detector
        (GRACE + 1, NO_SIGNAL, None),  # wrong state
    ],
)
def test_tracking_lost_window(staleness, state, expected):
    res = RunTrackingLostDetector().detect(state, staleness, {})
    assert (res.event if res else None) == expected


@pytest.mark.parametrize(
    "staleness,state,expected",
    [
        (EXPIRY, NO_SIGNAL, None),
        (EXPIRY + 1, NO_SIGNAL, "run_tracking_expired"),
        (EXPIRY + 1, IN_PROGRESS, None),  # wrong state
    ],
)
def test_tracking_expired_window(staleness, state, expected):
    res = RunTrackingExpiredDetector().detect(state, staleness, {})
    assert (res.event if res else None) == expected


def test_periodic_detectors_tag_lifecycle_and_system_actor():
    res = RunTrackingLostDetector().detect(IN_PROGRESS, GRACE + 5, {})
    assert res.fsm == "lifecycle"
    assert res.extra_payload.get("actor_role") == "system"
