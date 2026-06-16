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
