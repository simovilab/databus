"""
JSON:API endpoints for GTFS Schedule resources.

Endpoint map:
  GET /api/schedule/routes/          — filter[type], filter[stop]
  GET /api/schedule/stops/           — filter[route], filter[id], filter[location_type]
  GET /api/schedule/trips/           — filter[route], filter[direction_id], filter[service]
  GET /api/schedule/shapes/          — filter[route]
  GET /api/schedule/schedules/       — requires filter[trip], filter[stop], or filter[route]
  GET /api/schedule/services/        — filter[id], filter[route]
  GET /api/schedule/route-patterns/  — filter[route], filter[direction_id]

All responses follow JSON:API format: {"data": [...]}
"""
import json

from rest_framework.response import Response
from rest_framework.views import APIView

from gtfs.models import Calendar, GeoShape, Route, RouteStop, Stop, StopTime, Trip


# ---------------------------------------------------------------------------
# Resource serializers (model instance → JSON:API dict)
# ---------------------------------------------------------------------------


def _route_to_jsonapi(route):
    return {
        "id": route.route_id,
        "type": "route",
        "attributes": {
            "short_name": route.route_short_name,
            "long_name": route.route_long_name,
            "description": route.route_desc,
            "type": route.route_type,
            "color": route.route_color,
            "text_color": route.route_text_color,
            "sort_order": route.route_sort_order,
        },
    }


def _stop_to_jsonapi(stop):
    return {
        "id": stop.stop_id,
        "type": "stop",
        "attributes": {
            "name": stop.stop_name,
            "description": stop.stop_desc,
            "latitude": float(stop.stop_lat) if stop.stop_lat is not None else None,
            "longitude": float(stop.stop_lon) if stop.stop_lon is not None else None,
            "location_type": stop.location_type,
            "wheelchair_boarding": stop.wheelchair_boarding,
        },
    }


def _trip_to_jsonapi(trip):
    return {
        "id": trip.trip_id,
        "type": "trip",
        "attributes": {
            "headsign": trip.trip_headsign,
            "short_name": trip.trip_short_name,
            "direction_id": trip.direction_id,
            "wheelchair_accessible": trip.wheelchair_accessible,
            "bikes_allowed": trip.bikes_allowed,
        },
        "relationships": {
            "route": {"data": {"id": trip.route_id, "type": "route"}},
            "service": {"data": {"id": trip.service_id, "type": "service"}},
            "shape": {
                "data": {"id": trip.shape_id, "type": "shape"}
                if trip.shape_id
                else None
            },
        },
    }


def _shape_to_jsonapi(shape):
    try:
        geometry = json.loads(shape.geometry.geojson)
    except Exception:
        geometry = None
    return {
        "id": shape.shape_id,
        "type": "shape",
        "attributes": {
            "geometry": geometry,
            "name": shape.shape_name,
            "from": shape.shape_from,
            "to": shape.shape_to,
        },
    }


def _schedule_to_jsonapi(stoptime):
    return {
        "id": f"schedule-{stoptime.trip_id}-{stoptime.stop_sequence}",
        "type": "schedule",
        "attributes": {
            "arrival_time": (
                stoptime.arrival_time.strftime("%H:%M:%S")
                if stoptime.arrival_time
                else None
            ),
            "departure_time": (
                stoptime.departure_time.strftime("%H:%M:%S")
                if stoptime.departure_time
                else None
            ),
            "stop_sequence": stoptime.stop_sequence,
            "timepoint": stoptime.timepoint,
            "pickup_type": stoptime.pickup_type,
            "drop_off_type": stoptime.drop_off_type,
        },
        "relationships": {
            "stop": {"data": {"id": stoptime.stop_id, "type": "stop"}},
            "trip": {"data": {"id": stoptime.trip_id, "type": "trip"}},
        },
    }


