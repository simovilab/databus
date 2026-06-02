"""Pure unit tests for the dispatch *planner* (no Redis/Celery/Django).

The planner decides which events to fire given the current state and a message;
the impure wrapper that reads Redis and queues Celery tasks is covered by
integration tests in the compose stack.
"""

from runs.domain.detection import registry
from runs.domain.detection.dispatch import plan_telemetry_events, plan_scan_events
from runs.domain.detection import thresholds


def _events(results):
    return [(r.fsm, r.event) for r in results]


def test_registry_lists_are_populated_and_tagged():
    assert registry.TELEMETRY_DETECTORS
    assert registry.PERIODIC_DETECTORS
    for d in registry.TELEMETRY_DETECTORS + registry.PERIODIC_DETECTORS:
        assert d.fsm == "lifecycle"
        assert hasattr(d, "detect")


def test_plan_fires_at_most_one_lifecycle_event():
    data = {"current_status": "STOPPED_AT", "stop_id": "S9"}
    results = plan_telemetry_events(
        lifecycle_state="In Progress",
        leaf="progression",
        data=data,
        base_payload={},
        detectors=registry.TELEMETRY_DETECTORS,
    )
    events = _events(results)
    assert ("lifecycle", "complete_run") in events
    fsms = [fsm for fsm, _ in events]
    assert fsms.count("lifecycle") == 1


def test_plan_tracking_started_only():
    results = plan_telemetry_events(
        lifecycle_state="Confirmed",
        leaf="position",
        data={"speed": 0},
        base_payload={},
        detectors=registry.TELEMETRY_DETECTORS,
    )
    assert _events(results) == [("lifecycle", "run_tracking_started")]


def test_plan_scan_picks_single_lifecycle_event():
    results = plan_scan_events(
        lifecycle_state="In Progress",
        staleness_s=thresholds.TELEMETRY_GRACE_S + 5,
        payload={},
        detectors=registry.PERIODIC_DETECTORS,
    )
    assert _events(results) == [("lifecycle", "run_tracking_lost")]


def test_plan_scan_no_event_when_fresh():
    results = plan_scan_events(
        lifecycle_state="In Progress",
        staleness_s=1,
        payload={},
        detectors=registry.PERIODIC_DETECTORS,
    )
    assert results == []
