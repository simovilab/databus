import os
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import redis
from datetime import datetime
from django.conf import settings
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format
from .fake_stop_times import build_stop_time_updates


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


def get_entity_id(vehicle_id):
    return vehicle_id


def get_current_timestamp():
    return int(datetime.now().timestamp())


@shared_task(queue="schedule_engine")
def build_vehicle_positions():
    """Build the VehiclePosition feed message."""
    r = get_redis()

    feed_message = {
        "header": {
            "gtfs_realtime_version": "2.0",
            "incrementality": "FULL_DATASET",
            "timestamp": get_current_timestamp(),
        },
        "entity": [],
    }

    runs_in_progress = r.smembers("runs:in_progress")

    for run_id in runs_in_progress:
        run = r.hgetall(f"run:{run_id}")
        if not run:
            continue
        vehicle_id = run.get("vehicle", "")
        if not vehicle_id:
            continue

        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")
        occupancy = r.hgetall(f"vehicle:{vehicle_id}:occupancy")
        vehicle_meta = r.hgetall(f"vehicle:{vehicle_id}:data")

        if not position and not progression and not occupancy:
            continue

        entity: dict = {"id": vehicle_id, "vehicle": {}}
        v = entity["vehicle"]

        if position.get("timestamp"):
            try:
                v["timestamp"] = int(float(position["timestamp"]))
            except (ValueError, TypeError):
                v["timestamp"] = get_current_timestamp()
        else:
            v["timestamp"] = get_current_timestamp()

        v["trip"] = {
            "trip_id": run.get("trip_id", ""),
            "route_id": run.get("route_id", ""),
            "schedule_relationship": run.get("schedule_relationship", "SCHEDULED"),
        }
        if run.get("direction_id") not in (None, ""):
            try:
                v["trip"]["direction_id"] = int(run["direction_id"])
            except (ValueError, TypeError):
                pass
        if run.get("start_time"):
            v["trip"]["start_time"] = run["start_time"]
        if run.get("start_date"):
            v["trip"]["start_date"] = run["start_date"]

        v["vehicle"] = {
            "id": vehicle_meta.get("id", vehicle_id),
            "label": vehicle_meta.get("label", vehicle_id),
        }
        if vehicle_meta.get("license_plate"):
            v["vehicle"]["license_plate"] = vehicle_meta["license_plate"]
        if vehicle_meta.get("wheelchair_accessible"):
            v["vehicle"]["wheelchair_accessible"] = vehicle_meta["wheelchair_accessible"]

        if position:
            try:
                pos_entry: dict = {
                    "latitude": float(position.get("latitude", 0)),
                    "longitude": float(position.get("longitude", 0)),
                }
                if position.get("bearing"):
                    pos_entry["bearing"] = float(position["bearing"])
                if position.get("speed"):
                    pos_entry["speed"] = float(position["speed"])
                if position.get("odometer"):
                    pos_entry["odometer"] = float(position["odometer"])
                v["position"] = pos_entry
            except (ValueError, TypeError):
                pass

        if progression:
            if progression.get("current_stop_sequence"):
                try:
                    v["current_stop_sequence"] = int(progression["current_stop_sequence"])
                except (ValueError, TypeError):
                    pass
            if progression.get("stop_id"):
                v["stop_id"] = progression["stop_id"]
            if progression.get("current_status"):
                v["current_status"] = progression["current_status"]
            if progression.get("congestion_level"):
                v["congestion_level"] = progression["congestion_level"]

        if occupancy:
            if occupancy.get("occupancy_status"):
                v["occupancy_status"] = occupancy["occupancy_status"]
            if occupancy.get("occupancy_percentage"):
                try:
                    v["occupancy_percentage"] = int(occupancy["occupancy_percentage"])
                except (ValueError, TypeError):
                    pass

        feed_message["entity"].append(entity)

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

    feed_message = {
        "header": {
            "gtfs_realtime_version": "2.0",
            "incrementality": "FULL_DATASET",
            "timestamp": get_current_timestamp(),
        },
        "entity": [],
    }

    runs_in_progress = r.smembers("runs:in_progress")

    for run_id in runs_in_progress:
        run = r.hgetall(f"run:{run_id}")
        if not run:
            continue
        vehicle_id = run.get("vehicle", "")
        if not vehicle_id:
            continue

        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")
        vehicle_meta = r.hgetall(f"vehicle:{vehicle_id}:data")

        if not position and not progression:
            continue

        entity: dict = {"id": get_entity_id(vehicle_id), "trip_update": {}}
        tu = entity["trip_update"]

        if position.get("timestamp"):
            try:
                tu["timestamp"] = int(float(position["timestamp"]))
            except (ValueError, TypeError):
                tu["timestamp"] = get_current_timestamp()
        else:
            tu["timestamp"] = get_current_timestamp()

        tu["trip"] = {
            "trip_id": run.get("trip_id", ""),
            "route_id": run.get("route_id", ""),
            "schedule_relationship": run.get("schedule_relationship", "SCHEDULED"),
        }
        if run.get("direction_id") not in (None, ""):
            try:
                tu["trip"]["direction_id"] = int(run["direction_id"])
            except (ValueError, TypeError):
                pass
        if run.get("start_time"):
            tu["trip"]["start_time"] = run["start_time"]
        if run.get("start_date"):
            tu["trip"]["start_date"] = run["start_date"]

        tu["vehicle"] = {
            "id": vehicle_meta.get("id", vehicle_id),
            "label": vehicle_meta.get("label", vehicle_id),
        }
        if vehicle_meta.get("license_plate"):
            tu["vehicle"]["license_plate"] = vehicle_meta["license_plate"]

        stop_time_updates = build_stop_time_updates(
            run=run, progression=progression
        )
        tu["stop_time_update"] = []
        for update in stop_time_updates:
            tu["stop_time_update"].append({
                "stop_sequence": update["stop_sequence"],
                "stop_id": update["stop_id"],
                "arrival": {
                    "time": update["eta_posix"],
                    "uncertainty": update["uncertainty"],
                },
                "departure": {
                    "time": update["eta_posix"],
                    "uncertainty": update["uncertainty"],
                },
            })

        feed_message["entity"].append(entity)

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


@shared_task(queue="schedule_engine")
def build_alerts():
    return "Feed ServiceAlert built"
