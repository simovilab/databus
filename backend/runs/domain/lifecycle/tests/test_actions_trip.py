"""Unit tests for the run:<id>:trip projection write in update_system_state.

The repo has no pytest-django harness; ``actions.py`` imports ``runs.models``
at module top, which needs a configured Django. To keep this an import-light
unit test (matching the convention in ``runs/domain/detection/tests``), we stub
``runs.models`` before importing the action and drive it with a fake Redis
pipeline that records ``hset`` calls. The projection logic itself
(``trip.project_from_run_hash``) is covered separately in
``runs/domain/telemetry/tests/test_trip.py``; here we assert the *action glue*:
that the trip subset is written to ``run:<id>:trip`` and skipped when empty.
"""

import sys
import types
from types import SimpleNamespace

import pytest

from runs.domain.telemetry import keys


@pytest.fixture
def actions_module(monkeypatch):
    """Import actions.py with runs.models stubbed and a recording fake Redis."""
    fake_models = types.ModuleType("runs.models")
    fake_models.Run = type("Run", (), {})
    monkeypatch.setitem(sys.modules, "runs.models", fake_models)

    # Import fresh so the stubbed runs.models is in effect.
    import importlib

    actions = importlib.import_module("runs.domain.lifecycle.actions")
    actions = importlib.reload(actions)

    monkeypatch.setattr(actions, "r", _FakeRedis())
    return actions


class _FakePipe:
    def __init__(self):
        self.hset_calls = []  # list[(key, mapping)]
        self.set_calls = []

    def hset(self, key, mapping=None, **kwargs):
        self.hset_calls.append((key, mapping))

    def set(self, key, value):
        self.set_calls.append((key, value))

    def execute(self):
        return []


class _FakeRedis:
    def __init__(self):
        self.pipe = _FakePipe()

    def pipeline(self):
        return self.pipe


def _make_run(*, trip_id, route_id, direction_id=0):
    """A run double exposing only what update_system_state touches."""
    empty_qs = SimpleNamespace(
        values_list=lambda *a, **k: SimpleNamespace(first=lambda: None)
    )
    return SimpleNamespace(
        id="run-123",
        route_id=route_id,
        trip_id=trip_id,
        direction_id=direction_id,
        shape_id="shape-1",
        schedule_relationship="SCHEDULED",
        start_date=None,
        start_time=None,
        vehicle=empty_qs,
        operator=empty_qs,
    )


def _transition():
    return SimpleNamespace(to_state=SimpleNamespace(value="IN_PROGRESS"))


def _trip_hsets(pipe):
    return [m for (k, m) in pipe.hset_calls if k == keys.trip_key("run-123")]


def test_writes_trip_projection_when_trip_present(actions_module):
    actions = actions_module
    run = _make_run(trip_id="T1", route_id="R1", direction_id=1)

    actions.RunLifecycleActions.update_system_state(run, _transition(), {})

    trip_writes = _trip_hsets(actions.r.pipe)
    assert len(trip_writes) == 1
    mapping = trip_writes[0]
    assert mapping == {
        "trip_id": "T1",
        "route_id": "R1",
        "direction_id": "1",
        "schedule_relationship": "SCHEDULED",
    }
    # Run-only fields must not leak into the trip projection.
    assert "shape_id" not in mapping
    assert "run_id" not in mapping
    assert "run_lifecycle_state" not in mapping


def test_skips_trip_write_when_no_trip(actions_module):
    actions = actions_module
    run = _make_run(trip_id=None, route_id=None)

    actions.RunLifecycleActions.update_system_state(run, _transition(), {})

    assert _trip_hsets(actions.r.pipe) == []
    # The flat run hash is still written regardless.
    assert any(k == "run:run-123" for (k, _m) in actions.r.pipe.hset_calls)
