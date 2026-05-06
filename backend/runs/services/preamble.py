from feed.models import Feed, Trip, Route
from operations.models import Vehicle


class RunValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("Run request validation failed")


class RunInitializationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def trip_exists(trip_id: str | None, feed: Feed | None = None) -> bool:
    if not trip_id:
        return False
    feed = feed or Feed.objects.filter(is_current=True).first()
    if not feed:
        return False
    return Trip.objects.filter(feed=feed, trip_id=trip_id).exists()


def route_exists(route_id: str | None, feed: Feed | None = None) -> bool:
    if not route_id:
        return False
    feed = feed or Feed.objects.filter(is_current=True).first()
    if not feed:
        return False
    return Route.objects.filter(feed=feed, route_id=route_id).exists()


def vehicle_exists(vehicle_id: str | None) -> bool:
    if not vehicle_id:
        return False
    return Vehicle.objects.filter(id=vehicle_id).exists()


class RunRequestValidator:
    def validate(self, payload) -> dict:
        errors = {}
        current_feed = Feed.objects.filter(is_current=True).first()

        trip_id = payload.get("trip_id")
        route_id = payload.get("route_id")
        vehicle_id = payload.get("vehicle_id")

        if not current_feed:
            errors["feed"] = "A current feed is required"

        if not trip_id:
            errors["trip_id"] = "A trip is required"
        elif current_feed and not trip_exists(trip_id, current_feed):
            errors["trip_id"] = "The trip does not exist"

        if not route_id:
            errors["route_id"] = "A route is required"
        elif current_feed and not route_exists(route_id, current_feed):
            errors["route_id"] = "The route does not exist"

        if not vehicle_id:
            errors["vehicle_id"] = "A vehicle is required"
        elif not vehicle_exists(vehicle_id):
            errors["vehicle_id"] = "The vehicle does not exist"

        if errors:
            raise RunValidationError(errors)

        return payload


class RunRequestInitializer:
    def initialize(self, payload) -> str:
        # Create a new run in the database with status REQUESTED
        # and return the run ID.
        # This is a placeholder implementation. You would need to implement
        # the actual logic to create a run in your database.
        return "new_run_id"
