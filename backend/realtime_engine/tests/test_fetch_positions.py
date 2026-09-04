"""Unit tests for realtime_engine.tasks.fetch_positions.

No live database and no real MQTT broker: ``Sensor.objects`` is monkeypatched
to return fake ``SimpleNamespace`` sensors (never touching Postgres), the
adapter registry (``realtime_engine.sources.get_adapter``) and the publisher
(``realtime_engine.sources.publisher.MqttPublisher``) are monkeypatched, and
the module-level ``redis_client`` is replaced with a ``MagicMock`` — matching
the same patch targets already used by ``test_mqtt_ingestion.py`` for this
module.

Importing ``realtime_engine.tasks`` pulls in the full Django app registry
(pre-existing, via ``runs.services.lifecycle.RunLifecycleService`` at module
scope) so this file needs ``DEBUG`` and ``DJANGO_SETTINGS_MODULE`` set, same
as ``test_mqtt_ingestion.py`` in this same directory -- run it with e.g.
``DEBUG=True DJANGO_SETTINGS_MODULE=databus.settings uv run pytest
realtime_engine/tests/test_fetch_positions.py``. No test here ever queries a
real database.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from celery.exceptions import SoftTimeLimitExceeded

from operations.models import Sensor

import realtime_engine.sources as sources_module
import realtime_engine.sources.publisher as publisher_module
import realtime_engine.tasks as tasks_module
from realtime_engine.tasks import fetch_positions
from runs.domain.telemetry import keys

IN_SERVICE_VEHICLE_ID = "veh-in-service"
OUT_OF_SERVICE_VEHICLE_ID = "veh-out-of-service"


def _make_sensor(sensor_id="sensor-1"):
    return SimpleNamespace(
        id=sensor_id,
        source_http_url="http://example.test/positions",
        source_json_mapping={},
        equipment=SimpleNamespace(vehicle_id=IN_SERVICE_VEHICLE_ID),
    )


def _fake_redis(in_service=(IN_SERVICE_VEHICLE_ID,)) -> MagicMock:
    """Redis mock: ``scan_iter`` over ``vehicle:*:current_run`` yields one key
    per in-service vehicle -- the same ``current_run`` gate the task uses."""
    r = MagicMock()
    r.scan_iter.return_value = [keys.current_run_key(vid) for vid in in_service]
    return r


def _fake_sensor_manager(sensors):
    """A MagicMock standing in for Sensor.objects supporting filter().select_related()."""
    manager = MagicMock()
    manager.filter.return_value.select_related.return_value = sensors
    return manager


# ---------------------------------------------------------------------------
# Only in-service vehicles get published; out-of-service readings are dropped
# ---------------------------------------------------------------------------


def test_fetch_positions_filters_out_of_service_vehicles(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    sensor = _make_sensor()
    monkeypatch.setattr(Sensor, "objects", _fake_sensor_manager([sensor]))

    fake_adapter = MagicMock()
    fake_adapter.fetch.return_value = [
        (IN_SERVICE_VEHICLE_ID, {"latitude": 1.0, "longitude": 2.0}),
        (OUT_OF_SERVICE_VEHICLE_ID, {"latitude": 3.0, "longitude": 4.0}),
    ]
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(
        publisher_module, "MqttPublisher", lambda: fake_publisher
    )

    result = fetch_positions()

    fake_publisher.publish_batch.assert_called_once()
    (published_records,), _ = fake_publisher.publish_batch.call_args
    published_vehicle_ids = {vid for vid, _ in published_records}
    assert published_vehicle_ids == {IN_SERVICE_VEHICLE_ID}
    assert "published 1" in result


def test_fetch_positions_skips_publish_when_no_in_service_readings(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    sensor = _make_sensor()
    monkeypatch.setattr(Sensor, "objects", _fake_sensor_manager([sensor]))

    fake_adapter = MagicMock()
    fake_adapter.fetch.return_value = [
        (OUT_OF_SERVICE_VEHICLE_ID, {"latitude": 3.0, "longitude": 4.0}),
    ]
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(
        publisher_module, "MqttPublisher", lambda: fake_publisher
    )

    result = fetch_positions()

    fake_publisher.publish_batch.assert_not_called()
    assert "published 0" in result


# ---------------------------------------------------------------------------
# A raising source is isolated -- the task still succeeds and other sensors'
# readings still get published.
# ---------------------------------------------------------------------------


def test_fetch_positions_isolates_a_raising_sensor(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    good_sensor = _make_sensor(sensor_id="sensor-good")
    bad_sensor = _make_sensor(sensor_id="sensor-bad")
    monkeypatch.setattr(
        Sensor, "objects", _fake_sensor_manager([bad_sensor, good_sensor])
    )

    fake_adapter = MagicMock()

    def _fetch(sensor):
        if sensor.id == "sensor-bad":
            raise ConnectionError("upstream is down")
        return [(IN_SERVICE_VEHICLE_ID, {"latitude": 1.0, "longitude": 2.0})]

    fake_adapter.fetch.side_effect = _fetch
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(
        publisher_module, "MqttPublisher", lambda: fake_publisher
    )

    # Must not raise even though one sensor's fetch blows up.
    result = fetch_positions()

    fake_publisher.publish_batch.assert_called_once()
    (published_records,), _ = fake_publisher.publish_batch.call_args
    assert [vid for vid, _ in published_records] == [IN_SERVICE_VEHICLE_ID]
    assert "polled 2 sensors" in result
    assert "1 failures" in result


def test_fetch_positions_queries_only_active_http_position_sensors(monkeypatch):
    """Sanity-check the filter kwargs passed to Sensor.objects.filter."""
    fake_r = _fake_redis(in_service=())
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    manager = _fake_sensor_manager([])
    monkeypatch.setattr(Sensor, "objects", manager)
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: MagicMock())
    monkeypatch.setattr(publisher_module, "MqttPublisher", lambda: MagicMock())

    fetch_positions()

    manager.filter.assert_called_once_with(
        status="ACTIVE",
        provides_position=True,
        source_type__in=["http", "both"],
    )
    manager.filter.return_value.select_related.assert_called_once_with(
        "equipment__vehicle"
    )


# ---------------------------------------------------------------------------
# Pre-fetch filter: a sensor is never even called over HTTP unless its own
# equipment/vehicle is in service.
# ---------------------------------------------------------------------------


def test_fetch_positions_never_fetches_sensor_with_out_of_service_vehicle(monkeypatch):
    fake_r = _fake_redis()  # only IN_SERVICE_VEHICLE_ID is in service
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    out_of_service_sensor = SimpleNamespace(
        id="sensor-oos",
        source_http_url="http://example.test/positions",
        source_json_mapping={},
        equipment=SimpleNamespace(vehicle_id=OUT_OF_SERVICE_VEHICLE_ID),
    )
    monkeypatch.setattr(
        Sensor, "objects", _fake_sensor_manager([out_of_service_sensor])
    )

    fake_adapter = MagicMock()
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(publisher_module, "MqttPublisher", lambda: fake_publisher)

    result = fetch_positions()

    fake_adapter.fetch.assert_not_called()
    fake_publisher.publish_batch.assert_not_called()
    assert "polled 1 sensors" in result
    assert "0 fetched" in result


def test_fetch_positions_skips_sensor_with_no_equipment_or_vehicle(monkeypatch):
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    no_equipment_sensor = SimpleNamespace(
        id="sensor-no-equipment",
        source_http_url="http://example.test/positions",
        source_json_mapping={},
        equipment=None,
    )
    no_vehicle_sensor = SimpleNamespace(
        id="sensor-no-vehicle",
        source_http_url="http://example.test/positions",
        source_json_mapping={},
        equipment=SimpleNamespace(vehicle_id=None),
    )
    monkeypatch.setattr(
        Sensor,
        "objects",
        _fake_sensor_manager([no_equipment_sensor, no_vehicle_sensor]),
    )

    fake_adapter = MagicMock()
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(publisher_module, "MqttPublisher", lambda: fake_publisher)

    result = fetch_positions()

    fake_adapter.fetch.assert_not_called()
    fake_publisher.publish_batch.assert_not_called()
    assert "polled 2 sensors" in result
    assert "0 fetched" in result


def test_fetch_positions_still_fetches_and_publishes_in_service_sensor(monkeypatch):
    """An in-service sensor is fetched and published even when another,
    out-of-service sensor is present and correctly skipped."""
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    in_service_sensor = _make_sensor(sensor_id="sensor-in-service")
    out_of_service_sensor = SimpleNamespace(
        id="sensor-oos",
        source_http_url="http://example.test/positions",
        source_json_mapping={},
        equipment=SimpleNamespace(vehicle_id=OUT_OF_SERVICE_VEHICLE_ID),
    )
    monkeypatch.setattr(
        Sensor,
        "objects",
        _fake_sensor_manager([in_service_sensor, out_of_service_sensor]),
    )

    fake_adapter = MagicMock()
    fake_adapter.fetch.return_value = [
        (IN_SERVICE_VEHICLE_ID, {"latitude": 1.0, "longitude": 2.0}),
    ]
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(publisher_module, "MqttPublisher", lambda: fake_publisher)

    result = fetch_positions()

    fake_adapter.fetch.assert_called_once_with(in_service_sensor)
    fake_publisher.publish_batch.assert_called_once()
    (published_records,), _ = fake_publisher.publish_batch.call_args
    assert [vid for vid, _ in published_records] == [IN_SERVICE_VEHICLE_ID]
    assert "polled 2 sensors" in result
    assert "1 fetched" in result


# ---------------------------------------------------------------------------
# soft_time_limit: a pathological source can't hold the task open forever.
# ---------------------------------------------------------------------------


def test_fetch_positions_handles_soft_time_limit_mid_loop(monkeypatch, caplog):
    fake_r = _fake_redis()
    monkeypatch.setattr(tasks_module, "redis_client", fake_r)

    sensor_a = _make_sensor(sensor_id="sensor-a")
    sensor_b = _make_sensor(sensor_id="sensor-b")
    monkeypatch.setattr(
        Sensor, "objects", _fake_sensor_manager([sensor_a, sensor_b])
    )

    fake_adapter = MagicMock()

    def _fetch(sensor):
        if sensor.id == "sensor-a":
            raise SoftTimeLimitExceeded()
        return [(IN_SERVICE_VEHICLE_ID, {"latitude": 1.0, "longitude": 2.0})]

    fake_adapter.fetch.side_effect = _fetch
    monkeypatch.setattr(sources_module, "get_adapter", lambda kind: fake_adapter)

    fake_publisher = MagicMock()
    monkeypatch.setattr(publisher_module, "MqttPublisher", lambda: fake_publisher)

    with caplog.at_level("WARNING"):
        result = fetch_positions()

    # The loop stopped at sensor-a; sensor-b was never reached.
    assert fake_adapter.fetch.call_count == 1
    fake_publisher.publish_batch.assert_not_called()
    assert "sensor-a" in caplog.text
    assert "soft time limit" in result.lower()
