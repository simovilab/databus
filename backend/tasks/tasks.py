import os
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import redis
from datetime import datetime
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format
from .fake_stop_times import build_stop_time_updates


_redis = None


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get(
                "REDIS_HOST", "state"
            ),  # use compose service name, not localhost
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            decode_responses=True,
        )
    return _redis


def get_feed_version():
    # TODO: Implement a method to get the current feed version, e.g., from a database
    return "1.0.0"


def get_entity_id(vehicle_id):
    # TODO: Implement a method to get a unique entity ID based on vehicle ID or trip_id + schedule_relationship
    return vehicle_id


def get_current_timestamp():
    return int(datetime.now().timestamp())


@shared_task(queue="tasks")
def build_vehicle_positions():
    """
    Build the VehiclePosition feed message."""

    r = get_redis()

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = get_current_timestamp()
    feed_message["header"]["feed_version"] = get_feed_version()

    # Feed message entity
    feed_message["entity"] = []

    # Get all in-progress runs
    runs_in_progress = r.smembers("runs:in_progress")

    for run_id in runs_in_progress:
        run = r.hgetall(run_id)
        vehicle_id = run["vehicle"]
        vehicle = r.hgetall(f"vehicle:{vehicle_id}:data")
        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")
        occupancy = r.hgetall(f"vehicle:{vehicle_id}:occupancy")

        if not position and not progression and not occupancy:
            continue

        entity = {}
        entity["id"] = f"{vehicle['id']}"
        entity["vehicle"] = {}
        entity["vehicle"]["timestamp"] = int(position["timestamp"])
        entity["vehicle"]["trip"] = {}
        entity["vehicle"]["trip"]["trip_id"] = run["trip_id"]
        entity["vehicle"]["trip"]["route_id"] = run["route_id"]
        entity["vehicle"]["trip"]["direction_id"] = run["direction_id"]
        entity["vehicle"]["trip"]["start_time"] = run["start_time"]
        entity["vehicle"]["trip"]["start_date"] = run["start_date"]
        entity["vehicle"]["trip"]["schedule_relationship"] = run[
            "schedule_relationship"
        ]
        entity["vehicle"]["vehicle"] = {}
        entity["vehicle"]["vehicle"]["id"] = vehicle["id"]
        entity["vehicle"]["vehicle"]["label"] = vehicle["label"]
        entity["vehicle"]["vehicle"]["license_plate"] = vehicle["license_plate"]
        if vehicle.get("wheelchair_accessible"):
            entity["vehicle"]["vehicle"]["wheelchair_accessible"] = vehicle[
                "wheelchair_accessible"
            ]
        if position:
            entity["vehicle"]["position"] = {}
            entity["vehicle"]["position"]["latitude"] = position["latitude"]
            entity["vehicle"]["position"]["longitude"] = position["longitude"]
            if position.get("bearing"):
                entity["vehicle"]["position"]["bearing"] = position["bearing"]
            if position.get("odometer"):
                entity["vehicle"]["position"]["odometer"] = position["odometer"]
            if position.get("speed"):
                entity["vehicle"]["position"]["speed"] = position["speed"]
        if progression:
            if progression.get("current_stop_sequence"):
                entity["vehicle"]["current_stop_sequence"] = progression[
                    "current_stop_sequence"
                ]
            if progression.get("stop_id"):
                entity["vehicle"]["stop_id"] = progression["stop_id"]
            if progression.get("current_status"):
                entity["vehicle"]["current_status"] = progression["current_status"]
            if progression.get("congestion_level"):
                entity["vehicle"]["congestion_level"] = progression["congestion_level"]
        if occupancy:
            if occupancy.get("occupancy_status"):
                entity["vehicle"]["occupancy_status"] = occupancy["occupancy_status"]
            if occupancy.get("occupancy_percentage"):
                entity["vehicle"]["occupancy_percentage"] = occupancy[
                    "occupancy_percentage"
                ]

        # Append entity to feed message
        feed_message["entity"].append(entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message)
    with open("tasks/files/vehicle_positions.json", "w") as f:
        f.write(feed_message_json)

    # Create and save Protobuf
    feed_message_json = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_message_json, gtfs_rt.FeedMessage())
    with open("tasks/files/vehicle_positions.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    return "FeedMessage VehiclePosition built successfully"


@shared_task(queue="tasks")
def build_trip_updates():
    r = get_redis()

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = get_current_timestamp()
    feed_message["header"]["feed_version"] = get_feed_version()

    # Feed message entity
    feed_message["entity"] = []

    # Get all in-progress runs
    runs_in_progress = r.smembers("runs:in_progress")

    for run_id in runs_in_progress:
        run = r.hgetall(run_id)
        vehicle_id = run["vehicle"]
        vehicle = r.hgetall(f"vehicle:{vehicle_id}:data")
        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")

        if not position and not progression:
            continue

        entity = {}
        entity["id"] = get_entity_id(vehicle["id"])
        entity["trip_update"] = {}
        entity["trip_update"]["timestamp"] = int(position["timestamp"])
        entity["trip_update"]["trip"] = {}
        entity["trip_update"]["trip"]["trip_id"] = run["trip_id"]
        entity["trip_update"]["trip"]["route_id"] = run["route_id"]
        entity["trip_update"]["trip"]["direction_id"] = run["direction_id"]
        entity["trip_update"]["trip"]["start_time"] = run["start_time"]
        entity["trip_update"]["trip"]["start_date"] = run["start_date"]
        entity["trip_update"]["trip"]["schedule_relationship"] = run[
            "schedule_relationship"
        ]
        entity["trip_update"]["vehicle"] = {}
        entity["trip_update"]["vehicle"]["id"] = vehicle["id"]
        entity["trip_update"]["vehicle"]["label"] = vehicle["label"]
        entity["trip_update"]["vehicle"]["license_plate"] = vehicle["license_plate"]
        if vehicle.get("wheelchair_accessible"):
            entity["trip_update"]["vehicle"]["wheelchair_accessible"] = vehicle[
                "wheelchair_accessible"
            ]
        entity["trip_update"]["stop_time_update"] = []
        stop_time_updates = build_stop_time_updates(
            run=run, position=position, progression=progression
        )
        for update in stop_time_updates:
            stop_time_update = {}
            stop_time_update["stop_sequence"] = update["stop_sequence"]
            stop_time_update["stop_id"] = update["stop_id"]
            stop_time_update["arrival"] = {}
            stop_time_update["arrival"]["time"] = update["eta_posix"]
            stop_time_update["arrival"]["uncertainty"] = update["uncertainty"]
            stop_time_update["departure"] = {}
            stop_time_update["departure"]["time"] = update["eta_posix"]
            stop_time_update["departure"]["uncertainty"] = update["uncertainty"]

            # Append stop time update to stop time updates
            entity["trip_update"]["stop_time_update"].append(stop_time_update)

        # Append entity to feed message
        feed_message["entity"].append(entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message)
    with open("tasks/files/trip_updates.json", "w") as f:
        f.write(feed_message_json)

    # Create and save Protobuf
    feed_message_json = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_message_json, gtfs_rt.FeedMessage())
    with open("tasks/files/trip_updates.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    # Send status update to WebSocket
    message = {}
    message["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message["runs"] = len(runs_in_progress)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "status",
        {
            "type": "status_message",
            "message": message,
        },
    )

    return "Feed TripUpdate built."


@shared_task(queue="tasks")
def build_alerts():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"
