from django.conf import settings
from django.http import FileResponse
from django.contrib.auth import authenticate
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.views import SpectacularRedocView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from feed.models import *
from gtfs.models import Feed, Trip, StopTime, RouteStop
from .serializers import *
from .permissions import IsOperatorOrReadOnly, IsAdminOrReadOnly, CanManageEquipment

from datetime import datetime, timedelta


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )


@method_decorator(xframe_options_exempt, name="dispatch")
class RedocView(SpectacularRedocView):
    pass


class LoginView(APIView):
    def post(self, request):
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


@extend_schema_view(
    list=extend_schema(
        description="List all companies",
        examples=[
            OpenApiExample(
                'Company List Response',
                value={
                    "count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{
                        "id": "company001",
                        "name": "Transporte Ejemplo S.A.",
                        "description": "Empresa de transporte público",
                        "phone": "+50612345678",
                        "email": "contacto@ejemplo.com"
                    }]
                },
                response_only=True
            )
        ]
    ),
    create=extend_schema(
        description="Create a new company",
        examples=[
            OpenApiExample(
                'Create Company Request',
                value={
                    "id": "company002",
                    "name": "Nueva Compañía",
                    "description": "Descripción de la compañía",
                    "phone": "+50687654321",
                    "email": "info@nueva.com"
                },
                request_only=True
            )
        ]
    )
)
class CompanyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing transport companies.
    
    list: Get all companies
    retrieve: Get a specific company by ID
    create: Create a new company (admin only)
    update: Update a company (admin only)
    partial_update: Partially update a company (admin only)
    destroy: Delete a company (admin only)
    """
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'id']
    ordering = ['name']


class DataProviderViewSet(viewsets.ModelViewSet):
    queryset = DataProvider.objects.all()
    serializer_class = DataProviderSerializer
    authentication_classes = [TokenAuthentication]


@extend_schema_view(
    list=extend_schema(
        description="List all vehicles with optional filtering",
        parameters=[
            OpenApiParameter(name='company', description='Filter by company ID', required=False, type=str),
        ],
    ),
    create=extend_schema(
        description="Create a new vehicle",
        examples=[
            OpenApiExample(
                'Create Vehicle Request',
                value={
                    "company": "company001",
                    "license_plate": "ABC123",
                    "vehicle_type": "bus",
                    "capacity": 40
                },
                request_only=True
            )
        ]
    )
)
class VehicleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing vehicles.
    
    Supports filtering by company.
    """
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["company"]
    search_fields = ['license_plate', 'internal_id']
    ordering_fields = ['license_plate', 'id']
    ordering = ['license_plate']


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    authentication_classes = [TokenAuthentication]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "id": serializer.instance.id,
            }
        )


class EquipmentLogViewSet(viewsets.ModelViewSet):
    queryset = EquipmentLog.objects.all()
    serializer_class = EquipmentLogSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["equipment", "data_provider", "vehicle"]
    authentication_classes = [TokenAuthentication]
    # TODO: Enable only the GET method


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    authentication_classes = [TokenAuthentication]


