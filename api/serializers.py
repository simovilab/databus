from django.contrib.auth.models import Group, User
from feed.models import OnBoardEquipment
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ["url", "username", "email", "groups"]


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ["url", "name"]


class OnBoardEquipmentSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = OnBoardEquipment
        fields = ["url", "serial_number", "brand", "model", "owner", "created_at", "updated_at"]