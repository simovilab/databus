"""Dispatch: turn telemetry / staleness into fired lifecycle events.

Two layers:

* **Pure planners** (``plan_telemetry_events`` / ``plan_scan_events``) decide which
  events to fire given the current state and a message. No I/O — unit-testable.
* **Impure wrappers** (``detect_from_telemetry`` / ``detect_from_scan``) read run
  state from Redis, seed the few preconditions the lifecycle guards depend on, and
  queue the resulting events onto the lifecycle Celery task.

``mqtt.py`` and ``scan_stale_runs`` call only the wrappers; they hold no detection
logic of their own.
"""

from typing import Any, cast

from django.utils.timezone import now

from databus.redis_client import create_redis_client
from runs.domain.detection.result import DetectionResult
from runs.domain.detection import registry

r = create_redis_client()

# Lifecycle events whose guard (``is_vehicle_tracked``) requires the run to
# already be in ``runs:tracking``. The arrival of telemetry is precisely the
# signal that justifies membership, so the dispatcher seeds it before firing —
# mirroring the original inline behavior while keeping detectors pure.
_TRACKING_SEED_EVENTS = {"run_tracking_started", "run_tracking_restored"}


# ---------------------------------------------------------------------------
# Pure planners
# ---------------------------------------------------------------------------


def plan_telemetry_events(
    lifecycle_state: str | None,
    leaf: str,
    data: dict[str, Any],
    base_payload: dict[str, Any],
    detectors: list[Any] = registry.TELEMETRY_DETECTORS,
) -> list[DetectionResult]:
    """Plan at most one event per FSM for a telemetry message."""
    results: list[DetectionResult] = []
    fired_fsms: set[str] = set()
    for detector in detectors:
        if detector.fsm in fired_fsms:
            continue
        if lifecycle_state is None:
            continue
        result = detector.detect(lifecycle_state, leaf, data, base_payload)
        if result is not None:
            results.append(result)
            fired_fsms.add(result.fsm)
    return results


def plan_scan_events(
    lifecycle_state: str | None,
    staleness_s: float,
    payload: dict[str, Any],
    detectors: list[Any] = registry.PERIODIC_DETECTORS,
) -> list[DetectionResult]:
    """Plan at most one lifecycle event for a staleness scan tick."""
    if lifecycle_state is None:
        return []
    for detector in detectors:
        result = detector.detect(lifecycle_state, staleness_s, payload)
        if result is not None:
            return [result]
    return []


# ---------------------------------------------------------------------------
# Impure wrappers
# ---------------------------------------------------------------------------


def _fire(result: DetectionResult, base_payload: dict[str, Any]) -> None:
    from realtime_engine.tasks import run_lifecycle_event

    payload = {**base_payload, **result.extra_payload}
    if result.event in _TRACKING_SEED_EVENTS:
        r.sadd("runs:tracking", base_payload["run_id"])
    run_lifecycle_event.delay(result.event, payload)


def detect_from_telemetry(
    run_id: str, vehicle_id: str, leaf: str, data: dict[str, Any]
) -> None:
    """Evaluate telemetry detectors for one message and queue any fired lifecycle events."""
    # r has decode_responses=True, so hget really returns str | None; cast narrows
    # away the Awaitable branch that redis-py's shared sync/async stub attaches.
    lifecycle_state = cast("str | None", r.hget(f"run:{run_id}", "run_lifecycle_state"))
    if not lifecycle_state:
        return

    base_payload = {
        "run_id": run_id,
        "vehicle_id": vehicle_id,
        "last_seen_at": now().isoformat(),
        **data,
    }
    for result in plan_telemetry_events(lifecycle_state, leaf, data, base_payload):
        _fire(result, base_payload)


def detect_from_scan(run_id: str, staleness_s: float, raw_last_seen: str) -> int:
    """Evaluate periodic detectors for one run; returns number of events fired."""
    lifecycle_state = cast("str | None", r.hget(f"run:{run_id}", "run_lifecycle_state"))
    base_payload = {
        "run_id": run_id,
        "last_seen_at": raw_last_seen,
        "actor_role": "system",
    }
    fired = 0
    for result in plan_scan_events(lifecycle_state, staleness_s, base_payload):
        _fire(result, base_payload)
        fired += 1
    return fired
