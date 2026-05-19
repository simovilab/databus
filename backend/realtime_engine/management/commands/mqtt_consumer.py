"""
Django management command: mqtt_consumer

Long-lived MQTT subscriber that bridges vehicle telemetry into the run
lifecycle FSM.  Run by the 'realtime-consumer' compose service.

Topic pattern: transit/vehicle/+/{position,progression,occupancy,data}
"""
import json
import logging
import os
import time

import redis
from django.core.management.base import BaseCommand
from django.utils.timezone import now

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_HOST", "telemetry-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

_redis = redis.Redis(
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

    run_id_bytes = _redis.get(f"vehicle:{vehicle_id}:current_run")
    if not run_id_bytes:
        logger.debug("No active run for vehicle %s — dropping %s", vehicle_id, leaf)
        return

    run_id = run_id_bytes

    # Persist raw telemetry so GTFS-RT builders can read it
    if isinstance(data, dict):
        _redis.hset(f"vehicle:{vehicle_id}:{leaf}", mapping={k: str(v) for k, v in data.items()})

    # Update last-seen timestamp
    _redis.set(f"runs:last_seen:{run_id}", now().isoformat())

    # Determine which lifecycle event (if any) to fire
    _maybe_fire_lifecycle_event(run_id, vehicle_id, leaf, data)


def _maybe_fire_lifecycle_event(
    run_id: str, vehicle_id: str, leaf: str, data: dict
) -> None:
    from realtime_engine.tasks import run_lifecycle_event

    run_state = _redis.hget(f"run:{run_id}", "run_lifecycle_state")
    if not run_state:
        return

    payload = {
        "run_id": run_id,
        "vehicle_id": vehicle_id,
        "last_seen_at": now().isoformat(),
        **data,
    }

    if run_state == "Confirmed":
        # CONFIRMED → TRACKING: first valid ping
        _redis.sadd("runs:tracking", run_id)
        run_lifecycle_event.delay("run_tracking_started", payload)

    elif run_state == "Tracking" and leaf == "position":
        speed = float(data.get("speed", 0))
        if speed > 0.5:
            # TRACKING → IN_PROGRESS: vehicle is moving
            run_lifecycle_event.delay("run_started", payload)

    elif run_state == "No Signal":
        # NO_SIGNAL → IN_PROGRESS: signal restored
        _redis.sadd("runs:tracking", run_id)
        run_lifecycle_event.delay("run_tracking_restored", payload)

    elif run_state == "In Progress" and leaf == "progression":
        current_status = data.get("current_status", "")
        stop_id = data.get("stop_id", "")
        if current_status == "STOPPED_AT" and stop_id:
            # May be at terminal stop — fire COMPLETE_RUN and let the guard decide
            run_lifecycle_event.delay("complete_run", {**payload, "stop_id": stop_id})


def _on_connect(client: mqtt.Client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.subscribe("transit/vehicle/+/position", qos=0)
        client.subscribe("transit/vehicle/+/progression", qos=0)
        client.subscribe("transit/vehicle/+/occupancy", qos=0)
    else:
        logger.error("MQTT connection refused, rc=%d", rc)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    vehicle_id = _vehicle_id_from_topic(msg.topic)
    leaf = _leaf_from_topic(msg.topic)
    if not vehicle_id or not leaf:
        return
    try:
        _handle_telemetry(vehicle_id, leaf, msg.payload)
    except Exception:
        logger.exception("Error processing telemetry for vehicle %s/%s", vehicle_id, leaf)


class Command(BaseCommand):
    help = "Long-lived MQTT subscriber — bridges vehicle telemetry into the run lifecycle FSM"

    def handle(self, *args, **options):
        client = mqtt.Client(client_id="databus-realtime-consumer", clean_session=True)
        client.on_connect = _on_connect
        client.on_message = _on_message

        while True:
            try:
                client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
                client.loop_forever()
            except Exception:
                logger.exception("MQTT connection failed — retrying in 5s")
                time.sleep(5)
