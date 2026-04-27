from celery import shared_task
from messages.publish import databus_event
from typing import Any
from datetime import date, datetime
from schedule_engine.models import Vehicle, Operator, Run
from feed.models import Feed, Trip


@shared_task(queue="realtime_engine")
def hello_world() -> None:
    print("Hello, world!")


@shared_task(queue="realtime_engine")
def initialize_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de inicialización del run_data
    return True


@shared_task(queue="realtime_engine")
def register_run(run_data: dict[str, Any]) -> tuple[bool, str | None]:
    validation_result = validate_run(run_data)
    if validation_result:
        databus_event("RUN_VALIDATION_SUCCEEDED", run_data)
        intialization_result = initialize_run(run_data)
        if intialization_result:
            databus_event("RUN_INITIALIZATION_SUCCEEDED", run_data)
            return (True, "94268469")
        else:
            databus_event("RUN_INITIALIZATION_FAILED", run_data)
            return (False, None)
    else:
        databus_event("RUN_VALIDATION_FAILED", run_data)
        return (False, None)


@shared_task(queue="realtime_engine")
def start_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de inicio del run_data
    return True


@shared_task(queue="realtime_engine")
def end_run(run_data: dict[str, Any]) -> bool:
    # Aquí iría la lógica de finalización del run_data
    return True

@shared_task(queue="realtime_engine")
def validate_run(run_data: dict[str, Any]) -> bool:
# Are all required fields present and non-empty?
    required = [
        "vehicle_id",
        "operator_id",
        "route_id",
        "trip_id",
        "direction_id",
        "shape_id",
        "start_date",
        "start_time",
        "schedule_relationship"
    ]
    if any(run_data.get(field) in (None, "") for field in required):
        return False
#  JSON often sends numbers as strings ("0" instead of 0). The database stores it as an integer, so we convert. If the value can't be converted (e.g. "abc"), reject.
    try:
        direction_id = int(run_data["direction_id"])
    except (TypeError, ValueError):
        return False
# Is the date today? (quiza inncesario)
    try:
        submitted_date = datetime.strptime(run_data["start_date"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    if submitted_date != date.today():
        return False
# Does the vehicle exist?
    if not Vehicle.objects.filter(id=run_data["vehicle_id"]).exists():
        return False
# Does the operator exist?
    if not Operator.objects.filter(id=run_data["operator_id"]).exists():
        return False
# Is the bus in another active run?
    if Run.objects.filter(
        vehicle_id=run_data["vehicle_id"],
        run_status="IN_PROGRESS",
    ).exists():
        return False
# Is there a current GTFS Feed
    feed = Feed.objects.filter(is_current=True).first()
    if feed is None:
        return False
# Does the trip exist in the current GTFS feed?
    trip_exists = Trip.objects.filter(
        feed=feed,
        trip_id=run_data["trip_id"],
        route_id=run_data["route_id"],
        direction_id=direction_id,
        shape_id=run_data["shape_id"],
    ).exists()
    if not trip_exists:
        return False

    return True
