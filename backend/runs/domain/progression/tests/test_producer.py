"""Unit tests for produce_stop_status — monkeypatched Redis, no I/O.

The module-level ``r`` object in producer.py is replaced with a fake Redis
so all tests run entirely in-process.

Patch target: ``runs.domain.progression.producer.r``
"""

from unittest.mock import MagicMock, call

import pytest

import runs.domain.progression.producer as producer_module
from runs.domain.progression.producer import produce_stop_status
from runs.domain.telemetry import keys, vehicle_stop_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VEHICLE_ID = "v-42"
RUN_ID = "run-99"

_POSITION_RAW = {
    "latitude": "51.5074",
    "longitude": "-0.1278",
    "bearing": "90.0",
    "speed": "8.5",
    "timestamp": "1700000000",
}

_RUN_RAW = {
    "trip_id": "trip-1",
    "route_id": "route-1",
    "shape_id": "shape-1",
}

_PREV_RAW = {
    "current_stop_sequence": "5",
    "stop_id": "STOP-42",
    "current_status": "IN_TRANSIT_TO",
}


def _fake_redis(
    position_raw: dict | None = None,
    run_raw: dict | None = None,
    prev_raw: dict | None = None,
) -> MagicMock:
    """Return a Mock redis client whose hgetall returns canned hashes."""
    r = MagicMock()

    def hgetall_side_effect(key: str) -> dict:
        if key == keys.position_key(VEHICLE_ID):
            return position_raw if position_raw is not None else _POSITION_RAW
        if key == keys.run_key(RUN_ID):
            return run_raw if run_raw is not None else _RUN_RAW
        if key == keys.stop_status_key(RUN_ID):
            return prev_raw if prev_raw is not None else {}
        return {}

    r.hgetall.side_effect = hgetall_side_effect
    return r


# ---------------------------------------------------------------------------
# Test 1 — Happy path: writes stop_status_key with IN_TRANSIT_TO
# ---------------------------------------------------------------------------


def test_produces_stop_status_for_valid_position(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(producer_module, "r", fake_r)

    produce_stop_status(RUN_ID, VEHICLE_ID)

    fake_r.hset.assert_called_once()
    call_args = fake_r.hset.call_args
    written_key = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
    mapping = call_args.kwargs.get("mapping")

    assert written_key == keys.stop_status_key(RUN_ID)
    assert mapping[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"

    # All values must be strings (Redis-ready)
    for v in mapping.values():
        assert isinstance(v, str), f"Expected str, got {type(v)!r} for {v!r}"


# ---------------------------------------------------------------------------
# Test 2 — Empty position hash: returns early, no hset, returns None
# ---------------------------------------------------------------------------


def test_returns_early_when_position_hash_is_empty(monkeypatch):
    fake_r = _fake_redis(position_raw={})
    monkeypatch.setattr(producer_module, "r", fake_r)

    result = produce_stop_status(RUN_ID, VEHICLE_ID)

    fake_r.hset.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# Test 3 — prev_state with sequence and stop_id: carried into written mapping
# ---------------------------------------------------------------------------


def test_carries_prev_sequence_and_stop_id_into_written_mapping(monkeypatch):
    fake_r = _fake_redis(prev_raw=_PREV_RAW)
    monkeypatch.setattr(producer_module, "r", fake_r)

    produce_stop_status(RUN_ID, VEHICLE_ID)

    fake_r.hset.assert_called_once()
    mapping = fake_r.hset.call_args.kwargs.get("mapping")

    assert mapping[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert mapping[vehicle_stop_status.CURRENT_STOP_SEQUENCE] == "5"
    assert mapping[vehicle_stop_status.STOP_ID] == "STOP-42"


# ---------------------------------------------------------------------------
# Test 4 — No prev stop-status in Redis: still writes with just IN_TRANSIT_TO
# ---------------------------------------------------------------------------


def test_writes_without_prev_state_when_stop_status_key_is_empty(monkeypatch):
    fake_r = _fake_redis(prev_raw={})
    monkeypatch.setattr(producer_module, "r", fake_r)

    produce_stop_status(RUN_ID, VEHICLE_ID)

    fake_r.hset.assert_called_once()
    mapping = fake_r.hset.call_args.kwargs.get("mapping")

    assert mapping[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert vehicle_stop_status.CURRENT_STOP_SEQUENCE not in mapping
    assert vehicle_stop_status.STOP_ID not in mapping


# ---------------------------------------------------------------------------
# Test 5 — Correct Redis keys are read and written
# ---------------------------------------------------------------------------


def test_reads_and_writes_correct_redis_keys(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(producer_module, "r", fake_r)

    produce_stop_status(RUN_ID, VEHICLE_ID)

    read_keys = {c.args[0] for c in fake_r.hgetall.call_args_list}
    assert keys.position_key(VEHICLE_ID) in read_keys
    assert keys.run_key(RUN_ID) in read_keys
    assert keys.stop_status_key(RUN_ID) in read_keys

    written_key = (
        fake_r.hset.call_args.args[0]
        if fake_r.hset.call_args.args
        else fake_r.hset.call_args.kwargs.get("name")
    )
    assert written_key == keys.stop_status_key(RUN_ID)


# ---------------------------------------------------------------------------
# Test 6 — Returns computed dict (typed, not stringified) when position exists
# ---------------------------------------------------------------------------


def test_returns_computed_dict_when_position_exists(monkeypatch):
    """produce_stop_status must return the typed computed dict (not None, not
    the stringified Redis mapping) when position data is available.

    The returned dict must carry at minimum ``current_status`` as a string,
    suitable for passing directly to detect_from_telemetry as the
    ``leaf="progression"`` data payload (RunCompletedDetector contract).
    """
    fake_r = _fake_redis()
    monkeypatch.setattr(producer_module, "r", fake_r)

    result = produce_stop_status(RUN_ID, VEHICLE_ID)

    assert result is not None
    assert isinstance(result, dict)
    assert vehicle_stop_status.CURRENT_STATUS in result
    # current_status must be a plain string value (not a Redis-stringified mapping)
    assert isinstance(result[vehicle_stop_status.CURRENT_STATUS], str)


def test_returns_none_when_no_position_data(monkeypatch):
    """produce_stop_status must return None when no position hash exists in Redis."""
    fake_r = _fake_redis(position_raw={})
    monkeypatch.setattr(producer_module, "r", fake_r)

    result = produce_stop_status(RUN_ID, VEHICLE_ID)

    assert result is None
