from django.conf import settings
from django.http import FileResponse
from django.contrib.auth.models import Group, User
from feed.models import OnBoardEquipment
from rest_framework import permissions, viewsets

from .serializers import GroupSerializer, UserSerializer, OnBoardEquipmentSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """

    queryset = Group.objects.all().order_by("name")
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class OnBoardEquipmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows on board equipment to be viewed or edited.
    """

    queryset = OnBoardEquipment.objects.all().order_by("created_at")
    serializer_class = OnBoardEquipmentSerializer
    permission_classes = [permissions.IsAuthenticated]


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "realtime.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="realtime.yml"
    )
