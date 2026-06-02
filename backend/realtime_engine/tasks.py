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
def run_progress_event(event: str, payload: dict[str, Any]) -> None:
    from runs.domain.progress import RunProgressEvents
    from runs.services.progress import RunProgressService

    service = RunProgressService()
    try:
        evt = RunProgressEvents(event)
    except ValueError:
        logger.error("Unknown progress event: %s", event)
        return
    try:
        service.process_event(evt, payload)
    except Exception:
        logger.exception(
            "Progress event %s failed for run %s", event, payload.get("run_id")
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
