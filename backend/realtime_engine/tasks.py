from celery import shared_task
from messages.publisher import publish_event
from typing import Any
from operations.models import Vehicle, Operator
from runs.models import Run
from runs.services import RunLifecycleService, RunProgressService
from feed.models import Feed, Trip
import redis
import os

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"), port=os.getenv("REDIS_PORT", 6379), db=0
)


@shared_task(queue="realtime_engine")
def hello_world() -> None:
    print("Hello, world!")


@shared_task(queue="realtime_engine")
def manage_run_event(event: str, payload: dict[str, Any]) -> None:
    pass


@shared_task(queue="realtime_engine")
def validate_run(run_data: dict[str, Any]) -> bool:
    # Validation against the system state in Redis.
    # Verify that:
    # 1. the vehicle is not currently in another run,
    # 2. the trip_id is not already being executed by another run
    return True  # Placeholder for actual validation logic. Always returns True for now.


@shared_task(queue="realtime_engine")
def initialize_run(run_data: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Initializes a run in the database and the system state (Redis).

    Args:
        run_data (dict): Run request payload to initialize. Expected keys include
            ``vehicle_id``, ``operator_id``, ``route_id``, ``trip_id``,
            ``direction_id``, ``shape_id``, and ``schedule_relationship``.
    Returns:
        tuple[bool, str | None]: A tuple where the first value is ``True`` when the run was successfully initialized. The second value is the run ID on success, or ``None`` on failure.
    """
    try:
        run = Run.objects.create(
            vehicle_id=run_data.get("vehicle_id"),
            operator_id=run_data.get("operator_id"),
            route_id=run_data.get("route_id"),
            trip_id=run_data.get(
                "trip_id"
            ),  # Cuando no es SCHEDULED, alguien tiene que crear un nuevo trip_id
            direction_id=int(run_data.get("direction_id")),
            shape_id=run_data.get("shape_id"),
            schedule_relationship=run_data.get("schedule_relationship"),
            run_status="INITIALIZED",  # TODO: CONFIRMAR ESTADO ADECUADO
        )
        # Save run data (all) to Redis' "runs" key
        redis_client.hset(f"run:{run.id}", mapping=run_data)
        return (True, str(run.id))
    except Exception as e:
        publish_event(
            "RUN_INITIALIZATION_ERROR",
            {"error": str(e), **run_data},  # Error with payload
        )
        return (False, None)


@shared_task(queue="realtime_engine")
def register_run(run_data: dict[str, Any]) -> tuple[bool, str | None]:
    if not validate_run(run_data):
        publish_event("RUN_VALIDATION_FAILED", run_data)
        return (False, None)

    publish_event("RUN_VALIDATION_SUCCEEDED", run_data)
    initialization_ok, run_id = initialize_run(run_data)
    if initialization_ok:
        publish_event("RUN_INITIALIZATION_SUCCEEDED", run_data)
        return (True, run_id)

    publish_event("RUN_INITIALIZATION_FAILED", run_data)
    return (False, None)


@shared_task(queue="realtime_engine")
def start_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de inicio del run_data
    # Save run_id to Redis' runs:in_progress group
    # redis_client.sadd("runs:in_progress", run_data.get("run_id"))
    return True


@shared_task(queue="realtime_engine")
def end_run(run_data: dict[str, Any]) -> bool:
    # Transitions an IN_PROGRESS run to COMPLETED. Returns False if the run is missing, in a non-completable state, or an erorr occurs.
    run_id = run_data.get("run_id")
    if run_id in (None, ""):
        return False
    try:
        run = Run.objects.filter(id=run_id).first()
        if run is None:
            return False
        if run.run_status != "IN_PROGRESS":
            return False
        run.run_status = "COMPLETED"
        run.save(update_fields=["run_status"])
        return True
    except Exception as e:
        publish_event(
            "RUN_COMPLETION_ERROR",
            {"error": str(e), **run_data},
        )
        return False
