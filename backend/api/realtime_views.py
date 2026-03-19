"""
MBTA-style JSON:API endpoints for real-time vehicle positions and predictions.

Data sources:
  /api/realtime/vehicles/    — reads live from Redis state
  /api/realtime/predictions/ — parses the trip_updates.json feed file built by publisher
"""
import json
import os
from datetime import datetime, timezone

import redis
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from gtfs.models import Stop

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "state"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=int(os.environ.get("REDIS_DB", "0")),
            decode_responses=True,
        )
    return _redis_client


def _read_all_vehicles(r):
    """Return a list of {run, vehicle, position, progression, occupancy} dicts."""
    vehicles = []
    for run_key in r.smembers("runs:in_progress"):
        run = r.hgetall(run_key)
        vehicle_id = run.get("vehicle")
        if not vehicle_id:
            continue
        vehicles.append(
            {
                "run": run,
                "vehicle": r.hgetall(f"vehicle:{vehicle_id}:data"),
                "position": r.hgetall(f"vehicle:{vehicle_id}:position"),
                "progression": r.hgetall(f"vehicle:{vehicle_id}:progression"),
                "occupancy": r.hgetall(f"vehicle:{vehicle_id}:occupancy"),
            }
        )
    return vehicles


def _vehicle_to_jsonapi(entry):
    """Convert a Redis vehicle bundle to a JSON:API resource object."""
    run = entry["run"]
    vehicle = entry["vehicle"]
    position = entry["position"]
    progression = entry["progression"]
    occupancy = entry["occupancy"]

    vehicle_id = vehicle.get("id", "")
    stop_id = progression.get("stop_id", "")

    ts = position.get("timestamp")
    updated_at = (
        datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if ts else None
    )

    current_stop_sequence = progression.get("current_stop_sequence")
    occupancy_percentage = occupancy.get("occupancy_percentage")

    return {
        "id": vehicle_id,
        "type": "vehicle",
        "attributes": {
            "label": vehicle.get("label"),
            "latitude": float(position["latitude"]) if position.get("latitude") else None,
            "longitude": float(position["longitude"]) if position.get("longitude") else None,
            "speed": float(position["speed"]) if position.get("speed") else None,
            "bearing": float(position["bearing"]) if position.get("bearing") else None,
            "current_status": progression.get("current_status"),
            "current_stop_sequence": int(current_stop_sequence) if current_stop_sequence else None,
            "stop_id": stop_id,
            "updated_at": updated_at,
            "occupancy_status": occupancy.get("occupancy_status"),
            "occupancy_percentage": int(occupancy_percentage) if occupancy_percentage else None,
        },
        "relationships": {
            "trip": {"data": {"id": run.get("trip_id", ""), "type": "trip"}},
            "route": {"data": {"id": run.get("route_id", ""), "type": "route"}},
            "stop": {"data": {"id": stop_id, "type": "stop"}},
        },
    }


class RealtimeVehiclesView(APIView):
    """
    GET /api/realtime/vehicles/

    Returns all in-progress vehicles from Redis as JSON:API resources.

    Filters (query params):
      ?filter[route]={routeId}
      ?filter[trip]={tripId}
      ?filter[vehicle]={vehicleId}
    """

    def get(self, request):
        r = _get_redis()
        route_filter = request.query_params.get("filter[route]")
        trip_filter = request.query_params.get("filter[trip]")
        vehicle_filter = request.query_params.get("filter[vehicle]")

        results = []
        for entry in _read_all_vehicles(r):
            run = entry["run"]
            vehicle = entry["vehicle"]
            if route_filter and run.get("route_id") != route_filter:
                continue
            if trip_filter and run.get("trip_id") != trip_filter:
                continue
            if vehicle_filter and vehicle.get("id") != vehicle_filter:
                continue
            results.append(_vehicle_to_jsonapi(entry))

        return Response({"data": results})


def _load_trip_updates():
    """Load the trip_updates.json file built by the publisher."""
    feed_path = settings.BASE_DIR / "feed" / "files" / "trip_updates.json"
    with open(feed_path) as f:
        return json.load(f)


