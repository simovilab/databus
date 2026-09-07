"""Unit tests for the generic HTTP+JSON source adapter (kind="http").

No real HTTP, no Django ORM: ``requests.get`` is monkeypatched to return a
fake response, and the "sensor" is a lightweight ``SimpleNamespace`` rather
than the real Django model — this adapter only ever touches
``sensor.source_http_url``, ``sensor.source_json_mapping``, and (as a
fallback) ``sensor.equipment.vehicle_id``, all accessed structurally.
"""

from types import SimpleNamespace

import pytest

from realtime_engine.sources import http_json
from runs.domain.telemetry import position

NAVSAT_MAPPING = {
    "type": "array",
    "paths": {
        "vehicle_id": "plateNumber",
        "timestamp": "crDateTime",
        "lat": "latitude",
        "lon": "longitude",
        "speed": "speed",
        "odometer": "odometer",
    },
    "units": {"speed": "kmh", "odometer": "km"},
    "timestamp": {"format": "%Y-%m-%d %H:%M:%S", "tz": "America/Costa_Rica"},
}

SAMPLE_RECORD = {
    "plateNumber": "299-1014",
    "crDateTime": "2026-07-21 14:19:19",
    "latitude": 9.9355516,
    "longitude": -84.0490749,
    "odometer": 114879,
    "speed": 0,
}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _make_sensor(mapping=NAVSAT_MAPPING, url="http://navsat.example/positions", vehicle_id="fallback-veh"):
    return SimpleNamespace(
        source_http_url=url,
        source_json_mapping=mapping,
        equipment=SimpleNamespace(vehicle_id=vehicle_id),
    )


# ---------------------------------------------------------------------------
# Array handling, multiple records
# ---------------------------------------------------------------------------


def test_fetch_array_with_multiple_records(monkeypatch):
    second_record = {**SAMPLE_RECORD, "plateNumber": "299-2020", "speed": 36}

    def fake_get(url, timeout):
        return FakeResponse([SAMPLE_RECORD, second_record])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor()
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert len(results) == 2
    vehicle_ids = {vid for vid, _ in results}
    assert vehicle_ids == {"299-1014", "299-2020"}


# ---------------------------------------------------------------------------
# Single-object (non-array) handling
# ---------------------------------------------------------------------------


def test_fetch_single_object_body(monkeypatch):
    mapping = {**NAVSAT_MAPPING, "type": "object"}

    def fake_get(url, timeout):
        return FakeResponse(SAMPLE_RECORD)

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor(mapping=mapping)
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert len(results) == 1
    vehicle_id, payload = results[0]
    assert vehicle_id == "299-1014"
    assert payload["latitude"] == pytest.approx(9.9355516)
    assert payload["longitude"] == pytest.approx(-84.0490749)


# ---------------------------------------------------------------------------
# Field extraction + unit conversion
# ---------------------------------------------------------------------------


def test_fetch_converts_units_correctly(monkeypatch):
    record = {**SAMPLE_RECORD, "speed": 36, "odometer": 112}

    def fake_get(url, timeout):
        return FakeResponse([record])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor()
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert len(results) == 1
    _, payload = results[0]
    assert payload["speed"] == pytest.approx(10.0)  # 36 km/h -> 10.0 m/s
    assert payload["odometer"] == pytest.approx(112_000.0)  # 112 km -> 112000 m
    assert isinstance(payload["timestamp"], int)
    assert payload["timestamp"] > 0


# ---------------------------------------------------------------------------
# Malformed record skipped without killing the batch
# ---------------------------------------------------------------------------


def test_fetch_skips_malformed_record_without_failing_batch(monkeypatch):
    good_record = SAMPLE_RECORD
    missing_latlon = {"plateNumber": "BAD-1", "crDateTime": "2026-07-21 14:19:19"}
    bad_timestamp = {**SAMPLE_RECORD, "plateNumber": "BAD-2", "crDateTime": "not-a-date"}
    non_dict_record = "this is not a record"

    def fake_get(url, timeout):
        return FakeResponse([good_record, missing_latlon, bad_timestamp, non_dict_record])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor()
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    vehicle_ids = {vid for vid, _ in results}
    # missing_latlon is dropped entirely (no lat/lon).
    assert "BAD-1" not in vehicle_ids
    # bad_timestamp keeps its lat/lon; only the timestamp field is omitted.
    assert "BAD-2" in vehicle_ids
    bad_ts_payload = next(p for vid, p in results if vid == "BAD-2")
    assert "timestamp" not in bad_ts_payload
    # The good record still comes through.
    assert good_record["plateNumber"] in vehicle_ids


def test_fetch_http_error_returns_empty_list(monkeypatch):
    def fake_get(url, timeout):
        raise ConnectionError("boom")

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor()
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert results == []


# ---------------------------------------------------------------------------
# vehicle_id resolution: mapped path vs. sensor fallback
# ---------------------------------------------------------------------------


def test_fetch_uses_vehicle_id_from_mapped_path(monkeypatch):
    def fake_get(url, timeout):
        return FakeResponse([SAMPLE_RECORD])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor(vehicle_id="should-not-be-used")
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    vehicle_id, _ = results[0]
    assert vehicle_id == "299-1014"


def test_fetch_falls_back_to_sensor_equipment_vehicle_id_when_no_mapping(monkeypatch):
    mapping = {**NAVSAT_MAPPING, "paths": {k: v for k, v in NAVSAT_MAPPING["paths"].items() if k != "vehicle_id"}}

    def fake_get(url, timeout):
        return FakeResponse([SAMPLE_RECORD])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor(mapping=mapping, vehicle_id="fallback-veh-123")
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    vehicle_id, _ = results[0]
    assert vehicle_id == "fallback-veh-123"


# ---------------------------------------------------------------------------
# Nullable Sensor fields: guarded explicitly rather than falling through to
# the generic try/except.
# ---------------------------------------------------------------------------


def test_fetch_skips_sensor_with_no_source_http_url(monkeypatch):
    def fake_get(url, timeout):
        raise AssertionError("requests.get should not be called for a None URL")

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor(url=None)
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert results == []


def test_fetch_skips_record_when_fallback_vehicle_id_has_no_equipment(monkeypatch):
    mapping = {**NAVSAT_MAPPING, "paths": {k: v for k, v in NAVSAT_MAPPING["paths"].items() if k != "vehicle_id"}}

    def fake_get(url, timeout):
        return FakeResponse([SAMPLE_RECORD])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor(mapping=mapping)
    sensor.equipment = None
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    assert results == []


# ---------------------------------------------------------------------------
# Contract compliance: produced payloads must pass position.validate_for_write
# ---------------------------------------------------------------------------


def test_fetch_produces_payloads_valid_for_position_contract(monkeypatch):
    record = {**SAMPLE_RECORD, "speed": 36, "odometer": 112}

    def fake_get(url, timeout):
        return FakeResponse([record])

    monkeypatch.setattr(http_json.requests, "get", fake_get)

    sensor = _make_sensor()
    results = http_json.HttpJsonSourceAdapter().fetch(sensor)

    _, payload = results[0]
    # Must not raise -- validates required lat/lon and coercible optionals.
    mapping = position.validate_for_write(payload)
    assert "latitude" in mapping
    assert "longitude" in mapping
