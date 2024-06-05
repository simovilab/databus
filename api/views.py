from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.authentication import TokenAuthentication

from feed.models import *
from .serializers import *


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    authentication_classes = [TokenAuthentication]


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    authentication_classes = [TokenAuthentication]


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    authentication_classes = [TokenAuthentication]


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    authentication_classes = [TokenAuthentication]


class PathViewSet(viewsets.ModelViewSet):
    queryset = Path.objects.all()
    serializer_class = PathSerializer
    authentication_classes = [TokenAuthentication]


class OccupancyViewSet(viewsets.ModelViewSet):
    queryset = Occupancy.objects.all()
    serializer_class = OccupancySerializer
    authentication_classes = [TokenAuthentication]
