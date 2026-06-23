"""Unit tests for produce_stop_times — monkeypatched Redis, no I/O.

The module-level ``r`` object in stop_times.py is replaced with a MagicMock so
all tests run entirely in-process without a live Redis instance.

Patch target: ``runs.domain.progression.stop_times.r``
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import runs.domain.progression.stop_times as stop_times_module
from runs.domain.progression.stop_times import (
    STOP_TIME_UPDATES_TTL_S,
    produce_stop_times,
)
from runs.domain.telemetry import keys, stop_time_updates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VEHICLE_ID = "v-42"
RUN_ID = "run-99"

_RUN_RAW = {
    "trip_id": "trip-1",
    "route_id": "route-1",
    "shape_id": "shape-1",
    "vehicle": VEHICLE_ID,
}

_STOP_STATUS_RAW = {
    "current_stop_sequence": "3",
    "stop_id": "STOP-42",
    "current_status": "IN_TRANSIT_TO",
}

# Two fake entries that build_stop_time_updates might return
_FAKE_STOP_ENTRIES = [
    {
        "stop_sequence": 3,
        "stop_id": "stop-1",
        "eta_posix": 1700001000,
        "uncertainty": 120,
    },
    {
        "stop_sequence": 4,
        "stop_id": "stop-2",
        "eta_posix": 1700001300,
        "uncertainty": 120,
    },
]


def _fake_redis(run_raw=None, stop_status_raw=None) -> MagicMock:
    r = MagicMock()

    def hgetall_side_effect(key: str) -> dict:
        if key == keys.run_key(RUN_ID):
            return run_raw if run_raw is not None else _RUN_RAW
        if key == keys.stop_status_key(RUN_ID):
            return stop_status_raw if stop_status_raw is not None else {}
        return {}

    r.hgetall.side_effect = hgetall_side_effect
    return r


# ---------------------------------------------------------------------------
# Test 1 — Empty run hash: returns early, no r.set called
# ---------------------------------------------------------------------------


def test_returns_early_when_run_hash_is_empty(monkeypatch):
    fake_r = _fake_redis(run_raw={})
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    produce_stop_times(RUN_ID, VEHICLE_ID)

    fake_r.set.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2 — Happy path: maps fake entries to contract and writes JSON
# ---------------------------------------------------------------------------


def test_happy_path_writes_stop_time_updates_key(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    with patch(
        "schedule_engine.fake_stop_times.build_stop_time_updates",
        return_value=_FAKE_STOP_ENTRIES,
    ):
        produce_stop_times(RUN_ID, VEHICLE_ID)

    fake_r.set.assert_called_once()
    call_args = fake_r.set.call_args
    written_key = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
    assert written_key == keys.stop_time_updates_key(RUN_ID)


def test_happy_path_payload_is_valid_json(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    with patch(
        "schedule_engine.fake_stop_times.build_stop_time_updates",
        return_value=_FAKE_STOP_ENTRIES,
    ):
        produce_stop_times(RUN_ID, VEHICLE_ID)

    payload_str = fake_r.set.call_args.args[1]
    parsed = json.loads(payload_str)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_fake_to_contract_mapping(monkeypatch):
    """Each fake entry {eta_posix} must map to contract {arrival_time, departure_time}."""
    fake_r = _fake_redis()
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    with patch(
        "schedule_engine.fake_stop_times.build_stop_time_updates",
        return_value=_FAKE_STOP_ENTRIES,
    ):
        produce_stop_times(RUN_ID, VEHICLE_ID)

    payload_str = fake_r.set.call_args.args[1]
    entries = stop_time_updates.from_redis(payload_str)
    assert len(entries) == 2
    # Verify the eta_posix → arrival_time / departure_time mapping
    assert entries[0][stop_time_updates.ARRIVAL_TIME] == 1700001000
    assert entries[0][stop_time_updates.DEPARTURE_TIME] == 1700001000
    assert entries[0][stop_time_updates.STOP_SEQUENCE] == 3
    assert entries[0][stop_time_updates.STOP_ID] == "stop-1"
    assert entries[0][stop_time_updates.UNCERTAINTY] == 120


def test_writes_with_ttl(monkeypatch):
    """r.set must be called with ex=STOP_TIME_UPDATES_TTL_S."""
    fake_r = _fake_redis()
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    with patch(
        "schedule_engine.fake_stop_times.build_stop_time_updates",
        return_value=_FAKE_STOP_ENTRIES,
    ):
        produce_stop_times(RUN_ID, VEHICLE_ID)

    call_kwargs = fake_r.set.call_args.kwargs
    assert call_kwargs.get("ex") == STOP_TIME_UPDATES_TTL_S


# ---------------------------------------------------------------------------
# Test 3 — Empty fake entries: writes empty JSON array
# ---------------------------------------------------------------------------


def test_empty_fake_entries_writes_empty_array(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(stop_times_module, "r", fake_r)

    with patch(
        "schedule_engine.fake_stop_times.build_stop_time_updates",
        return_value=[],
    ):
        produce_stop_times(RUN_ID, VEHICLE_ID)

    fake_r.set.assert_called_once()
    payload_str = fake_r.set.call_args.args[1]
    assert json.loads(payload_str) == []


# ---------------------------------------------------------------------------
# Test 4 — TTL constant is 60
# ---------------------------------------------------------------------------


def test_ttl_constant_is_60():
    assert STOP_TIME_UPDATES_TTL_S == 60
