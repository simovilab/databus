from django.conf import settings
from django.http import FileResponse
from django.contrib.auth import authenticate
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt

from feed.models import *
from gtfs.models import Feed, Trip, StopTime
from .serializers import *

from datetime import datetime, timedelta


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    authentication_classes = [TokenAuthentication]


class OperatorViewSet(viewsets.ModelViewSet):
    queryset = Operator.objects.all()
    serializer_class = OperatorSerializer
    authentication_classes = [TokenAuthentication]


class DataProviderViewSet(viewsets.ModelViewSet):
    queryset = DataProvider.objects.all()
    serializer_class = DataProviderSerializer
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


class FindTripsView(APIView):
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        # Get the query parameters
        route_id = request.query_params.get("route_id")
        service_id = request.query_params.get("service_id")
        shape_id = request.query_params.get("shape_id")
        direction_id = request.query_params.get("direction_id")
        if not route_id or not service_id or not shape_id or not direction_id:
            return Response(
                {"error": "Todos los parámetros route_id, service_id, shape_id, and direction_id son requeridos"},
                status=400,
            )

        # Get the current feed
        feed = Feed.objects.filter(is_current=True).first()
        trips = Trip.objects.filter(
            route_id=route_id,
            service_id=service_id,
            shape_id=shape_id,
            direction_id=direction_id,
            feed=feed,
        )

        selected_trips = []
        tolerance = timedelta(minutes=30)
        lower_bound = datetime.now() - tolerance
        upper_bound = datetime.now() + tolerance

        for trip in trips:
            # Get the stop times for the trip
            print(trip)
            first_stop_time = (
                StopTime.objects.filter(trip_id=trip.trip_id)
                .order_by("stop_sequence")
                .first()
            )
            departure_time = first_stop_time.departure_time
            print(departure_time)
            if departure_time > lower_bound.time() and departure_time < upper_bound.time():
                selected_trips.append(
                    {
                        "trip_id": trip.trip_id,
                        "trip_departure_time": departure_time,
                    }
                )

        # Serialize the journeys
        serializer = FindTripsSerializer(selected_trips, many=True)

        return Response(serializer.data)
