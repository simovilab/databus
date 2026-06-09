"""Pure unit tests for the MQTT telemetry ingestion path in mqtt.py.

No real Redis, no real MQTT broker, no Django ORM.  The module-level ``r``
object and the lazily-imported ``detect_from_telemetry`` are both monkeypatched
so each test runs entirely in-process without I/O.

Patch targets
-------------
- ``realtime_engine.mqtt.r``            — the Redis client used by _handle_telemetry.
- ``runs.domain.detection.dispatch.detect_from_telemetry``
                                        — the lazy import inside _handle_telemetry
                                          resolves via the module object, so patching
                                          the attribute on the module is the correct
                                          target (as the import statement is
                                          ``from runs.domain.detection.dispatch import
                                          detect_from_telemetry`` inside the function).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

import realtime_engine.mqtt as mqtt_module
from realtime_engine.mqtt import _handle_telemetry
from runs.domain.telemetry import keys, occupancy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VEHICLE_ID = "v-42"
RUN_ID = "run-99"

_VALID_POSITION = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "bearing": 90.0,
    "speed": 8.5,
    "timestamp": 1700000000,
}

_VALID_OCCUPANCY_WITH_PCT = {
    "occupancy_percentage": 90,
    "occupancy_count": 45,
    # edge-sent status — must be ignored / overwritten
    "occupancy_status": "BOGUS_EDGE_VALUE",
}

_VALID_OCCUPANCY_NO_PCT = {
    "occupancy_count": 10,
    # No occupancy_percentage key at all
}


_FAKE_NOW_ISO = "2026-06-08T12:00:00+00:00"


def _fake_redis(run_id: str = RUN_ID) -> MagicMock:
    """Return a Mock that impersonates redis.Redis with decode_responses=True."""
    r = MagicMock()
    r.get.return_value = run_id  # simulates r.get(current_run_key) → run_id
    return r


def _fake_now():
    """Replacement for django.utils.timezone.now — avoids needing Django settings."""
    m = MagicMock()
    m.isoformat.return_value = _FAKE_NOW_ISO
    return m


def _encode(data: dict) -> bytes:
    return json.dumps(data).encode()


# ---------------------------------------------------------------------------
# Test 1 — Valid position payload: hset called with typed contract mapping
# ---------------------------------------------------------------------------


def test_valid_position_writes_position_key(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)
    monkeypatch.setattr(mqtt_module, "now", _fake_now)

    with patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect:
        _handle_telemetry(VEHICLE_ID, "position", _encode(_VALID_POSITION))

    # Verify hset was called with the correct Redis key
    assert fake_r.hset.call_count == 1

    # Extract the mapping regardless of whether it was passed as kwarg or positional
    call_kwargs = fake_r.hset.call_args
    redis_key = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("name")
    mapping = call_kwargs.kwargs.get("mapping")

    assert redis_key == keys.position_key(VEHICLE_ID)

    # All values must be strings (Redis-ready)
    for v in mapping.values():
        assert isinstance(v, str), f"Expected str, got {type(v)} for value {v!r}"

    # Required fields present and round-trip correctly
    assert float(mapping["latitude"]) == pytest.approx(51.5074)
    assert float(mapping["longitude"]) == pytest.approx(-0.1278)
    assert float(mapping["bearing"]) == pytest.approx(90.0)

    # last_seen updated with the run's key
    fake_r.set.assert_called_once_with(keys.last_seen_key(RUN_ID), _FAKE_NOW_ISO)

    # detect_from_telemetry called with raw data
    mock_detect.assert_called_once_with(RUN_ID, VEHICLE_ID, "position", _VALID_POSITION)


# ---------------------------------------------------------------------------
# Test 2 — Occupancy with percentage: status is recomputed, not trusted from edge
# ---------------------------------------------------------------------------


def test_occupancy_with_percentage_rewrites_status(monkeypatch):
    """percentage=90 → FULL; edge-sent BOGUS_EDGE_VALUE must be overwritten."""
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)
    monkeypatch.setattr(mqtt_module, "now", _fake_now)

    with patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect:
        _handle_telemetry(VEHICLE_ID, "occupancy", _encode(_VALID_OCCUPANCY_WITH_PCT))

    assert fake_r.hset.call_count == 1
    call_kwargs = fake_r.hset.call_args
    redis_key = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("name")
    mapping = call_kwargs.kwargs.get("mapping")

    assert redis_key == keys.occupancy_key(VEHICLE_ID)

    # Status must be FULL (90 >= 80 threshold), NOT the bogus edge value
    assert mapping[occupancy.OCCUPANCY_STATUS] == "FULL"
    assert mapping[occupancy.OCCUPANCY_STATUS] != "BOGUS_EDGE_VALUE"

    # Numeric fields preserved as strings
    assert int(mapping[occupancy.OCCUPANCY_PERCENTAGE]) == 90
    assert int(mapping[occupancy.OCCUPANCY_COUNT]) == 45

    # detect called with raw data (including the original bogus status)
    mock_detect.assert_called_once_with(
        RUN_ID, VEHICLE_ID, "occupancy", _VALID_OCCUPANCY_WITH_PCT
    )


# ---------------------------------------------------------------------------
# Test 3 — Occupancy without percentage → NO_DATA_AVAILABLE
# ---------------------------------------------------------------------------


def test_occupancy_without_percentage_yields_no_data_available(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)
    monkeypatch.setattr(mqtt_module, "now", _fake_now)

    with patch("runs.domain.detection.dispatch.detect_from_telemetry"):
        _handle_telemetry(VEHICLE_ID, "occupancy", _encode(_VALID_OCCUPANCY_NO_PCT))

    mapping = fake_r.hset.call_args.kwargs.get("mapping")
    assert mapping[occupancy.OCCUPANCY_STATUS] == "NO_DATA_AVAILABLE"


# ---------------------------------------------------------------------------
# Test 4 — Malformed position (missing lat/lon): dropped, no side effects
# ---------------------------------------------------------------------------


def test_malformed_position_is_dropped_without_side_effects(monkeypatch):
    """A position payload missing lat/lon must be fully discarded.

    - No hset call.
    - No last_seen update (r.set not called).
    - detect_from_telemetry NOT called.
    - No exception propagates out.
    """
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)

    bad_payload = {"speed": 12.0, "bearing": 45.0}  # no latitude / longitude

    with patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect:
        # Must not raise
        _handle_telemetry(VEHICLE_ID, "position", _encode(bad_payload))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 — Unknown leaf: dropped (no hset, detect not called)
# ---------------------------------------------------------------------------


def test_unknown_leaf_is_dropped(monkeypatch):
    """Legacy 'progression' or any other unknown leaf must be silently dropped."""
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)

    progression_payload = {
        "current_status": "STOPPED_AT",
        "stop_id": "S99",
        "current_stop_sequence": 5,
    }

    with patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect:
        _handle_telemetry(VEHICLE_ID, "progression", _encode(progression_payload))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6 — No active run: nothing written, detect not called
# ---------------------------------------------------------------------------


def test_no_active_run_drops_all_telemetry(monkeypatch):
    """When r.get(current_run_key) returns falsy, all leaves are dropped."""
    fake_r = _fake_redis(run_id="")  # falsy empty string
    fake_r.get.return_value = None   # also covers None return
    monkeypatch.setattr(mqtt_module, "r", fake_r)

    with patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect:
        _handle_telemetry(VEHICLE_ID, "position", _encode(_VALID_POSITION))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7 — _on_connect subscribes to position and occupancy only (not progression)
# ---------------------------------------------------------------------------


def test_on_connect_subscribes_position_and_occupancy_only():
    """_on_connect must subscribe to exactly 'position' and 'occupancy'.

    'progression' must NOT be subscribed (decommissioned).
    """
    mock_client = MagicMock()
    mqtt_module._on_connect(mock_client, userdata=None, flags=None, rc=0)

    subscribed_topics = {c.args[0] for c in mock_client.subscribe.call_args_list}
    assert "transit/vehicle/+/position" in subscribed_topics
    assert "transit/vehicle/+/occupancy" in subscribed_topics
    assert "transit/vehicle/+/progression" not in subscribed_topics
