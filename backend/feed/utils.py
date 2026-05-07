from .models import Feed, Trip
from operations.models import Vehicle, Operator
from runs.models import Run


def validate_run_request_data(run_data) -> tuple[bool, str | None]:
    """
    Validate incoming run payload against system state and current GTFS feed.

    Args:
        run_data (dict): Run request payload to validate. Expected keys include
            ``vehicle_id``, ``operator_id``, ``route_id``, ``trip_id``,
            ``direction_id``, ``shape_id``, and ``schedule_relationship``.

    Returns:
        tuple[bool, str | None]: A tuple where the first value is ``True`` when
        the payload is valid. The second value is ``None`` on success, or an
        error code string on failure.

    Example:
        >>> run_data = {
        ...     "vehicle_id": "BUS-01",
        ...     "operator_id": "OP-10",
        ...     "route_id": "10",
        ...     "trip_id": "10_20260427_1",
        ...     "direction_id": "1",
        ...     "shape_id": "shape_10_1",
        ...     "schedule_relationship": "SCHEDULED",
        ... }
        >>> validate_run_request_data(run_data)
        (True, None)
    """
    feed = Feed.objects.filter(is_current=True).first()
    trip = Trip.objects.filter(feed=feed, trip_id=run_data.get("trip_id")).count()
    if run_data.get("schedule_relationship") == "SCHEDULED" and trip > 0:
        return (True, None)
    # Are all required fields present and non-empty?
    required = [
        "vehicle_id",
        "operator_id",
        "route_id",
        "trip_id",
        "direction_id",
        "shape_id",
        "schedule_relationship",
    ]
    if any(run_data.get(field) in (None, "") for field in required):
        return (False, "MISSING_REQUIRED_FIELDS")
    #  JSON often sends numbers as strings ("0" instead of 0). The database stores it as an integer, so we convert. If the value can't be converted (e.g. "abc"), reject.
    try:
        direction_id = int(run_data["direction_id"])
    except (TypeError, ValueError):
        return (False, "INVALID_DIRECTION_ID")
    if direction_id not in (0, 1):
        return (False, "INVALID_DIRECTION_ID")
    # Does the vehicle exist?
    if not Vehicle.objects.filter(id=run_data["vehicle_id"]).exists():
        return (False, "VEHICLE_NOT_FOUND")
    # Does the operator exist?
    if not Operator.objects.filter(id=run_data["operator_id"]).exists():
        return (False, "OPERATOR_NOT_FOUND")
    # Is the bus in another active run?
    if Run.objects.filter(
        vehicle_id=run_data["vehicle_id"],
        run_lifecycle_state="IN_PROGRESS",
    ).exists():
        return (False, "VEHICLE_ALREADY_IN_PROGRESS")
    # Is there a current GTFS Feed?
    feed = Feed.objects.filter(is_current=True).first()
    if feed is None:
        return (False, "CURRENT_FEED_NOT_FOUND")
    # Does the trip exist in the current GTFS feed?
    trip_exists = Trip.objects.filter(
        feed=feed,
        trip_id=run_data["trip_id"],
        route_id=run_data["route_id"],
        direction_id=direction_id,
        shape_id=run_data["shape_id"],
    ).exists()
    if not trip_exists:
        return (False, "TRIP_NOT_FOUND_IN_CURRENT_FEED")

    return (True, None)
