import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis
from celery import shared_task
from django.utils.timezone import now

from runs.services.lifecycle import RunLifecycleService

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


@shared_task(queue="realtime_engine")
def run_lifecycle_event(event: str, payload: dict[str, Any]) -> None:
    from runs.domain.lifecycle import RunLifecycleEvents

    service = RunLifecycleService()
    try:
        evt = RunLifecycleEvents(event)
    except ValueError:
        logger.error("Unknown lifecycle event: %s", event)
        return
    try:
        service.process_event(evt, payload)
    except Exception:
        logger.exception(
            "Lifecycle event %s failed for run %s", event, payload.get("run_id")
        )


@shared_task(queue="realtime_engine")
def scan_stale_runs() -> str:
    """Scan ``runs:tracking`` every 30 s and let the detection layer decide.

    The staleness windows and the IN_PROGRESS/NO_SIGNAL conditions live in the
    periodic detectors (``runs.domain.detection``); this task only computes how
    long each run has been quiet and hands it to the dispatcher.
    """
    from runs.domain.detection.dispatch import detect_from_scan

    run_ids = redis_client.smembers("runs:tracking")
    fired = 0
    for run_id in run_ids:
        raw_last_seen = redis_client.get(f"runs:last_seen:{run_id}")
        if not raw_last_seen:
            continue
        try:
            last_seen = datetime.fromisoformat(raw_last_seen)
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        staleness = (now() - last_seen).total_seconds()
        fired += detect_from_scan(run_id, staleness, raw_last_seen)

    return f"scan_stale_runs: checked {len(run_ids)} runs, fired {fired} events"


@shared_task(queue="realtime_engine")
def fetch_positions() -> str:
    """Poll active HTTP telemetry sources and publish in-service vehicle positions.

    1. Build the in-service vehicle-id set: every vehicle with an active
       (non-terminal) run assigned, i.e. a ``vehicle:<id>:current_run`` key.
       This is the *same* gate the MQTT consumer uses to accept telemetry, so
       the poller and the consumer agree on which vehicles count. Gating on
       ``runs:in_progress`` instead would deadlock a CONFIRMED run: it only
       reaches IN_PROGRESS once telemetry proves the vehicle is moving, and
       delivering that telemetry is exactly this task's job.
    2. Query ACTIVE sensors that provide position data over HTTP (source_type
       "http" or "both" both use the "http" adapter).
    3. Fetch each sensor's readings, keep only the ones for in-service
       vehicles, and publish the survivors on ``transit/vehicle/<id>/position``.

    Each sensor is fetched independently inside its own try/except so one
    failing source can't sink the rest of the poll.
    """
    from operations.models import Sensor
    from runs.domain.telemetry import keys
    from realtime_engine.sources import get_adapter
    from realtime_engine.sources.publisher import MqttPublisher

    # Derive the key prefix/suffix from the helper so we never hardcode the
    # ``vehicle:<id>:current_run`` shape here.
    _prefix, _suffix = keys.current_run_key("\x00").split("\x00")
    in_service_vehicle_ids: set[str] = {
        key[len(_prefix): len(key) - len(_suffix)]
        for key in redis_client.scan_iter(match=keys.current_run_key("*"))
    }

    sensors = Sensor.objects.filter(
        status="ACTIVE",
        provides_position=True,
        source_type__in=["http", "both"],
    ).select_related("equipment__vehicle")

    readings: list[tuple[str, dict]] = []
    sensor_count = 0
    failure_count = 0
    for sensor in sensors:
        sensor_count += 1
        try:
            adapter = get_adapter("http")
            fetched = adapter.fetch(sensor)
        except Exception:
            failure_count += 1
            logger.exception(
                "Position fetch failed for sensor %s", getattr(sensor, "id", "?")
            )
            continue

        for vehicle_id, payload in fetched:
            if vehicle_id in in_service_vehicle_ids:
                readings.append((vehicle_id, payload))

    if readings:
        try:
            MqttPublisher().publish_batch(readings)
        except Exception:
            failure_count += 1
            logger.exception("Failed to publish fetched positions batch")

    return (
        f"fetch_positions: polled {sensor_count} sensors, "
        f"{failure_count} failures, published {len(readings)} positions"
    )


@shared_task(queue="realtime_engine")
def process_position_update(run_id: str, vehicle_id: str) -> None:
    """Run server-side producers and detection for a position update.

    Called by the MQTT callback after the position hash has been written to
    Redis. Only run_id and vehicle_id cross the queue — the task re-reads the
    latest ``vehicle:<id>:position`` from Redis so the work is idempotent and
    last-write-wins. No retries (a retried tick is stale; the next ping
    recovers).
    """
    from runs.domain.telemetry import keys, position

    # Step 1: produce server-side stop status (real map-matching).
    computed_stop_status = None
    try:
        from runs.domain.progression.producer import produce_stop_status
        computed_stop_status = produce_stop_status(run_id, vehicle_id)
    except Exception:
        logger.exception(
            "stop-status production failed for vehicle %s run %s",
            vehicle_id,
            run_id,
        )

    # Step 2: re-feed server-computed stop status into the completion detector.
    # RunCompletedDetector requires leaf="progression" + current_status/stop_id.
    if computed_stop_status:
        try:
            from runs.domain.detection.dispatch import detect_from_telemetry
            detect_from_telemetry(run_id, vehicle_id, "progression", computed_stop_status)
        except Exception:
            logger.exception(
                "progression detection failed for vehicle %s run %s",
                vehicle_id,
                run_id,
            )

    # Step 3: compute and cache the stop-time-updates projection.
    try:
        from runs.domain.progression.stop_times import produce_stop_times
        produce_stop_times(run_id, vehicle_id)
    except Exception:
        logger.exception(
            "stop-time-updates production failed for vehicle %s run %s",
            vehicle_id,
            run_id,
        )

    # Step 4: position-leaf detection (RunStartedDetector etc.).
    # Re-read the latest position from Redis — equivalent to passing the
    # original MQTT data since position is last-write-wins and speed survives
    # the validate_for_write → from_redis round-trip as a typed float.
    try:
        raw_position = redis_client.hgetall(keys.position_key(vehicle_id))
        if raw_position:
            latest_position = position.from_redis(raw_position)
            from runs.domain.detection.dispatch import detect_from_telemetry
            detect_from_telemetry(run_id, vehicle_id, "position", latest_position)
    except Exception:
        logger.exception(
            "position detection failed for vehicle %s run %s",
            vehicle_id,
            run_id,
        )
