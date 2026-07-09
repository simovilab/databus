import os
from celery import chord, group, shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import redis
from datetime import datetime
from django.conf import settings
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format

# Probably needed imports for telemetry fetching
import requests
import paho.mqtt.client as mqtt
from operations.models import Vehicle


from .builders import (
    build_vehicle_positions_feed,
    build_trip_updates_feed,
    get_current_timestamp,
    get_entity_id,
)


_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get("REDIS_HOST", "state"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            decode_responses=True,
        )
    return _redis


def get_feed_version():
    return "1.0.0"


@shared_task(queue="schedule_engine")
def build_vehicle_positions():
    """Build the VehiclePosition feed message."""
    r = get_redis()

    feed_message = build_vehicle_positions_feed(r)

    output_dir = settings.BASE_DIR / "feed" / "files"
    output_dir.mkdir(parents=True, exist_ok=True)

    feed_message_json = json.dumps(feed_message)
    with open(output_dir / "vehicle_positions.json", "w") as f:
        f.write(feed_message_json)

    feed_dict = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_dict, gtfs_rt.FeedMessage())
    with open(output_dir / "vehicle_positions.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    return f"VehiclePositions built: {len(feed_message['entity'])} entities"


@shared_task(queue="schedule_engine")
def build_trip_updates():
    r = get_redis()

    feed_message = build_trip_updates_feed(r)

    runs_in_progress = r.smembers("runs:in_progress")

    output_dir = settings.BASE_DIR / "feed" / "files"
    output_dir.mkdir(parents=True, exist_ok=True)

    feed_message_json = json.dumps(feed_message)
    with open(output_dir / "trip_updates.json", "w") as f:
        f.write(feed_message_json)

    feed_dict = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_dict, gtfs_rt.FeedMessage())
    with open(output_dir / "trip_updates.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "status",
                {
                    "type": "status_message",
                    "message": {
                        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "runs": len(runs_in_progress),
                    },
                },
            )
    except Exception:
        pass

    return f"TripUpdates built: {len(feed_message['entity'])} entities"


def fetch_and_publish(vehicle):
    response = requests.get(vehicle.position_source_url, timeout=10)
    response.raise_for_status()
    data = response.json()

    # Extract relevant fields from the JSON response using the position_source_paths mapping
    timestamp = data.get(vehicle.position_source_paths.get("paths").get("timestamp"))
    lat = data.get(vehicle.position_source_paths.get("paths").get("lat"))
    lon = data.get(vehicle.position_source_paths.get("paths").get("lon"))
    speed = data.get(vehicle.position_source_paths.get("paths").get("speed"))

    # Publish to MQTT broker
    mqtt_client = mqtt.Client()
    mqtt_client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, 60)
    topic = f"vehicle/{vehicle.id}/position"
    payload = json.dumps(
        {"timestamp": timestamp, "lat": lat, "lon": lon, "speed": speed}
    )
    mqtt_client.publish(topic, payload)
    mqtt_client.disconnect()
    return None


@shared_task(queue="schedule_engine")
def fetch_position():
    """
    Fetch telemetry position data from configured sources.

    Using the TelemetrySources model, this task retrieves telemetry data from various sources.

    The retrieved data is then processed relayed to the MQTT broker for further use in the system.

    type: array
    vehicle_id: JSON PATH
    timestamp: JSON PATH element.crDateTime
    lat: JSON PATH
    lon: JSON PATH
    speed: JSON PATH

    position_source_paths = {
       "type": "array",
       "paths": {
           "vehicle_id": "plateNumber",
           "timestamp": "crDateTime",
           "lat": "latitude",
           "lon": "longitude",
           "speed": "speed"
       }
    }

    Publish to MQTT broker at topic: vehicle/<vehicle_id>/position with payload:
    {
        "timestamp": <timestamp>,
        "lat": <lat>,
        "lon": <lon>,
        "speed": <speed>
    }
    """
    vehicles_in_runs_in_progress = get_redis().smembers("runs:in_progress")
    for vehicle_in_progress in vehicles_in_runs_in_progress:
        vehicle = Vehicle.objects.get(id=vehicle_in_progress)
        if vehicle.position_source_type == "mqtt":
            # Check if the vehicle has updated positions in Redis
            position_data = get_redis().get(f"vehicle:{vehicle.id}:position")
            if position_data:
                continue  # Position data already exists, skip fetching
            elif vehicle.position_source_type == "both":
                try:
                    fetch_and_publish(vehicle)
                except requests.RequestException as e:
                    print(f"Error fetching position for vehicle {vehicle.id}: {e}")
                except Exception as e:
                    print(f"Unexpected error for vehicle {vehicle.id}: {e}")
        elif vehicle.position_source_type == "http":
            try:
                fetch_and_publish(vehicle)
            except requests.RequestException as e:
                print(f"Error fetching position for vehicle {vehicle.id}: {e}")
            except Exception as e:
                print(f"Unexpected error for vehicle {vehicle.id}: {e}")
    return "Position data fetched and published to MQTT broker"


@shared_task(queue="schedule_engine")
def build_alerts():
    return "Feed ServiceAlert built"


@shared_task(queue="schedule_engine")
def update_gtfs_realtime():

    fetching = group(fetch_position.s())
    building = group(
        build_vehicle_positions.s(), build_trip_updates.s(), build_alerts.s()
    )
    workflow = chord(fetching)(building)

    return workflow.id
