from django.conf import settings
from django.http import FileResponse
from django.contrib.auth import authenticate
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend

from feed.models import *
from gtfs.models import Feed, Trip, StopTime, RouteStop
from .serializers import *

from datetime import datetime, timedelta


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )


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

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    # authentication_classes = [TokenAuthentication]


class DataProviderViewSet(viewsets.ModelViewSet):
    queryset = DataProvider.objects.all()
    serializer_class = DataProviderSerializer
    authentication_classes = [TokenAuthentication]


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    authentication_classes = [TokenAuthentication]


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    authentication_classes = [TokenAuthentication]

    # Using Response, return the id of the created object
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {
                "id": serializer.instance.id,
                "serial_number": serializer.instance.serial_number,
                # TODO: verify that no repeated serial numbers are allowed
            }
        )


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    authentication_classes = [TokenAuthentication]


class JourneyViewSet(viewsets.ModelViewSet):
    queryset = Journey.objects.all()
    serializer_class = JourneySerializer
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


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    authentication_classes = [TokenAuthentication]


class ProgressionViewSet(viewsets.ModelViewSet):
    queryset = Progression.objects.all()
    serializer_class = ProgressionSerializer
    authentication_classes = [TokenAuthentication]


class OccupancyViewSet(viewsets.ModelViewSet):
    queryset = Occupancy.objects.all()
    serializer_class = OccupancySerializer
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
        shapes = RouteStop.objects.filter(route_id=route_id)
        shapes = shapes.values("shape_id").distinct()
        geo_shapes = []
        for shape in shapes:
            geo_shape = (
                GeoShape.objects.filter(shape_id=shape["shape_id"])
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
        print(trips)

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
                        trip_id=trip.trip_id, start_date=datetime.now().date()
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
                    }
                )

        serializer = FindTripsSerializer(selected_trips, many=True)

        return Response(serializer.data)