def _entities_to_predictions(entities, trip_filter=None, stop_filter=None):
    """Convert GTFS-RT entities to JSON:API prediction resources."""
    predictions = []
    stop_ids = set()

    for entity in entities:
        trip_update = entity.get("trip_update", {})
        trip = trip_update.get("trip", {})
        vehicle = trip_update.get("vehicle", {})

        trip_id = trip.get("trip_id", "")
        route_id = trip.get("route_id", "")
        direction_id = trip.get("direction_id", 0)
        vehicle_id = vehicle.get("id", "")

        if trip_filter and trip_id != trip_filter:
            continue

        for stu in trip_update.get("stop_time_update", []):
            stop_id = stu.get("stop_id", "")
            stop_sequence = stu.get("stop_sequence")

            if stop_filter and stop_id != stop_filter:
                continue

            arrival = stu.get("arrival", {})
            departure = stu.get("departure", {})
            arrival_ts = arrival.get("time")
            departure_ts = departure.get("time")
            uncertainty = arrival.get("uncertainty", 0)

            predictions.append(
                {
                    "id": f"prediction-{stop_id}-{trip_id}-{stop_sequence}",
                    "type": "prediction",
                    "attributes": {
                        "arrival_time": (
                            datetime.fromtimestamp(arrival_ts, tz=timezone.utc).isoformat()
                            if arrival_ts
                            else None
                        ),
                        "departure_time": (
                            datetime.fromtimestamp(departure_ts, tz=timezone.utc).isoformat()
                            if departure_ts
                            else None
                        ),
                        "stop_sequence": stop_sequence,
                        "stop_id": stop_id,
                        "direction_id": direction_id,
                        "schedule_relationship": "SCHEDULED",
                        "uncertainty": uncertainty,
                    },
                    "relationships": {
                        "stop": {"data": {"id": stop_id, "type": "stop"}},
                        "trip": {"data": {"id": trip_id, "type": "trip"}},
                        "route": {"data": {"id": route_id, "type": "route"}},
                        "vehicle": {"data": {"id": vehicle_id, "type": "vehicle"}},
                    },
                }
            )
            stop_ids.add(stop_id)

    return predictions, stop_ids


def _build_included_stops(stop_ids):
    """Fetch stops from PostgreSQL and return JSON:API included resources."""
    included = []
    for stop in Stop.objects.filter(stop_id__in=stop_ids).values(
        "stop_id", "stop_name", "stop_lat", "stop_lon"
    ):
        included.append(
            {
                "id": stop["stop_id"],
                "type": "stop",
                "attributes": {
                    "name": stop["stop_name"],
                    "latitude": float(stop["stop_lat"]) if stop["stop_lat"] else None,
                    "longitude": float(stop["stop_lon"]) if stop["stop_lon"] else None,
                },
            }
        )
    return included


class RealtimePredictionsView(APIView):
    """
    GET /api/realtime/predictions/

    Parses the publisher's trip_updates.json feed and re-exposes it as JSON:API.

    Filters (query params):
      ?filter[trip]={tripId}   — predictions for a specific trip
      ?filter[stop]={stopId}   — next predictions at a given stop across all trips
      ?include=stop            — sideload stop name/coordinates in 'included'
    """

    def get(self, request):
        trip_filter = request.query_params.get("filter[trip]")
        stop_filter = request.query_params.get("filter[stop]")
        include = request.query_params.get("include", "")

        try:
            feed = _load_trip_updates()
        except (FileNotFoundError, json.JSONDecodeError):
            return Response(
                {"data": [], "errors": [{"detail": "Feed not available"}]},
                status=503,
            )

        predictions, stop_ids = _entities_to_predictions(
            feed.get("entity", []), trip_filter, stop_filter
        )

        response_data = {"data": predictions}
        if "stop" in include.split(","):
            response_data["included"] = _build_included_stops(stop_ids)

        return Response(response_data)
