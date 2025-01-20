from feed.models import (
    Vehicle,
    Operator,
    DataProvider,
    Equipment,
    Journey,
    Position,
    Progression,
    Occupancy,
)
from gtfs.models import Agency
from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.gis.geos import Point


class VehicleSerializer(serializers.HyperlinkedModelSerializer):
    agency = serializers.PrimaryKeyRelatedField(queryset=Agency.objects.all())

    class Meta:
        model = Vehicle
        fields = "__all__"
        ordering = ["id"]


class DataProviderSerializer(serializers.HyperlinkedModelSerializer):
    agency = serializers.PrimaryKeyRelatedField(
        queryset=Agency.objects.all(), many=True
    )

    class Meta:
        model = DataProvider
        fields = "__all__"
        ordering = ["id"]


class EquipmentSerializer(serializers.HyperlinkedModelSerializer):

    data_provider = serializers.PrimaryKeyRelatedField(
        queryset=DataProvider.objects.all()
    )
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = Equipment
        fields = "__all__"
        ordering = ["id"]


class OperatorSerializer(serializers.HyperlinkedModelSerializer):

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    agency = serializers.PrimaryKeyRelatedField(
        queryset=Agency.objects.all(), many=True
    )
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    equipment = serializers.PrimaryKeyRelatedField(queryset=Equipment.objects.all())

    class Meta:
        model = Operator
        fields = "__all__"
        ordering = ["operator_id"]


class JourneySerializer(serializers.HyperlinkedModelSerializer):

    equipment = serializers.PrimaryKeyRelatedField(read_only=True)
    operator = serializers.PrimaryKeyRelatedField(queryset=Operator.objects.all())

    class Meta:
        model = Journey
        fields = "__all__"
        ordering = ["id"]


class PositionSerializer(serializers.HyperlinkedModelSerializer):

    journey = serializers.PrimaryKeyRelatedField(
        queryset=Journey.objects.filter(journey_status="IN_PROGRESS")
    )
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "url",
            "journey",
            "timestamp",
            "point",
            "latitude",
            "longitude",
            "bearing",
            "odometer",
            "speed",
        ]
        ordering = ["id"]

    def get_latitude(self, obj):
        if obj.point:
            return obj.point.y
        return None

    def get_longitude(self, obj):
        if obj.point:
            return obj.point.x
        return None

    # def create(self, validated_data):
    #     latitude = validated_data.pop("latitude")
    #     longitude = validated_data.pop("longitude")
    #     point = Point(longitude, latitude)
    #     return Position.objects.create(point=point, **validated_data)


class ProgressionSerializer(serializers.HyperlinkedModelSerializer):

    journey = serializers.PrimaryKeyRelatedField(
        queryset=Journey.objects.filter(journey_status="IN_PROGRESS")
    )

    class Meta:
        model = Progression
        fields = [
            "url",
            "journey",
            "timestamp",
            "current_stop_sequence",
            "stop_id",
            "current_status",
            "congestion_level",
        ]
        ordering = ["id"]


class OccupancySerializer(serializers.HyperlinkedModelSerializer):

    journey = serializers.PrimaryKeyRelatedField(
        queryset=Journey.objects.filter(journey_status="IN_PROGRESS")
    )

    class Meta:
        model = Occupancy
        fields = [
            "url",
            "journey",
            "timestamp",
            "occupancy_status",
            "occupancy_percentage",
            "occupancy_count",
        ]
        ordering = ["id"]


class FindTripsSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    trip_departure_time = serializers.TimeField()
