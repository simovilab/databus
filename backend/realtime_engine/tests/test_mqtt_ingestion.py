"""Pure unit tests for the MQTT telemetry ingestion path in mqtt.py.

No real Redis, no real MQTT broker, no Django ORM.  The module-level ``r``
object and the lazily-imported domain functions are monkeypatched so each
test runs entirely in-process without I/O.

Patch targets
-------------
- ``realtime_engine.mqtt.r``            — the Redis client used by _handle_telemetry.
- ``realtime_engine.tasks.process_position_update``
                                        — the Celery task enqueued by the callback;
                                          ``.delay`` is asserted on the mock.
- ``runs.domain.detection.dispatch.detect_from_telemetry``
                                        — only still called inline for occupancy.

Architecture note: after the refactor, the position branch enqueues
``process_position_update.delay(run_id, vehicle_id)`` and returns; it no
longer calls ``produce_stop_status``, ``produce_stop_times``, or
``detect_from_telemetry`` inline.  Those calls now live in the task
(tested separately below).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import realtime_engine.mqtt as mqtt_module
import realtime_engine.tasks as tasks_module
from realtime_engine.mqtt import _handle_telemetry
from realtime_engine.tasks import process_position_update
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
# Test 1 — Valid position payload: hset called with typed contract mapping,
#           task enqueued, producers NOT called inline.
# ---------------------------------------------------------------------------


def test_valid_position_writes_position_key(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)
    monkeypatch.setattr(mqtt_module, "now", _fake_now)

    with patch("realtime_engine.tasks.process_position_update") as mock_task:
        mock_task.delay = MagicMock()
        _handle_telemetry(VEHICLE_ID, "position", _encode(_VALID_POSITION))

    # Verify hset was called with the correct Redis key
    assert fake_r.hset.call_count == 1

    # Extract the mapping regardless of whether it was passed as kwarg or positional
    call_kwargs = fake_r.hset.call_args
    redis_key = (
        call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("name")
    )
    mapping = call_kwargs.kwargs.get("mapping")

    assert redis_key == keys.position_key(VEHICLE_ID)

    # All values must be strings (Redis-ready)
    for v in mapping.values():
        assert isinstance(v, str), f"Expected str, got {type(v)} for value {v!r}"

    # Required fields present and round-trip correctly
    assert float(mapping["latitude"]) == pytest.approx(51.5074)
    assert float(mapping["longitude"]) == pytest.approx(-0.1278)
    assert float(mapping["bearing"]) == pytest.approx(90.0)

    # last_seen updated with the run's key (synchronous, not in the task)
    fake_r.set.assert_called_once_with(keys.last_seen_key(RUN_ID), _FAKE_NOW_ISO)

    # Task enqueued with correct args — heavy work is off the network thread
    mock_task.delay.assert_called_once_with(RUN_ID, VEHICLE_ID)


# ---------------------------------------------------------------------------
# Test 2 — Position callback does NOT call producers or detect inline
# ---------------------------------------------------------------------------


def test_valid_position_does_not_call_producers_or_detect_inline(monkeypatch):
    """The callback must enqueue the task and nothing more on the position branch.

    produce_stop_status, produce_stop_times, and detect_from_telemetry must NOT
    be called from the network-thread callback — they run inside the task.
    """
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)
    monkeypatch.setattr(mqtt_module, "now", _fake_now)

    with (
        patch("realtime_engine.tasks.process_position_update") as mock_task,
        patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect,
        patch("runs.domain.progression.producer.produce_stop_status") as mock_produce,
        patch("runs.domain.progression.stop_times.produce_stop_times") as mock_stop_times,
    ):
        mock_task.delay = MagicMock()
        _handle_telemetry(VEHICLE_ID, "position", _encode(_VALID_POSITION))

    mock_task.delay.assert_called_once_with(RUN_ID, VEHICLE_ID)
    mock_detect.assert_not_called()
    mock_produce.assert_not_called()
    mock_stop_times.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3 — Occupancy with percentage: status is recomputed, not trusted from edge
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
    redis_key = (
        call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("name")
    )
    mapping = call_kwargs.kwargs.get("mapping")

    assert redis_key == keys.occupancy_key(VEHICLE_ID)

    # Status must be FULL (90 >= 80 threshold), NOT the bogus edge value
    assert mapping[occupancy.OCCUPANCY_STATUS] == "FULL"
    assert mapping[occupancy.OCCUPANCY_STATUS] != "BOGUS_EDGE_VALUE"

    # Numeric fields preserved as strings
    assert int(mapping[occupancy.OCCUPANCY_PERCENTAGE]) == 90
    assert int(mapping[occupancy.OCCUPANCY_COUNT]) == 45

    # detect called inline for occupancy (RunTrackingStartedDetector /
    # RunTrackingRestoredDetector both match any leaf, so occupancy must still
    # go through detection inline).
    mock_detect.assert_called_once_with(
        RUN_ID, VEHICLE_ID, "occupancy", _VALID_OCCUPANCY_WITH_PCT
    )


# ---------------------------------------------------------------------------
# Test 4 — Occupancy without percentage → NO_DATA_AVAILABLE
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
# Test 5 — Malformed position (missing lat/lon): dropped, no side effects
# ---------------------------------------------------------------------------


def test_malformed_position_is_dropped_without_side_effects(monkeypatch):
    """A position payload missing lat/lon must be fully discarded.

    - No hset call.
    - No last_seen update (r.set not called).
    - process_position_update.delay NOT called.
    - No exception propagates out.
    """
    fake_r = _fake_redis()
    monkeypatch.setattr(mqtt_module, "r", fake_r)

    bad_payload = {"speed": 12.0, "bearing": 45.0}  # no latitude / longitude

    with patch("realtime_engine.tasks.process_position_update") as mock_task:
        mock_task.delay = MagicMock()
        # Must not raise
        _handle_telemetry(VEHICLE_ID, "position", _encode(bad_payload))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6 — Unknown leaf: dropped (no hset, no task, no detect)
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

    with (
        patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect,
        patch("realtime_engine.tasks.process_position_update") as mock_task,
    ):
        mock_task.delay = MagicMock()
        _handle_telemetry(VEHICLE_ID, "progression", _encode(progression_payload))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_detect.assert_not_called()
    mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7 — No active run: nothing written, task not enqueued
# ---------------------------------------------------------------------------


def test_no_active_run_drops_all_telemetry(monkeypatch):
    """When r.get(current_run_key) returns falsy, all leaves are dropped."""
    fake_r = _fake_redis(run_id="")  # falsy empty string
    fake_r.get.return_value = None  # also covers None return
    monkeypatch.setattr(mqtt_module, "r", fake_r)

    with (
        patch("runs.domain.detection.dispatch.detect_from_telemetry") as mock_detect,
        patch("realtime_engine.tasks.process_position_update") as mock_task,
    ):
        mock_task.delay = MagicMock()
        _handle_telemetry(VEHICLE_ID, "position", _encode(_VALID_POSITION))

    fake_r.hset.assert_not_called()
    fake_r.set.assert_not_called()
    mock_detect.assert_not_called()
    mock_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Test 8 — _on_connect subscribes to position and occupancy only (not progression)
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


# ---------------------------------------------------------------------------
# Task-level tests for process_position_update
# ---------------------------------------------------------------------------


_POSITION_RAW_REDIS = {
    "latitude": "51.5074",
    "longitude": "-0.1278",
    "bearing": "90.0",
    "speed": "8.5",
    "timestamp": "1700000000",
}

_STOPPED_AT_STATUS = {
    "current_status": "STOPPED_AT",
    "stop_id": "TERM-1",
    "current_stop_sequence": 10,
}


def _fake_task_redis(position_raw: dict | None = None) -> MagicMock:
    """Redis mock for task tests: hgetall returns position hash."""
    r = MagicMock()
    r.hgetall.return_value = position_raw if position_raw is not None else _POSITION_RAW_REDIS
    return r


# ---------------------------------------------------------------------------
# Task test 1 — Happy path: producer + detection called in correct order
# ---------------------------------------------------------------------------


def test_task_calls_producers_and_detectors_in_order(monkeypatch):
    """process_position_update must call produce_stop_status, then
    detect_from_telemetry(progression), then produce_stop_times, then
    detect_from_telemetry(position) — in that order.
    """
    fake_r = _fake_task_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    call_log = []

    def mock_produce_stop_status(run_id, vehicle_id):
        call_log.append("produce_stop_status")
        return _STOPPED_AT_STATUS

    def mock_detect(run_id, vehicle_id, leaf, data):
        call_log.append(f"detect:{leaf}")

    def mock_produce_stop_times(run_id, vehicle_id):
        call_log.append("produce_stop_times")

    with (
        patch("runs.domain.progression.producer.produce_stop_status", side_effect=mock_produce_stop_status),
        patch("runs.domain.detection.dispatch.detect_from_telemetry", side_effect=mock_detect),
        patch("runs.domain.progression.stop_times.produce_stop_times", side_effect=mock_produce_stop_times),
    ):
        process_position_update(RUN_ID, VEHICLE_ID)

    assert call_log == [
        "produce_stop_status",
        "detect:progression",
        "produce_stop_times",
        "detect:position",
    ]


# ---------------------------------------------------------------------------
# Task test 2 — None stop status skips progression detection
# ---------------------------------------------------------------------------


def test_task_skips_progression_detection_when_stop_status_is_none(monkeypatch):
    """When produce_stop_status returns None, detect_from_telemetry must NOT
    be called with leaf='progression'.
    """
    fake_r = _fake_task_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    detect_calls = []

    with (
        patch("runs.domain.progression.producer.produce_stop_status", return_value=None),
        patch(
            "runs.domain.detection.dispatch.detect_from_telemetry",
            side_effect=lambda run_id, vehicle_id, leaf, data: detect_calls.append(leaf),
        ),
        patch("runs.domain.progression.stop_times.produce_stop_times"),
    ):
        process_position_update(RUN_ID, VEHICLE_ID)

    assert "progression" not in detect_calls
    assert "position" in detect_calls


# ---------------------------------------------------------------------------
# Task test 3 — Empty position hash skips position detection
# ---------------------------------------------------------------------------


def test_task_skips_position_detection_when_position_hash_empty(monkeypatch):
    """When hgetall returns an empty dict, position detection must be skipped."""
    fake_r = _fake_task_redis(position_raw={})
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    detect_calls = []

    with (
        patch("runs.domain.progression.producer.produce_stop_status", return_value=None),
        patch(
            "runs.domain.detection.dispatch.detect_from_telemetry",
            side_effect=lambda run_id, vehicle_id, leaf, data: detect_calls.append(leaf),
        ),
        patch("runs.domain.progression.stop_times.produce_stop_times"),
    ):
        process_position_update(RUN_ID, VEHICLE_ID)

    assert "position" not in detect_calls


# ---------------------------------------------------------------------------
# Task test 4 — Producer exception is swallowed; remaining steps still execute
# ---------------------------------------------------------------------------


def test_task_producer_exception_does_not_propagate(monkeypatch):
    """A failure in produce_stop_status must be swallowed — the task continues
    and must not raise out of the task function.
    """
    fake_r = _fake_task_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    with (
        patch("runs.domain.progression.producer.produce_stop_status", side_effect=RuntimeError("boom")),
        patch("runs.domain.detection.dispatch.detect_from_telemetry"),
        patch("runs.domain.progression.stop_times.produce_stop_times"),
    ):
        # Must not raise
        process_position_update(RUN_ID, VEHICLE_ID)


# ---------------------------------------------------------------------------
# Task test 5 — speed survives the position round-trip for RunStartedDetector
# ---------------------------------------------------------------------------


def test_task_position_detection_receives_speed_from_redis(monkeypatch):
    """speed must survive validate_for_write → HSET → hgetall → from_redis so
    that RunStartedDetector's float(data.get("speed", 0) or 0) still works.

    The raw Redis hash stores speed as "8.5" (string); from_redis coerces it
    to float 8.5. detect_from_telemetry must receive a dict with speed as a
    float (or coercible value) so the detector fires correctly.
    """
    fake_r = _fake_task_redis()  # _POSITION_RAW_REDIS has speed="8.5"
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    received_data = {}

    def capture_detect(run_id, vehicle_id, leaf, data):
        if leaf == "position":
            received_data.update(data)

    with (
        patch("runs.domain.progression.producer.produce_stop_status", return_value=None),
        patch("runs.domain.detection.dispatch.detect_from_telemetry", side_effect=capture_detect),
        patch("runs.domain.progression.stop_times.produce_stop_times"),
    ):
        process_position_update(RUN_ID, VEHICLE_ID)

    assert "speed" in received_data
    # Must be coercible to float — RunStartedDetector uses float(data.get("speed", 0) or 0)
    assert float(received_data["speed"]) == pytest.approx(8.5)
