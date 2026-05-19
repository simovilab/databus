import logging
import os
from datetime import datetime, timezone
from typing import Any

import redis
from celery import shared_task
from django.utils.timezone import now

from runs.services.lifecycle import RunLifecycleService
from runs.domain.states import RunLifecycleStates

logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)

TELEMETRY_GRACE_S = 60
TELEMETRY_EXPIRY_S = 300


@shared_task(queue="realtime_engine")
def run_lifecycle_event(event: str, payload: dict[str, Any]) -> None:
    from runs.domain.events import RunLifecycleEvents

    service = RunLifecycleService()
    try:
        evt = RunLifecycleEvents(event)
    except ValueError:
        logger.error("Unknown lifecycle event: %s", event)
        return
    try:
        service.process_event(evt, payload)
    except Exception:
        logger.exception("Lifecycle event %s failed for run %s", event, payload.get("run_id"))


@shared_task(queue="realtime_engine")
def scan_stale_runs() -> str:
    """
    Scans runs:tracking every 30 s.
    - Grace exceeded (>60s, ≤300s) while IN_PROGRESS → RUN_TRACKING_LOST
    - Expiry exceeded (>300s) while NO_SIGNAL → RUN_TRACKING_EXPIRED
    """
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
        run_state = redis_client.hget(f"run:{run_id}", "run_lifecycle_state")

        payload = {
            "run_id": run_id,
            "last_seen_at": raw_last_seen,
            "actor_role": "system",
        }

        if (
            TELEMETRY_GRACE_S < staleness <= TELEMETRY_EXPIRY_S
            and run_state == RunLifecycleStates.IN_PROGRESS.value
        ):
            run_lifecycle_event.delay("run_tracking_lost", payload)
            fired += 1
        elif (
            staleness > TELEMETRY_EXPIRY_S
            and run_state == RunLifecycleStates.NO_SIGNAL.value
        ):
            run_lifecycle_event.delay("run_tracking_expired", payload)
            fired += 1

    return f"scan_stale_runs: checked {len(run_ids)} runs, fired {fired} events"
