"""MQTT publishing for HTTP-sourced telemetry.

Mirrors the paho-mqtt v2 client setup already used by the ingestion
consumer (``realtime_engine/mqtt.py``) so messages published from here land
on exactly the topics that consumer subscribes to:
``transit/vehicle/<vehicle_id>/position``, QoS 0, not retained.
"""

from __future__ import annotations

import json
import logging
import os

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_HOST", "telemetry-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

POSITION_TOPIC_TEMPLATE = "transit/vehicle/{vehicle_id}/position"


def position_topic(vehicle_id: str) -> str:
    return POSITION_TOPIC_TEMPLATE.format(vehicle_id=vehicle_id)


def publish_position(client: mqtt.Client, vehicle_id: str, payload: dict) -> None:
    """Publish a single position payload for ``vehicle_id``.

    Catches and logs publish errors per-message so one bad publish doesn't
    take down the rest of a batch.
    """
    topic = position_topic(vehicle_id)
    try:
        client.publish(topic, json.dumps(payload), qos=0, retain=False)
    except Exception:
        logger.exception("Failed to publish position for vehicle %s", vehicle_id)


class MqttPublisher:
    """Thin wrapper managing a paho v2 client's connect/publish/disconnect cycle."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or MQTT_HOST
        self.port = port or MQTT_PORT
        self._client: mqtt.Client | None = None

    def _build_client(self) -> mqtt.Client:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self) -> None:
        self._client = self._build_client()
        self._client.connect(self.host, self.port, keepalive=60)

    def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            self._client.disconnect()
        except Exception:
            logger.exception("Error disconnecting MQTT publisher client")
        finally:
            self._client = None

    def publish_batch(self, records: list[tuple[str, dict]]) -> None:
        """Connect, publish every ``(vehicle_id, payload)`` record, then disconnect.

        Each record is published independently — a failure on one message
        is logged (via ``publish_position``) without aborting the batch.
        """
        self.connect()
        try:
            for vehicle_id, payload in records:
                publish_position(self._client, vehicle_id, payload)
        finally:
            self.disconnect()
