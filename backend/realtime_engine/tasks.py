"""Celery tasks for the realtime-engine worker: lifecycle events, staleness scanning, HTTP polling."""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils.timezone import now

from databus.redis_client import create_redis_client
from runs.services.lifecycle import RunLifecycleService

if TYPE_CHECKING:
    from operations.models import Sensor

logger = logging.getLogger(__name__)

redis_client = create_redis_client()


def _smembers(key: str) -> set[str]:
    """Read a Redis set as `set[str]`, narrowing away redis-py's shared Awaitable stub.

    `redis_client` here is always the synchronous, `decode_responses=True`
    client, but redis-py's `CoreCommands` mixin types every command
    `Awaitable[X] | X` since it's shared with the async client — this cast
    narrows to the sync branch that's actually returned.
    """
    return cast("set[str]", redis_client.smembers(key))


def _get(key: str) -> str | None:
    """Read a Redis string value, narrowing away redis-py's shared Awaitable stub."""
    return cast("str | None", redis_client.get(key))


def _hgetall(key: str) -> dict[str, str]:
    """Read a Redis hash as `dict[str, str]`, narrowing away redis-py's shared Awaitable stub."""
    return cast("dict[str, str]", redis_client.hgetall(key))


@shared_task(queue="realtime_engine")
def run_lifecycle_event(event: str, payload: dict[str, Any]) -> None:
    """Dispatch a lifecycle event to `RunLifecycleService`, logging benign re-fires as warnings."""
    from runs.domain.lifecycle import RunLifecycleEvents, target_state_for_event
    from runs.services.exceptions import RunLifecycleError

    service = RunLifecycleService()
    try:
        evt = RunLifecycleEvents(event)
    except ValueError:
        logger.error("Unknown lifecycle event: %s", event)
        return
    try:
        service.process_event(evt, payload)
    except RunLifecycleError as exc:
        # Detectors already gate on current run state before firing, but a
        # detection can still lose a race against an in-flight transition for
        # the same run (e.g. two position pings both see "Tracking" before the
        # first RUN_STARTED lands). When that happens the run has already
        # reached this event's target state by the time this dispatch runs —
        # a harmless no-op re-fire, not a real failure. Genuine invalid
        # transitions (target state unresolved/mismatched) still log loudly.
        target_state = target_state_for_event(evt)
        current_state = exc.errors.get("current_state")
        if target_state is not None and current_state == target_state.value:
            logger.warning(
                "Lifecycle event %s for run %s: no-op re-fire, run already %s",
                event,
                payload.get("run_id"),
                current_state,
            )
        else:
            logger.exception(
                "Lifecycle event %s failed for run %s", event, payload.get("run_id")
            )
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

    run_ids = _smembers("runs:tracking")
    fired = 0
    for run_id in run_ids:
        raw_last_seen = _get(f"runs:last_seen:{run_id}")
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


@shared_task(queue="realtime_engine", soft_time_limit=25)
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
    3. Pre-fetch filter: skip a sensor entirely -- never issue the HTTP call
       -- when its own ``equipment.vehicle`` is not in the in-service set (or
       the sensor has no equipment, or the equipment has no vehicle). This is
       what stops the task from paying the full HTTP cost of every ACTIVE
       sensor on every 10s tick regardless of whether anything behind it is
       actually in service; previously, e.g. 6 ACTIVE sensors pointed at a
       slow/unreachable host could occupy every worker slot and starve
       ``process_position_update``.

       CAVEAT (NavSat and similar fleet endpoints): some adapters can return
       readings for MANY vehicles from a single sensor's URL, not only the
       vehicle named by that sensor's own ``equipment.vehicle``. This
       pre-fetch filter only decides whether to CALL a given sensor -- it
       has no way to know what a fleet endpoint might actually return. A
       sensor whose own vehicle is out of service, but whose fleet endpoint
       would otherwise have served *other* in-service vehicles' positions,
       is now skipped entirely, and those vehicles' positions are missed via
       this sensor until it (or some other covering sensor) is in service
       again. Accepted trade-off -- see the commit message / task report for
       the reasoning.
    4. Fetch each remaining sensor's readings, keep only the ones for
       in-service vehicles (the *post*-fetch filter -- unaffected by the
       above; still required to handle the fleet-endpoint case), and publish
       the survivors on ``transit/vehicle/<id>/position``.

    Each sensor is fetched independently inside its own try/except so one
    failing source can't sink the rest of the poll. The task also carries a
    ``soft_time_limit`` so a single pathological source (e.g. a host that
    hangs on every request) can never hold a worker slot indefinitely: on
    ``SoftTimeLimitExceeded`` the sensor that was in flight is logged and the
    task returns early instead of propagating the exception.
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

    sensors = list(
        Sensor.objects.filter(
            status="ACTIVE",
            provides_position=True,
            source_type__in=["http", "both"],
        ).select_related("equipment__vehicle")
    )

    def _sensor_vehicle_id(sensor: "Sensor") -> str | None:
        """Resolve the vehicle id a sensor's equipment is currently assigned to."""
        equipment = getattr(sensor, "equipment", None)
        if equipment is None:
            return None
        vehicle_id = getattr(equipment, "vehicle_id", None)
        return str(vehicle_id) if vehicle_id is not None else None

    sensors_to_fetch = [
        sensor
        for sensor in sensors
        if (vid := _sensor_vehicle_id(sensor)) is not None
        and vid in in_service_vehicle_ids
    ]

    logger.info(
        "fetch_positions: %d active HTTP position sensor(s), %d have an "
        "in-service vehicle and will be fetched",
        len(sensors),
        len(sensors_to_fetch),
    )

    readings: list[tuple[str, dict]] = []
    failure_count = 0
    in_flight_sensor_id: object = None
    try:
        for sensor in sensors_to_fetch:
            in_flight_sensor_id = getattr(sensor, "id", "?")
            try:
                adapter = get_adapter("http")
                fetched = adapter.fetch(sensor)
            except SoftTimeLimitExceeded:
                # Never let the blanket `except Exception` below swallow
                # this -- it must propagate to the outer handler so the loop
                # actually stops instead of moving on to the next sensor.
                raise
            except Exception:
                failure_count += 1
                logger.exception(
                    "Position fetch failed for sensor %s", in_flight_sensor_id
                )
                continue

            for vehicle_id, payload in fetched:
                if vehicle_id in in_service_vehicle_ids:
                    readings.append((vehicle_id, payload))
    except SoftTimeLimitExceeded:
        logger.warning(
            "fetch_positions hit its soft time limit while sensor %s was "
            "in flight (%d/%d sensors fetched before the limit); returning "
            "early without publishing",
            in_flight_sensor_id,
            len(readings),
            len(sensors_to_fetch),
        )
        return (
            f"fetch_positions: soft time limit exceeded while fetching "
            f"sensor {in_flight_sensor_id}; polled {len(sensors)} sensors, "
            f"{len(sensors_to_fetch)} eligible"
        )

    if readings:
        try:
            MqttPublisher().publish_batch(readings)
        except Exception:
            failure_count += 1
            logger.exception("Failed to publish fetched positions batch")

    return (
        f"fetch_positions: polled {len(sensors)} sensors, "
        f"{len(sensors_to_fetch)} fetched, "
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
        raw_position = _hgetall(keys.position_key(vehicle_id))
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
