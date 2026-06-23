"""
MQTT telemetry consumer — runs as a Celery bootstep inside the realtime-engine
worker process.

The bootstep is registered for every worker that loads ``databus.celery`` but
only activates when ``MQTT_CONSUMER_ENABLED`` is truthy. Compose sets this only
on the realtime-engine service, so other workers (schedule-engine, beat) skip
it and don't double-subscribe to the broker.

Topic pattern: ``transit/vehicle/<vehicle_id>/{position,occupancy}``.

Topic routing:
- ``position`` and ``occupancy`` are edge-sensed and written to
  ``vehicle:<id>:position`` / ``vehicle:<id>:occupancy`` via the telemetry
  contract (``runs.domain.telemetry``).
- ``progression`` is decommissioned server-side; we no longer subscribe even
  though the simulator may still publish it.
- ``occupancy_status`` is a server policy decision: the edge-sent value is
  discarded and recomputed with ``occupancy.classify_status`` at write time.
"""

import json
import logging
import os
import socket

import paho.mqtt.client as mqtt
import redis
from celery import bootsteps
from django.utils.timezone import now

from runs.domain.telemetry import keys, occupancy, position

logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_HOST", "telemetry-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_CONSUMER_ENABLED = os.getenv("MQTT_CONSUMER_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


def _vehicle_id_from_topic(topic: str) -> str | None:
    """Extract vehicle_id from transit/vehicle/<id>/<leaf>."""
    parts = topic.split("/")
    if len(parts) == 4 and parts[0] == "transit" and parts[1] == "vehicle":
        return parts[2]
    return None


def _leaf_from_topic(topic: str) -> str | None:
    parts = topic.split("/")
    return parts[-1] if len(parts) == 4 else None


def _handle_telemetry(vehicle_id: str, leaf: str, payload_bytes: bytes) -> None:
    try:
        data = json.loads(payload_bytes)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Non-JSON payload on vehicle %s/%s — ignored", vehicle_id, leaf)
        return

    run_id = r.get(keys.current_run_key(vehicle_id))
    if not run_id:
        logger.debug("No active run for vehicle %s — dropping %s", vehicle_id, leaf)
        return

    if leaf == "position":
        try:
            mapping = position.validate_for_write(data)
        except ValueError:
            logger.warning(
                "Invalid position payload for vehicle %s — dropped: %r",
                vehicle_id,
                data,
            )
            return
        r.hset(keys.position_key(vehicle_id), mapping=mapping)
        # Heavy work (map-matching, projection, detection) runs off the network
        # thread. Enqueue after the HSET so the task always reads at least the
        # value we just wrote.
        from realtime_engine.tasks import process_position_update
        process_position_update.delay(run_id, vehicle_id)

    elif leaf == "occupancy":
        # occupancy_status is server policy — discard any edge-sent value and
        # recompute it from the raw percentage.
        raw_pct = data.get("occupancy_percentage")
        try:
            pct = int(raw_pct) if raw_pct is not None else None
        except (ValueError, TypeError):
            pct = None

        occ_payload = {
            k: v
            for k, v in data.items()
            if k != occupancy.OCCUPANCY_STATUS
        }
        occ_payload[occupancy.OCCUPANCY_STATUS] = occupancy.classify_status(pct)

        try:
            mapping = occupancy.validate_for_write(occ_payload)
        except ValueError:
            logger.warning(
                "Invalid occupancy payload for vehicle %s — dropped: %r",
                vehicle_id,
                data,
            )
            return
        r.hset(keys.occupancy_key(vehicle_id), mapping=mapping)

    else:
        # Unknown leaf (e.g. legacy 'progression' still published by simulator).
        # Drop silently at debug level — a bad payload must not crash ingestion.
        logger.debug(
            "Unknown telemetry leaf '%s' for vehicle %s — dropped",
            leaf,
            vehicle_id,
        )
        return

    # last_seen is kept synchronous so staleness detection is never delayed by
    # queue latency (even with a slow worker draining the realtime_engine queue).
    r.set(keys.last_seen_key(run_id), now().isoformat())

    # Position detection (RunStartedDetector, RunTrackingStartedDetector, …) now
    # runs inside process_position_update off the network thread.  Occupancy
    # detection is cheap and still fires inline — RunTrackingStartedDetector and
    # RunTrackingRestoredDetector both match any leaf, so occupancy must still
    # reach detect_from_telemetry for correct lifecycle transitions.
    if leaf == "occupancy":
        from runs.domain.detection.dispatch import detect_from_telemetry
        detect_from_telemetry(run_id, vehicle_id, leaf, data)


def _on_connect(client: mqtt.Client, userdata, flags, rc) -> None:
    if rc == 0:
        logger.info("MQTT connected: %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe("transit/vehicle/+/position", qos=0)
        client.subscribe("transit/vehicle/+/occupancy", qos=0)
        # 'progression' is intentionally NOT subscribed — decommissioned.
    else:
        logger.error("MQTT connection refused: rc=%d", rc)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
    vehicle_id = _vehicle_id_from_topic(msg.topic)
    leaf = _leaf_from_topic(msg.topic)
    if not vehicle_id or not leaf:
        return
    try:
        _handle_telemetry(vehicle_id, leaf, msg.payload)
    except Exception:
        logger.exception("Telemetry handling failed for %s/%s", vehicle_id, leaf)


def build_client() -> mqtt.Client:
    # Unique per process: a fixed client_id makes a second consumer (e.g. another
    # worker that also has MQTT_CONSUMER_ENABLED) collide on the broker and trigger
    # an endless reconnect war. Single-consumer gating is still the real guarantee;
    # this only keeps an accidental duplicate from being catastrophic.
    client_id = f"databus-mqtt-consumer-{socket.gethostname()}-{os.getpid()}"
    client = mqtt.Client(client_id=client_id, clean_session=True)
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


class MQTTConsumerStep(bootsteps.StartStopStep):
    """Celery worker bootstep that runs the MQTT subscriber in-process.

    paho's `loop_start()` spawns its own background thread and handles
    reconnects internally, so the bootstep only orchestrates lifecycle:
    start on worker boot, stop on worker shutdown.
    """

    requires = {"celery.worker.components:Pool"}

    def __init__(self, worker, **kwargs):
        super().__init__(worker, **kwargs)
        self.client: mqtt.Client | None = None

    def start(self, worker) -> None:
        if not MQTT_CONSUMER_ENABLED:
            logger.info(
                "MQTT consumer bootstep disabled (MQTT_CONSUMER_ENABLED=%s)",
                os.getenv("MQTT_CONSUMER_ENABLED", "<unset>"),
            )
            return
        logger.info("Starting MQTT consumer bootstep (%s:%s)", MQTT_HOST, MQTT_PORT)
        client = build_client()
        try:
            client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            self.client = client
        except Exception:
            logger.exception("MQTT consumer failed to start")
            self.client = None

    def stop(self, worker) -> None:
        if self.client is None:
            return
        logger.info("Stopping MQTT consumer bootstep")
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            logger.exception("MQTT consumer shutdown failed")
        finally:
            self.client = None