@extend_schema_view(
    list=extend_schema(
        description="List all journeys with optional filtering",
        parameters=[
            OpenApiParameter(name='vehicle', description='Filter by vehicle ID', required=False, type=int),
            OpenApiParameter(name='status', description='Filter by status', required=False, type=str),
            OpenApiParameter(name='operator', description='Filter by operator ID', required=False, type=str),
        ],
    ),
    create=extend_schema(
        description="Create a new journey",
        examples=[
            OpenApiExample(
                'Create Journey Request',
                value={
                    "vehicle": 1,
                    "operator": "OP001",
                    "trip": 100,
                    "start_time": "2025-11-25T06:00:00Z",
                    "status": "ACTIVE"
                },
                request_only=True
            )
        ]
    )
)
class JourneyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing journeys (vehicle trips).
    
    A journey represents a specific execution of a planned trip by a vehicle.
    Supports filtering by vehicle, status, and operator.
    """
    queryset = Journey.objects.select_related('vehicle', 'operator', 'trip').all()
    serializer_class = JourneySerializer
    permission_classes = [IsOperatorOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['vehicle', 'status', 'operator', 'connection_status']
    search_fields = ['vehicle__license_plate', 'operator__id']
    ordering_fields = ['start_time', 'end_time', 'status']
    ordering = ['-start_time']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"id": serializer.instance.id, **serializer.data},
            status=status.HTTP_201_CREATED,
            headers=headers
        )


@extend_schema_view(
    list=extend_schema(
        description="List vehicle positions with optional filtering",
        parameters=[
            OpenApiParameter(name='vehicle', description='Filter by vehicle ID', required=False, type=int),
            OpenApiParameter(name='journey', description='Filter by journey ID', required=False, type=int),
        ],
    ),
    create=extend_schema(
        description="Report a vehicle position",
        examples=[
            OpenApiExample(
                'Create Position Request (with lat/lon)',
                value={
                    "vehicle": 1,
                    "journey": 10,
                    "latitude": 9.9333,
                    "longitude": -84.0833,
                    "bearing": 45.5,
                    "speed": 35.0,
                    "timestamp": "2025-11-25T10:30:00Z"
                },
                request_only=True
            ),
            OpenApiExample(
                'Create Position Request (with point)',
                value={
                    "vehicle": 1,
                    "journey": 10,
                    "point": "POINT(-84.0833 9.9333)",
                    "bearing": 45.5,
                    "speed": 35.0,
                    "timestamp": "2025-11-25T10:30:00Z"
                },
                request_only=True
            )
        ]
    )
)
class PositionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for vehicle positions (GPS telemetry).
    
    Positions can be created using either:
    - 'latitude' and 'longitude' fields (simpler)
    - 'point' field with WKT/GeoJSON (advanced)
    
    Supports filtering by vehicle and journey.
    """
    queryset = Position.objects.select_related('vehicle', 'journey').all()
    serializer_class = PositionSerializer
    permission_classes = [IsOperatorOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['vehicle', 'journey']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


@extend_schema_view(
    list=extend_schema(
        description="List progression updates with optional filtering",
        parameters=[
            OpenApiParameter(name='vehicle', description='Filter by vehicle ID', required=False, type=int),
            OpenApiParameter(name='journey', description='Filter by journey ID', required=False, type=int),
            OpenApiParameter(name='trip', description='Filter by trip ID', required=False, type=int),
        ],
    ),
)
class ProgressionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for vehicle progression (stop arrivals/departures).
    
    Progression tracks a vehicle's movement through trip stops.
    """
    queryset = Progression.objects.select_related('vehicle', 'journey', 'trip', 'stop').all()
    serializer_class = ProgressionSerializer
    permission_classes = [IsOperatorOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['vehicle', 'journey', 'trip', 'stop']
    ordering_fields = ['timestamp', 'stop_sequence']
    ordering = ['-timestamp']


@extend_schema_view(
    list=extend_schema(
        description="List occupancy updates with optional filtering",
        parameters=[
            OpenApiParameter(name='vehicle', description='Filter by vehicle ID', required=False, type=int),
            OpenApiParameter(name='journey', description='Filter by journey ID', required=False, type=int),
        ],
    ),
)
class OccupancyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for vehicle occupancy (passenger count).
    
    Tracks how many passengers are on board.
    """
    queryset = Occupancy.objects.select_related('vehicle', 'journey').all()
    serializer_class = OccupancySerializer
    permission_classes = [IsOperatorOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['vehicle', 'journey', 'occupancy_status']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


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
    def get(self, request):
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
    def get(self, request):
        route_id = request.query_params.get("route_id")
        feed = Feed.objects.filter(is_current=True).first()
        route = Route.objects.filter(feed=feed, route_id=route_id).first()
        shapes = RouteStop.objects.filter(route=route)
        shapes = shapes.values("shape").distinct()
        geo_shapes = []
        for shape in shapes:
            geo_shape = (
                GeoShape.objects.filter(id=shape["shape"])
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
    def get(self, request):
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
            this_trip = (
                TripTime.objects.filter(trip_id=trip.trip_id)
                .order_by("trip_time")
                .values("trip_id", "trip_time")
                .first()
            )
            if this_trip:
                this_journey_status = (
                    Journey.objects.filter(
                        trip_id=trip.trip_id,
                        start_date=datetime.now().date(),
                        # TODO: check the criteria for selecting the journeys
                    )
                    .values("journey_status")
                    .first()
                )
                if this_journey_status:
                    journey_status = this_journey_status["journey_status"]
                else:
                    journey_status = "UNKNOWN"
                selected_trips.append(
                    {
                        "trip_id": this_trip["trip_id"],
                        "trip_time": this_trip["trip_time"],
                        "journey_status": journey_status,
                        "direction_id": trip.direction_id,
                        "trip_headsign": trip.trip_headsign,
                    }
                )

        serializer = FindTripsSerializer(selected_trips, many=True)

        return Response(serializer.data)
