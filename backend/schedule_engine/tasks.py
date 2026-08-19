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

from .builders import (
    build_vehicle_positions_feed,
    build_trip_updates_feed,
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


@shared_task(queue="schedule_engine")
def build_alerts():
    return "Feed ServiceAlert built"


@shared_task(queue="schedule_engine")
def build_schedule():
    """Build the GTFS Schedule zip and publish it to feed/files/gtfs.zip."""
    import logging

    logger = logging.getLogger(__name__)

    from feed.models import Feed
    from feed.schedule.exporter import publish_gtfs_zip

    feed = Feed.objects.filter(is_current=True).first()
    if feed is None:
        logger.warning("build_schedule: no current Feed found, skipping")
        return

    dest = publish_gtfs_zip(feed)
    return f"GTFS Schedule zip published: {dest} ({dest.stat().st_size} bytes)"