def _service_to_jsonapi(calendar):
    day_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    valid_days = [i for i, day in enumerate(day_names) if getattr(calendar, day, False)]
    return {
        "id": calendar.service_id,
        "type": "service",
        "attributes": {
            "start_date": (
                calendar.start_date.isoformat() if calendar.start_date else None
            ),
            "end_date": (
                calendar.end_date.isoformat() if calendar.end_date else None
            ),
            "valid_days": valid_days,
        },
    }


def _route_pattern_to_jsonapi(route_id, direction_id, shape_id, representative_trip_id):
    pattern_id = f"route-pattern-{route_id}-{direction_id}"
    if shape_id:
        pattern_id += f"-{shape_id}"
    return {
        "id": pattern_id,
        "type": "route_pattern",
        "attributes": {
            "direction_id": direction_id,
        },
        "relationships": {
            "route": {"data": {"id": route_id, "type": "route"}},
            "representative_trip": {
                "data": {"id": representative_trip_id, "type": "trip"}
            },
        },
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class RoutesView(APIView):
    """
    GET /api/schedule/routes/

    Filters:
      ?filter[type]={routeType}   — 0=tram, 1=subway, 2=rail, 3=bus, 4=ferry
      ?filter[stop]={stopId}      — routes serving this stop
    """

    def get(self, request):
        route_type_filter = request.query_params.get("filter[type]")
        stop_filter = request.query_params.get("filter[stop]")

        qs = Route.objects.filter(feed__is_current=True)

        if route_type_filter is not None:
            qs = qs.filter(route_type=route_type_filter)

        if stop_filter:
            route_ids = RouteStop.objects.filter(
                feed__is_current=True, stop_id=stop_filter
            ).values_list("route_id", flat=True)
            qs = qs.filter(route_id__in=route_ids)

        return Response({"data": [_route_to_jsonapi(r) for r in qs]})


class StopsView(APIView):
    """
    GET /api/schedule/stops/

    Filters:
      ?filter[route]={routeId}          — stops served by this route
      ?filter[id]={stopId}              — exact stop ID match
      ?filter[location_type]={type}     — 0=stop, 1=station, 2=entrance
    """

    def get(self, request):
        route_filter = request.query_params.get("filter[route]")
        id_filter = request.query_params.get("filter[id]")
        location_type_filter = request.query_params.get("filter[location_type]")

        qs = Stop.objects.filter(feed__is_current=True)

        if route_filter:
            stop_ids = RouteStop.objects.filter(
                feed__is_current=True, route_id=route_filter
            ).values_list("stop_id", flat=True)
            qs = qs.filter(stop_id__in=stop_ids)

        if id_filter:
            qs = qs.filter(stop_id=id_filter)

        if location_type_filter is not None:
            qs = qs.filter(location_type=location_type_filter)

        return Response({"data": [_stop_to_jsonapi(s) for s in qs]})


class TripsView(APIView):
    """
    GET /api/schedule/trips/

    Filters:
      ?filter[route]={routeId}
      ?filter[direction_id]={0|1}
      ?filter[service]={serviceId}
    """

    def get(self, request):
        route_filter = request.query_params.get("filter[route]")
        direction_filter = request.query_params.get("filter[direction_id]")
        service_filter = request.query_params.get("filter[service]")

        qs = Trip.objects.filter(feed__is_current=True)

        if route_filter:
            qs = qs.filter(route_id=route_filter)
        if direction_filter is not None:
            qs = qs.filter(direction_id=direction_filter)
        if service_filter:
            qs = qs.filter(service_id=service_filter)

        return Response({"data": [_trip_to_jsonapi(t) for t in qs]})


class ShapesView(APIView):
    """
    GET /api/schedule/shapes/

    Filters:
      ?filter[route]={routeId}   — shapes used by trips on this route
    """

    def get(self, request):
        route_filter = request.query_params.get("filter[route]")

        qs = GeoShape.objects.filter(feed__is_current=True)

        if route_filter:
            shape_ids = (
                Trip.objects.filter(feed__is_current=True, route_id=route_filter)
                .distinct()
                .values_list("shape_id", flat=True)
            )
            qs = qs.filter(shape_id__in=shape_ids)

        return Response({"data": [_shape_to_jsonapi(s) for s in qs]})


class SchedulesView(APIView):
    """
    GET /api/schedule/schedules/

    At least one of filter[trip], filter[stop], or filter[route] is required.

    Filters:
      ?filter[trip]={tripId}
      ?filter[stop]={stopId}
      ?filter[route]={routeId}
      ?filter[direction_id]={0|1}
      ?filter[min_time]={HH:MM:SS}
      ?filter[max_time]={HH:MM:SS}
    """

    def get(self, request):
        trip_filter = request.query_params.get("filter[trip]")
        stop_filter = request.query_params.get("filter[stop]")
        route_filter = request.query_params.get("filter[route]")
        direction_filter = request.query_params.get("filter[direction_id]")
        min_time = request.query_params.get("filter[min_time]")
        max_time = request.query_params.get("filter[max_time]")

        if not trip_filter and not stop_filter and not route_filter:
            return Response(
                {
                    "errors": [
                        {
                            "detail": "At least one of filter[trip], filter[stop], or filter[route] is required."
                        }
                    ]
                },
                status=400,
            )

        qs = StopTime.objects.filter(feed__is_current=True)

        if trip_filter:
            qs = qs.filter(trip_id=trip_filter)
        if stop_filter:
            qs = qs.filter(stop_id=stop_filter)
        if route_filter:
            trip_ids = Trip.objects.filter(
                feed__is_current=True, route_id=route_filter
            ).values_list("trip_id", flat=True)
            qs = qs.filter(trip_id__in=trip_ids)
        if direction_filter is not None:
            trip_ids = Trip.objects.filter(
                feed__is_current=True, direction_id=direction_filter
            ).values_list("trip_id", flat=True)
            qs = qs.filter(trip_id__in=trip_ids)
        if min_time:
            qs = qs.filter(departure_time__gte=min_time)
        if max_time:
            qs = qs.filter(departure_time__lte=max_time)

        return Response({"data": [_schedule_to_jsonapi(s) for s in qs]})


class ServicesView(APIView):
    """
    GET /api/schedule/services/

    Filters:
      ?filter[id]={serviceId}
      ?filter[route]={routeId}   — services that operate on this route
    """

    def get(self, request):
        id_filter = request.query_params.get("filter[id]")
        route_filter = request.query_params.get("filter[route]")

        qs = Calendar.objects.filter(feed__is_current=True)

        if id_filter:
            qs = qs.filter(service_id=id_filter)

        if route_filter:
            service_ids = (
                Trip.objects.filter(feed__is_current=True, route_id=route_filter)
                .distinct()
                .values_list("service_id", flat=True)
            )
            qs = qs.filter(service_id__in=service_ids)

        return Response({"data": [_service_to_jsonapi(s) for s in qs]})


class RoutePatternsView(APIView):
    """
    GET /api/schedule/route-patterns/

    A route pattern is a unique (route_id, direction_id, shape_id) combination.
    Returns one resource per distinct pattern with a representative trip.

    Filters:
      ?filter[route]={routeId}
      ?filter[direction_id]={0|1}
    """

    def get(self, request):
        route_filter = request.query_params.get("filter[route]")
        direction_filter = request.query_params.get("filter[direction_id]")

        qs = Trip.objects.filter(feed__is_current=True)

        if route_filter:
            qs = qs.filter(route_id=route_filter)
        if direction_filter is not None:
            qs = qs.filter(direction_id=direction_filter)

        seen = set()
        patterns = []
        for trip in qs:
            key = (trip.route_id, trip.direction_id, trip.shape_id)
            if key not in seen:
                seen.add(key)
                patterns.append(
                    _route_pattern_to_jsonapi(
                        trip.route_id, trip.direction_id, trip.shape_id, trip.trip_id
                    )
                )

        return Response({"data": patterns})
