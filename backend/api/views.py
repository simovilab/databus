"""DRF views for the api app: operations/run resources, GTFS Schedule resources, and run lifecycle endpoints."""

from django.conf import settings
from django.http import FileResponse, HttpRequest
from django.contrib.auth import authenticate
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.views import SpectacularRedocView
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from runs.services.exceptions import RunLifecycleError
from runs.services.lifecycle import RunLifecycleService
from runs.domain.lifecycle import RunLifecycleEvents
from runs.domain.lifecycle import RunLifecycleStates
from operations.models import (
    Vehicle,
    Operator,
    Company,
    DataProvider,
    Equipment,
    EquipmentLog,
)
from runs.models import (
    Run,
    RunLifecycleTransition,
    Position,
    VehicleStopStatus,
    CongestionLevel,
    OccupancyStatus,
)
from feed.models import (
    Feed,
    Agency,
    Trip,
    Stop,
    Route,
    Calendar,
    CalendarDate,
    StopTime,
    RouteStop,
    Shape,
    GeoShape,
    FareAttribute,
    FareRule,
    FeedInfo,
    TripTime,
)
from .serializers import (
    CompanySerializer,
    DataProviderSerializer,
    VehicleSerializer,
    EquipmentSerializer,
    EquipmentLogSerializer,
    OperatorSerializer,
    CreateRunSerializer,
    RunUpdateSerializer,
    PositionSerializer,
    VehicleStopStatusSerializer,
    CongestionLevelSerializer,
    OccupancyStatusSerializer,
    AgencySerializer,
    StopSerializer,
    GeoStopSerializer,
    RouteSerializer,
    CalendarSerializer,
    CalendarDateSerializer,
    ShapeSerializer,
    GeoShapeSerializer,
    TripSerializer,
    StopTimeSerializer,
    FareAttributeSerializer,
    FareRuleSerializer,
    FeedInfoSerializer,
    ServiceTodaySerializer,
    WhichShapesSerializer,
    FindTripsSerializer,
)
from datetime import datetime
from datetime import date as DateType
from uuid import UUID


def get_schema(request: HttpRequest) -> FileResponse:
    """Serve the static GTFS Realtime OpenAPI schema (docs/schema/realtime.yml) as a file download."""
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )


@method_decorator(xframe_options_exempt, name="dispatch")
class RedocView(SpectacularRedocView):
    """Render the ReDoc API docs page, exempted from clickjacking protection so it can be embedded."""


# -------------
# Operations
# -------------


class LoginView(APIView):
    """Authenticate an operator by username/password and issue a DRF auth token."""

    def post(self, request: Request) -> Response:
        """Validate credentials and return an auth token with the operator's basic info."""
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {
                    "token": token.key,
                    "operator_id": user.operator.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                status=200,
            )
        else:
            return Response({"error": "Usuario o contraseña incorrectos"}, status=400)


class CompanyViewSet(viewsets.ModelViewSet):
    """REST resource for Company records (the legal entities operating vehicles)."""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    # authentication_classes = [TokenAuthentication]


class DataProviderViewSet(viewsets.ModelViewSet):
    """REST resource for DataProvider records (owners of telemetry equipment)."""

    queryset = DataProvider.objects.all()
    serializer_class = DataProviderSerializer
    authentication_classes = [TokenAuthentication]


class VehicleViewSet(viewsets.ModelViewSet):
    """REST resource for Vehicle records, filterable by company."""

    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["company"]
    authentication_classes = [TokenAuthentication]


