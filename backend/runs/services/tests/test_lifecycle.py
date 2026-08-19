"""Unit tests for RunLifecycleService._publish_run_lifecycle_transition.

No database access: a bare `RunLifecycleService()` only builds a
`TransitionRegistry` in `__init__`, and `_publish_run_lifecycle_transition`
only reads attributes off `run`/`transition`/`payload` before delegating to
`messages.publisher.publish_event`, which is monkeypatched here. Real
`Transition`/`RunLifecycleEvents`/`RunLifecycleStates` domain objects are
used (they carry no DB dependency); `run` is a lightweight fake standing in
for a `Run` model instance.
"""

from unittest.mock import MagicMock

from runs.domain.lifecycle import RunLifecycleEvents, RunLifecycleStates, Transition
from runs.services.lifecycle import RunLifecycleService


class _FakeVehicleManager:
    """Stands in for Run.vehicle (a ManyToManyField manager)."""

    def __init__(self, vehicle_ids):
        self._vehicle_ids = list(vehicle_ids)

    def values_list(self, *args, **kwargs):
        return self

    def first(self):
        return self._vehicle_ids[0] if self._vehicle_ids else None


class _FakeRun:
    def __init__(self, run_id="run-1", trip_id=None, route_id=None, vehicle_ids=()):
        self.id = run_id
        self.trip_id = trip_id
        self.route_id = route_id
        self.vehicle = _FakeVehicleManager(vehicle_ids)


def _transition(event=RunLifecycleEvents.RUN_CONFIRMED_BY_OPERATOR):
    return Transition(
        from_state=RunLifecycleStates.INITIALIZED,
        event=event,
        to_state=RunLifecycleStates.CONFIRMED,
        guards=[],
        actions=[],
    )


def _service() -> RunLifecycleService:
    return RunLifecycleService()


def test_publish_composes_event_and_states(monkeypatch):
    mock_publish = MagicMock()
    monkeypatch.setattr("runs.services.lifecycle.publish_event", mock_publish)

    run = _FakeRun(run_id="run-1")
    transition = _transition()

    _service()._publish_run_lifecycle_transition(run, transition, {})

    mock_publish.assert_called_once_with(
        event="run_confirmed_by_operator",
        run_id="run-1",
        from_state=RunLifecycleStates.INITIALIZED.value,
        to_state=RunLifecycleStates.CONFIRMED.value,
        data={},
    )


def test_publish_includes_trip_and_route_ids_when_present(monkeypatch):
    mock_publish = MagicMock()
    monkeypatch.setattr("runs.services.lifecycle.publish_event", mock_publish)

    run = _FakeRun(run_id="run-1", trip_id="T1", route_id="R1")
    transition = _transition()

    _service()._publish_run_lifecycle_transition(run, transition, {})

    _, kwargs = mock_publish.call_args
    assert kwargs["data"] == {"trip_id": "T1", "route_id": "R1"}


def test_publish_falls_back_to_run_vehicle_when_payload_has_no_vehicle_id(monkeypatch):
    mock_publish = MagicMock()
    monkeypatch.setattr("runs.services.lifecycle.publish_event", mock_publish)

    run = _FakeRun(run_id="run-1", vehicle_ids=["veh-9"])
    transition = _transition()

    _service()._publish_run_lifecycle_transition(run, transition, {})

    _, kwargs = mock_publish.call_args
    assert kwargs["data"]["vehicle_id"] == "veh-9"


def test_publish_prefers_payload_vehicle_id_over_run_vehicle(monkeypatch):
    mock_publish = MagicMock()
    monkeypatch.setattr("runs.services.lifecycle.publish_event", mock_publish)

    run = _FakeRun(run_id="run-1", vehicle_ids=["veh-9"])
    transition = _transition()

    _service()._publish_run_lifecycle_transition(
        run, transition, {"vehicle_id": "veh-override"}
    )

    _, kwargs = mock_publish.call_args
    assert kwargs["data"]["vehicle_id"] == "veh-override"


def test_publish_omits_absent_fields(monkeypatch):
    mock_publish = MagicMock()
    monkeypatch.setattr("runs.services.lifecycle.publish_event", mock_publish)

    run = _FakeRun(run_id="run-1")
    transition = _transition()

    _service()._publish_run_lifecycle_transition(run, transition, {})

    _, kwargs = mock_publish.call_args
    assert "vehicle_id" not in kwargs["data"]
    assert "trip_id" not in kwargs["data"]
    assert "route_id" not in kwargs["data"]
