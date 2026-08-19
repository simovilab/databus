"""Celery tasks that build and publish the GTFS-RT/Schedule feed artifacts.

Reads Redis state (written by ``realtime_engine`` only) via ``builders.py``
and serializes the result to JSON + protobuf under ``feed/files/``. Also
publishes the daily GTFS Schedule zip via ``feed.schedule.exporter``.
"""

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, cast

import redis
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2 as gtfs_rt

from .builders import (
    build_trip_updates_feed,
    build_vehicle_positions_feed,
)

if TYPE_CHECKING:
    from .builders import RedisLike


_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the module-level Redis client, lazily creating it on first use."""
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get("REDIS_HOST", "state"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            decode_responses=True,
        )
    return _redis


def get_feed_version() -> str:
    """Return the static schedule_engine GTFS-RT feed format version string."""
    return "1.0.0"


def _smembers(r: redis.Redis, key: str) -> set[str]:
    """Read a Redis set as `set[str]`, narrowing away redis-py's shared Awaitable stub."""
    return cast("set[str]", r.smembers(key))


@shared_task(queue="schedule_engine")
def build_vehicle_positions() -> str:
    """Build the VehiclePositions GTFS-RT feed and write it as JSON and protobuf."""
    r = get_redis()

    feed_message = build_vehicle_positions_feed(cast("RedisLike", r))

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
def build_trip_updates() -> str:
    """Build the TripUpdates GTFS-RT feed, write it as JSON/protobuf, and broadcast status."""
    r = get_redis()

    feed_message = build_trip_updates_feed(cast("RedisLike", r))

    runs_in_progress = _smembers(r, "runs:in_progress")

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
def build_alerts() -> str:
    """Return a placeholder string; the ServiceAlert feed builder is not yet implemented.

    Deliberately NOT registered in the Celery beat schedule (see periodic_engine /
    Django admin) — this task is a stub, not a working feed producer.
    """
    return "Feed ServiceAlert built"


@shared_task(queue="schedule_engine")
def build_schedule() -> str | None:
    """Export the current GTFS Schedule to a zip and publish it under feed/files/."""
    import logging

    logger = logging.getLogger(__name__)

    from feed.models import Feed
    from feed.schedule.exporter import publish_gtfs_zip

    feed = Feed.objects.filter(is_current=True).first()
    if feed is None:
        logger.warning("build_schedule: no current Feed found, skipping")
        return None

    dest = publish_gtfs_zip(feed)
    return f"GTFS Schedule zip published: {dest} ({dest.stat().st_size} bytes)"