class EquipmentViewSet(viewsets.ModelViewSet):
    """REST resource for telemetry Equipment records."""

    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    authentication_classes = [TokenAuthentication]

    def create(self, request: Request) -> Response:
        """Create an Equipment record and return only its ID."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "id": serializer.instance.id,
            }
        )


class EquipmentLogViewSet(viewsets.ModelViewSet):
    """REST resource for EquipmentLog records, the historical audit trail of Equipment changes."""

    queryset = EquipmentLog.objects.all()
    serializer_class = EquipmentLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["equipment", "data_provider", "vehicle"]
    authentication_classes = [TokenAuthentication]
    # TODO: Enable only the GET method


class OperatorViewSet(viewsets.ModelViewSet):
    """REST resource for Operator records (drivers, dispatchers, administrators)."""

    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    authentication_classes = [TokenAuthentication]


# -------------
# Runs
# -------------


class CreateRunViewSet(APIView):
    """
    Endpoint to request the creation of a new run.

    It only allows the POST method with the new run data.
    """

    def post(self, request: Request) -> Response:
        """Register a run and drive it REQUESTED -> VALIDATED -> INITIALIZED, or report the failing step."""
        service = RunLifecycleService()
        # Serialization and validation of the input data
        try:
            serializer = CreateRunSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:  # ad portas rejection for invalid input data
            return Response(
                {"status": "error", "step": "serialization", "errors": e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Operational validation of vehicle and operator existence
        payload = dict(serializer.validated_data)
        vehicle_id = payload.pop("vehicle_id", None)
        operator_id = payload.pop("operator_id", None)
        errors = {}
        vehicle = Vehicle.objects.filter(id=vehicle_id).first()
        if not vehicle:
            errors["vehicle_id"] = "Vehicle not found"
        operator_obj = Operator.objects.filter(id=operator_id).first()
        if not operator_obj:
            errors["operator_id"] = "Operator not found"
        if errors:  # ad portas rejection for invalid references to vehicle or operator
            return Response(
                {"status": "error", "step": "operational_validation", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Record creation puts the run in REQUESTED state (run_requested event)
        try:
            # vehicle/operator_obj are guaranteed non-None here: the `if errors`
            # check above already returned when either lookup came back empty.
            assert vehicle is not None
            assert operator_obj is not None
            run = Run.objects.create(**payload)
            run.vehicle.set([vehicle])
            run.operator.set([operator_obj])
            payload["run_id"] = run.id
            payload["vehicle_id"] = vehicle_id
            payload["operator_id"] = operator_id
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "step": "registration",
                    "errors": {"detail": f"Failed to register run: {str(e)}"},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        # REQUESTED → VALIDATED: GTFS consistency check
        try:
            service.process_event(RunLifecycleEvents.VALIDATE_RUN, payload)
        except RunLifecycleError as e:
            service.process_event(RunLifecycleEvents.RUN_REJECTED, payload)
            return Response(
                {"status": "error", "step": "gtfs_validation", "errors": e.errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        # VALIDATED → INITIALIZED: write system state
        try:
            service.process_event(RunLifecycleEvents.INITIALIZE_RUN, payload)
        except RunLifecycleError as e:
            return Response(
                {"status": "error", "step": "initialization", "errors": e.errors},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "status": "success",
                "run_id": run.id,
                "run_lifecycle_state": RunLifecycleStates.INITIALIZED,
            },
            status=status.HTTP_200_OK,
        )


class RunStateViewSet(APIView):
    """
    Endpoint to get the current lifecycle state of a run.

    It only allows the GET method with the run_id as path parameter.
    """

    def get(self, request: Request, run_id: UUID) -> Response:
        """Return the run's current lifecycle state, or 404 if the run does not exist."""
        run = Run.objects.filter(id=run_id).first()
        if not run:
            return Response(
                {"status": "error", "errors": {"run_id": "Run not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"status": "success", "run_lifecycle_state": run.run_lifecycle_state},
            status=status.HTTP_200_OK,
        )


class RunUpdateViewSet(APIView):
    """
    Endpoint to request an update of the lifecycle state of an existing run.

    It only allows the POST method with the event to process.
    """

    def post(self, request: Request, run_id: UUID) -> Response:
        """Process a lowercase run lifecycle event against the run's FSM and return the new state."""
        service = RunLifecycleService()
        serializer = RunUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": "error", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = dict(serializer.validated_data)
        # Flatten `details` into payload so guards/actions can read fields like
        # `actor_role` at the top level — matches the convention used by the
        # internal Celery path (realtime_engine/tasks.py).
        details = payload.pop("details", {}) or {}
        if isinstance(details, dict):
            payload.update(details)
        payload["run_id"] = run_id
        run = Run.objects.filter(id=run_id).first()
        if not run:
            return Response(
                {"status": "error", "errors": {"run_id": "Run not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Ensure the effective event (after payload normalization) is valid.
        event = payload.get("event")
        event_value = (
            event.value if isinstance(event, RunLifecycleEvents) else str(event)
        )
        allowed_events = {e.value for e in RunLifecycleEvents}
        if event_value not in allowed_events:
            return Response(
                {
                    "status": "error",
                    "errors": {
                        "event": f"Invalid event '{event_value}'. Allowed values: {sorted(allowed_events)}"
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload["event"] = event_value
        try:
            # event_value was just checked against every RunLifecycleEvents
            # value, so this reconstruction cannot raise; process_event wants
            # the enum member itself (same convention as
            # realtime_engine/tasks.py's run_lifecycle_event task).
            new_run_lifecycle_state, _guards, _actions = service.process_event(
                RunLifecycleEvents(event_value), payload
            )
        except RunLifecycleError as e:
            return Response(
                {"status": "error", "errors": e.errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(
            {"status": "success", "run_lifecycle_state": new_run_lifecycle_state},
            status=status.HTTP_200_OK,
        )


class RunHistoryView(APIView):
    """
    Return the ordered list of FSM transitions for a run.

    Read-only audit log derived from RunLifecycleTransition, which the
    lifecycle service writes before any external side-effect (so the log
    is authoritative even if a downstream action later fails).
    """

    def get(self, request: Request, run_id: UUID) -> Response:
        """Return the run's FSM transitions ordered by timestamp, or 404 if the run does not exist."""
        if not Run.objects.filter(id=run_id).exists():
            return Response(
                {"status": "error", "errors": {"detail": f"run {run_id} not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        transitions = RunLifecycleTransition.objects.filter(run_id=run_id).order_by(
            "timestamp", "created_at"
        )
        return Response(
            {
                "run_id": str(run_id),
                "transitions": [
                    {
                        "event": t.event_name,
                        "from_state": t.from_state,
                        "to_state": t.to_state,
                        "timestamp": t.timestamp.isoformat(),
                        "actions": t.actions or {},
                        "guards": t.guards or {},
                    }
                    for t in transitions
                ],
            },
            status=status.HTTP_200_OK,
        )


class PositionViewSet(viewsets.ModelViewSet):
    """REST resource for vehicle Position samples (GPS/motion telemetry)."""

    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    authentication_classes = [TokenAuthentication]


class VehicleStopStatusViewSet(viewsets.ModelViewSet):
    """REST resource for vehicle stop-status snapshots (GTFS-RT VehicleStopStatus)."""

    queryset = VehicleStopStatus.objects.all()
    serializer_class = VehicleStopStatusSerializer
    authentication_classes = [TokenAuthentication]


class CongestionLevelViewSet(viewsets.ModelViewSet):
    """REST resource for vehicle congestion-level snapshots (GTFS-RT CongestionLevel)."""

    queryset = CongestionLevel.objects.all()
    serializer_class = CongestionLevelSerializer
    authentication_classes = [TokenAuthentication]


class OccupancyViewSet(viewsets.ModelViewSet):
    """REST resource for vehicle occupancy snapshots (GTFS-RT OccupancyStatus)."""

    queryset = OccupancyStatus.objects.all()
    serializer_class = OccupancyStatusSerializer
    authentication_classes = [TokenAuthentication]


# -------------
# GTFS Schedule
# -------------


class AgencyViewSet(viewsets.ModelViewSet):
    """
    Agencias de transporte público.
    """

    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["agency_id", "agency_name"]
    # permission_classes = [permissions.IsAuthenticated]


class StopViewSet(viewsets.ModelViewSet):
    """
    Paradas de transporte público.
    """

    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "stop_id",
        "stop_code",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "stop_url",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class GeoStopViewSet(viewsets.ModelViewSet):
    """
    Paradas como GeoJSON.
    """

    queryset = Stop.objects.all()
    serializer_class = GeoStopSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "stop_id",
        "location_type",
        "zone_id",
        "parent_station",
        "wheelchair_boarding",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class RouteViewSet(viewsets.ModelViewSet):
    """
    Rutas de transporte público.
    """

    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["route_type", "route_id"]

    # def get_queryset(self):
    #    queryset = Route.objects.all()
    #    route_id = self.request.query_params.get("route_id")
    #    if route_id is not None:
    #        queryset = queryset.filter(route_id=route_id)
    #    return queryset

    # permission_classes = [permissions.IsAuthenticated]


class CalendarViewSet(viewsets.ModelViewSet):
    """
    Calendarios de transporte público.
    """

    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class CalendarDateViewSet(viewsets.ModelViewSet):
    """
    Fechas de calendario de transporte público.
    """

    queryset = CalendarDate.objects.all()
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class ShapeViewSet(viewsets.ModelViewSet):
    """
    Formas de transporte público.
    """

    queryset = Shape.objects.all()
    serializer_class = ShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class GeoShapeViewSet(viewsets.ModelViewSet):
    """
    Formas geográficas de transporte público.
    """

    queryset = GeoShape.objects.all()
    serializer_class = GeoShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class TripViewSet(viewsets.ModelViewSet):
    """
    Viajes de transporte público.
    """

    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # allowed_query_parameters =  ['shape_id', 'direction_id', 'trip_id', 'route_id', 'service_id']

    # def get_queryset(self):
    #    return self.get_filtered_queryset(self.allowed_query_parameters)

    # permission_classes = [permissions.IsAuthenticated]


class StopTimeViewSet(viewsets.ModelViewSet):
    """
    Horarios de paradas de transporte público.
    """

    queryset = StopTime.objects.all()
    serializer_class = StopTimeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["trip_id", "stop_id"]
    # permission_classes = [permissions.IsAuthenticated]


class FareAttributeViewSet(viewsets.ModelViewSet):
    """
    Atributos de tarifa de transporte público.
    """

    queryset = FareAttribute.objects.all()
    serializer_class = FareAttributeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["fare_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FareRuleViewSet(viewsets.ModelViewSet):
    """
    Reglas de tarifa de transporte público.
    """

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["route_id", "origin_id", "destination_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FeedInfoViewSet(viewsets.ModelViewSet):
    """
    Información de alimentación de transporte público.
    """

    queryset = FeedInfo.objects.all()
    serializer_class = FeedInfoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["feed_publisher_name"]
    # permission_classes = [permissions.IsAuthenticated]


# --------------
# Auxiliary GTFS
# --------------


class ServiceTodayView(APIView):
    """Endpoint returning the GTFS service IDs active on a given (or today's) date."""

    def get(self, request: Request) -> Response:
        """Return service IDs active on `?date=YYYY-MM-DD` (default today), from exceptions or the weekly calendar."""
        # `date` holds a full `datetime` when parsed from the query param, or a
        # bare `date` when defaulted to today; both work as GTFS date filters.
        date: datetime | DateType
        if request.query_params.get("date"):
            date = datetime.strptime(request.query_params.get("date"), "%Y-%m-%d")
        else:
            date = datetime.now().date()

        calendar_date = CalendarDate.objects.filter(date=date, exception_type=1).values(
            "service_id"
        )
        if calendar_date:
            serializer = ServiceTodaySerializer(calendar_date, many=True)
            return Response(serializer.data)

        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        day_of_week = date.weekday()
        service = Calendar.objects.filter(
            start_date__lte=date, end_date__gte=date, **{f"{days[day_of_week]}": True}
        ).values("service_id")

        serializer = ServiceTodaySerializer(service, many=True)
        return Response(serializer.data)


class WhichShapesView(APIView):
    """Endpoint returning the distinct shapes used by a route's stops, given `?route_id=`."""

    def get(self, request: Request) -> Response:
        """Return the distinct GeoShapes used by the given route in the current feed."""
        route_id = request.query_params.get("route_id")
        feed = Feed.objects.filter(is_current=True).first()
        route = Route.objects.filter(feed=feed, route_id=route_id).first()
        # Pre-existing bug, out of scope for this docs/type-hints pass: RouteStop
        # has no "route"/"shape" fields (only linked_route/linked_shape), so this
        # query raises FieldError at runtime; flagged in the task report rather
        # than fixed here. `# type: ignore` silences the resulting mypy errors
        # (field names it can't resolve, then a RouteStop row treated as a dict).
        shapes = RouteStop.objects.filter(route=route)  # type: ignore[misc]
        shapes = shapes.values("shape").distinct()  # type: ignore[misc]
        geo_shapes = []
        for shape in shapes:
            geo_shape = (
                GeoShape.objects.filter(id=shape["shape"])  # type: ignore[index, misc]
                .values(
                    "shape_id",
                    "direction_id",
                    "shape_name",
                    "shape_desc",
                    "shape_from",
                    "shape_to",
                )
                .first()
            )
            geo_shapes.append(geo_shape)

        serializer = WhichShapesSerializer(geo_shapes, many=True)
        return Response(serializer.data)


class FindTripsView(APIView):
    """Endpoint returning scheduled trips matching a route/service/shape, with their run lifecycle state."""

    def get(self, request: Request) -> Response:
        """Return trips for `?route_id=&service_id=&shape_id=`, each tagged with its run's lifecycle state."""
        # Get the query parameters
        route_id = request.query_params.get("route_id")
        service_id = request.query_params.get("service_id")
        shape_id = request.query_params.get("shape_id")
        if not route_id or not service_id or not shape_id:
            return Response(
                {
                    "error": "Todos los parámetros route_id, service_id, shape_id son requeridos"
                },
                status=400,
            )

        # Get the current feed
        feed = Feed.objects.filter(is_current=True).first()
        trips = Trip.objects.filter(
            route_id=route_id,
            service_id=service_id,
            shape_id=shape_id,
            feed=feed,
        )

        selected_trips = []
        for trip in trips:
            # Pre-existing bug, out of scope for this docs/type-hints pass:
            # TripTime has no "trip_time" field (it's "departure_time"), so this
            # raises FieldError at runtime; flagged in the task report rather
            # than fixed here.
            this_trip = (
                TripTime.objects.filter(trip_id=trip.trip_id)  # type: ignore[misc]
                .order_by("trip_time")
                .values("trip_id", "trip_time")
                .first()
            )
            if this_trip:
                this_run_lifecycle_state = (
                    Run.objects.filter(
                        trip_id=trip.trip_id,
                        start_date=datetime.now().date(),
                        # TODO: check the criteria for selecting the runs
                    )
                    .values("run_lifecycle_state")
                    .first()
                )
                if this_run_lifecycle_state:
                    run_lifecycle_state = this_run_lifecycle_state[
                        "run_lifecycle_state"
                    ]
                else:
                    run_lifecycle_state = "UNKNOWN"
                selected_trips.append(
                    {
                        "trip_id": this_trip["trip_id"],
                        "trip_time": this_trip["trip_time"],
                        "run_lifecycle_state": run_lifecycle_state,
                        "direction_id": trip.direction_id,
                        "trip_headsign": trip.trip_headsign,
                    }
                )

        serializer = FindTripsSerializer(selected_trips, many=True)

        return Response(serializer.data)
