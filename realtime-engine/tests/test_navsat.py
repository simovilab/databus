"""
Tests for Navsat adapter — mapping and polling logic.

RED phase: these tests define the expected behavior before implementation exists.
"""
import pytest
from unittest.mock import MagicMock, patch

from adapters.navsat import (
    speed_kmh_to_ms,
    estado_to_gtfs_status,
    parse_timestamp,
    map_vehicle,
    NavsatAdapter,
)
from models import VehicleState


# ---------------------------------------------------------------------------
# Pure mapping functions
# ---------------------------------------------------------------------------


def test_speed_zero():
    assert speed_kmh_to_ms(0) == 0.0


def test_speed_36_kmh_is_10_ms():
    assert speed_kmh_to_ms(36) == pytest.approx(10.0, rel=1e-3)


def test_speed_17_kmh():
    assert speed_kmh_to_ms(17) == pytest.approx(17 / 3.6, rel=1e-3)


def test_estado_movimiento():
    assert estado_to_gtfs_status("movimiento") == "IN_TRANSIT_TO"


def test_estado_detenido():
    assert estado_to_gtfs_status("detenido") == "STOPPED_AT"


def test_estado_unknown_defaults_in_transit():
    assert estado_to_gtfs_status("unknown_value") == "IN_TRANSIT_TO"


def test_estado_empty_defaults_in_transit():
    assert estado_to_gtfs_status("") == "IN_TRANSIT_TO"


def test_parse_timestamp_returns_int():
    ts = parse_timestamp("2026-03-19 14:20:54")
    assert isinstance(ts, int)
    assert ts > 0


def test_parse_timestamp_costa_rica_offset():
    # America/Costa_Rica is UTC-6, no DST
    # 2026-03-19 14:20:54 CR = 2026-03-19 20:20:54 UTC = 1773951654
    ts = parse_timestamp("2026-03-19 14:20:54")
    assert ts == 1773951654


def test_map_vehicle_basic():
    raw = {
        "plateNumber": "299-604",
        "crDateTime": "2026-03-19 14:20:54",
        "latitude": 9.9471766,
        "longitude": -84.0458883,
        "odometer": 262655,
        "speed": 17,
        "estado": "movimiento",
    }
    v = map_vehicle(raw)
    assert isinstance(v, VehicleState)
    assert v.vehicle_id == "299-604"
    assert v.label == "299-604"
    assert v.license_plate == "299-604"
    assert v.latitude == 9.9471766
    assert v.longitude == -84.0458883
    assert v.speed_ms == pytest.approx(17 / 3.6, rel=1e-3)
    assert v.odometer == 262655
    assert v.timestamp == 1773951654
    assert v.current_status == "IN_TRANSIT_TO"


def test_map_vehicle_stopped():
    raw = {
        "plateNumber": "ABC-123",
        "crDateTime": "2026-03-19 08:00:00",
        "latitude": 9.93,
        "longitude": -84.05,
        "odometer": 1000,
        "speed": 0,
        "estado": "detenido",
    }
    v = map_vehicle(raw)
    assert v.current_status == "STOPPED_AT"
    assert v.speed_ms == 0.0


def test_map_vehicle_missing_optional_fields():
    raw = {
        "plateNumber": "XYZ-999",
        "crDateTime": "2026-03-19 10:00:00",
        "latitude": 9.9,
        "longitude": -84.0,
    }
    v = map_vehicle(raw)
    assert v.speed_ms == 0.0
    assert v.odometer == 0
    assert v.current_status == "IN_TRANSIT_TO"


# ---------------------------------------------------------------------------
# NavsatAdapter polling
# ---------------------------------------------------------------------------

SAMPLE_NAVSAT_RESPONSE = [
    {
        "plateNumber": "299-604",
        "deviceName": "299-604",
        "crDateTime": "2026-03-19 14:20:54",
        "latitude": 9.9471766,
        "longitude": -84.0458883,
        "odometer": 262655,
        "speed": 17,
        "lugar": "San José",
        "estado": "movimiento",
    },
    {
        "plateNumber": "300-100",
        "deviceName": "300-100",
        "crDateTime": "2026-03-19 14:21:00",
        "latitude": 9.94,
        "longitude": -84.04,
        "odometer": 50000,
        "speed": 0,
        "lugar": "UCR",
        "estado": "detenido",
    },
]


def test_adapter_poll_once_writes_all_vehicles():
    mock_redis = MagicMock()
    mock_redis.smembers.return_value = set()

    with patch("adapters.navsat.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_NAVSAT_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()

        adapter = NavsatAdapter(url="http://example.com/api", redis_client=mock_redis)
        adapter._poll_once()

    # hset called for both vehicles (data, position, progression = 3 calls each)
    assert mock_redis.hset.call_count == 6
    # sadd called for both vehicles
    assert mock_redis.sadd.call_count == 2


def test_adapter_poll_once_cleans_up_stale_runs():
    mock_redis = MagicMock()
    # Simulate a stale navsat run from a vehicle no longer in the feed
    mock_redis.smembers.return_value = {"run:navsat:OLD-111"}

    with patch("adapters.navsat.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = [SAMPLE_NAVSAT_RESPONSE[0]]
        mock_get.return_value.raise_for_status = MagicMock()

        adapter = NavsatAdapter(url="http://example.com/api", redis_client=mock_redis)
        adapter._poll_once()

    # OLD-111 should have been removed
    mock_redis.srem.assert_called_once_with("runs:in_progress", "run:navsat:OLD-111")
    mock_redis.delete.assert_called_once_with("run:navsat:OLD-111")


def test_adapter_start_stop():
    mock_redis = MagicMock()
    mock_redis.smembers.return_value = set()

    with patch("adapters.navsat.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = []
        mock_get.return_value.raise_for_status = MagicMock()

        adapter = NavsatAdapter(url="http://example.com/api", redis_client=mock_redis, poll_interval=0)
        adapter.start()
        import time
        time.sleep(0.05)
        adapter.stop()

    assert not adapter._running
