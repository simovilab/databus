"""Unit tests for realtime_engine.sources.publisher.

No real MQTT broker: the paho client is a MagicMock throughout, and
``MqttPublisher._build_client`` is monkeypatched so ``connect()`` never
touches the network.
"""

import json
from unittest.mock import MagicMock, call

from realtime_engine.sources import publisher


# ---------------------------------------------------------------------------
# publish_position
# ---------------------------------------------------------------------------


def test_publish_position_uses_correct_topic_and_json_body():
    client = MagicMock()
    payload = {"latitude": 9.93, "longitude": -84.05, "speed": 10.0}

    publisher.publish_position(client, "299-1014", payload)

    client.publish.assert_called_once_with(
        "transit/vehicle/299-1014/position",
        json.dumps(payload),
        qos=0,
        retain=False,
    )


def test_publish_position_swallows_client_errors():
    client = MagicMock()
    client.publish.side_effect = RuntimeError("broker unreachable")

    # Must not raise.
    publisher.publish_position(client, "299-1014", {"latitude": 1.0, "longitude": 2.0})


def test_position_topic_format():
    assert publisher.position_topic("abc-123") == "transit/vehicle/abc-123/position"


# ---------------------------------------------------------------------------
# MqttPublisher lifecycle
# ---------------------------------------------------------------------------


def test_mqtt_publisher_connect_builds_client_and_connects(monkeypatch):
    mock_client = MagicMock()
    pub = publisher.MqttPublisher(host="broker-host", port=1884)
    monkeypatch.setattr(pub, "_build_client", lambda: mock_client)

    pub.connect()

    mock_client.connect.assert_called_once_with("broker-host", 1884, keepalive=60)


def test_mqtt_publisher_disconnect_is_safe_when_not_connected():
    pub = publisher.MqttPublisher()
    # Must not raise even though connect() was never called.
    pub.disconnect()


def test_mqtt_publisher_publish_batch_connects_publishes_all_then_disconnects(monkeypatch):
    mock_client = MagicMock()
    pub = publisher.MqttPublisher()
    monkeypatch.setattr(pub, "_build_client", lambda: mock_client)

    records = [
        ("veh-1", {"latitude": 1.0, "longitude": 2.0}),
        ("veh-2", {"latitude": 3.0, "longitude": 4.0}),
    ]
    pub.publish_batch(records)

    mock_client.connect.assert_called_once()
    assert mock_client.publish.call_count == 2
    mock_client.publish.assert_has_calls(
        [
            call(
                "transit/vehicle/veh-1/position",
                json.dumps({"latitude": 1.0, "longitude": 2.0}),
                qos=0,
                retain=False,
            ),
            call(
                "transit/vehicle/veh-2/position",
                json.dumps({"latitude": 3.0, "longitude": 4.0}),
                qos=0,
                retain=False,
            ),
        ]
    )
    mock_client.disconnect.assert_called_once()


def test_mqtt_publisher_publish_batch_disconnects_even_if_publish_raises(monkeypatch):
    mock_client = MagicMock()
    mock_client.publish.side_effect = RuntimeError("boom")
    pub = publisher.MqttPublisher()
    monkeypatch.setattr(pub, "_build_client", lambda: mock_client)

    # publish_position catches the error internally, so this must not raise,
    # and disconnect must still be called.
    pub.publish_batch([("veh-1", {"latitude": 1.0, "longitude": 2.0})])

    mock_client.disconnect.assert_called_once()


def test_build_client_uses_paho_v2_callback_api(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, callback_api_version):
            captured["callback_api_version"] = callback_api_version

    monkeypatch.setattr(publisher.mqtt, "Client", FakeClient)

    pub = publisher.MqttPublisher()
    client = pub._build_client()

    assert isinstance(client, FakeClient)
    assert captured["callback_api_version"] == publisher.mqtt.CallbackAPIVersion.VERSION2
