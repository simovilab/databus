"""Regression coverage for the impure dispatch wrapper's state gate.

Detectors are pure functions of (state, telemetry) and already refuse to
recognize an event that the run's current lifecycle state makes invalid
(see ``test_detectors.py``). This module checks the same guarantee one layer
up, at the impure wrapper that actually reads Redis and enqueues the
lifecycle Celery task — i.e. that a run which already reached an event's
target state does not get that event re-dispatched by further telemetry or
scan ticks. This is the exact "flood of ERROR logs" symptom the gate closes:
without it, ``run_lifecycle_event`` would repeatedly reject the event with
``RunLifecycleError`` for a state the run has already left behind.

Redis is mocked (module-level ``dispatch.r``); ``run_lifecycle_event.delay``
is mocked so no Celery broker/Django DB access is needed.
"""

from unittest.mock import MagicMock, patch

import runs.domain.detection.dispatch as dispatch_module
from runs.domain.detection.dispatch import detect_from_scan, detect_from_telemetry
from runs.domain.lifecycle.states import RunLifecycleStates

RUN_ID = "run-1"
VEHICLE_ID = "veh-1"


def _fake_redis(lifecycle_state: str) -> MagicMock:
    r = MagicMock()
    r.hget.return_value = lifecycle_state
    return r


def test_run_started_not_redispatched_when_already_in_progress(monkeypatch):
    """A moving-speed position update for a run already IN_PROGRESS must not
    re-fire run_started (the reported defect)."""
    monkeypatch.setattr(
        dispatch_module, "r", _fake_redis(RunLifecycleStates.IN_PROGRESS.value)
    )

    with patch("realtime_engine.tasks.run_lifecycle_event.delay") as mock_delay:
        detect_from_telemetry(RUN_ID, VEHICLE_ID, "position", {"speed": 12.0})

    mock_delay.assert_not_called()


def test_run_started_still_fires_from_tracking(monkeypatch):
    """Sanity check: the legitimate predecessor state still fires — the gate
    above isn't vacuously true."""
    monkeypatch.setattr(
        dispatch_module, "r", _fake_redis(RunLifecycleStates.TRACKING.value)
    )

    with patch("realtime_engine.tasks.run_lifecycle_event.delay") as mock_delay:
        detect_from_telemetry(RUN_ID, VEHICLE_ID, "position", {"speed": 12.0})

    mock_delay.assert_called_once()
    args, _ = mock_delay.call_args
    assert args[0] == "run_started"


def test_run_tracking_started_not_redispatched_when_already_tracking(monkeypatch):
    """Any telemetry for a run already TRACKING must not re-fire
    run_tracking_started."""
    monkeypatch.setattr(
        dispatch_module, "r", _fake_redis(RunLifecycleStates.TRACKING.value)
    )

    with patch("realtime_engine.tasks.run_lifecycle_event.delay") as mock_delay:
        detect_from_telemetry(RUN_ID, VEHICLE_ID, "occupancy", {})

    mock_delay.assert_not_called()


def test_run_completed_not_redispatched_when_already_completed(monkeypatch):
    """A STOPPED_AT-at-terminal progression update for a run already
    COMPLETED must not re-fire run_completed."""
    monkeypatch.setattr(
        dispatch_module, "r", _fake_redis(RunLifecycleStates.COMPLETED.value)
    )

    with patch("realtime_engine.tasks.run_lifecycle_event.delay") as mock_delay:
        detect_from_telemetry(
            RUN_ID,
            VEHICLE_ID,
            "progression",
            {"current_status": "STOPPED_AT", "stop_id": "TERM-1"},
        )

    mock_delay.assert_not_called()


def test_scan_no_periodic_event_once_run_is_terminal(monkeypatch):
    """A stray staleness-scan tick for a run that already reached a terminal
    state (e.g. CANCELLED after expiry) must not fire any periodic event."""
    monkeypatch.setattr(
        dispatch_module, "r", _fake_redis(RunLifecycleStates.CANCELLED.value)
    )

    with patch("realtime_engine.tasks.run_lifecycle_event.delay") as mock_delay:
        fired = detect_from_scan(
            RUN_ID, staleness_s=9999, raw_last_seen="2026-01-01T00:00:00+00:00"
        )

    assert fired == 0
    mock_delay.assert_not_called()
