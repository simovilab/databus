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
from gtfs.models import *
from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.gis.geos import Point
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField


# --------------
# Telemetry data
# --------------


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


# -------------
# GTFS Schedule
# -------------


class AgencySerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Agency
        fields = "__all__"


class StopSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Stop
        fields = "__all__"


class GeoStopSerializer(GeoFeatureModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    stop_point = GeometryField()

    class Meta:
        model = Stop
        geo_field = "stop_point"
        fields = "__all__"


class RouteSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Route
        fields = "__all__"


class CalendarSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Calendar
        fields = "__all__"


class CalendarDateSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CalendarDate
        fields = "__all__"


class ShapeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Shape
        fields = "__all__"


class GeoShapeSerializer(GeoFeatureModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    geometry = GeometryField()

    class Meta:
        model = GeoShape
        geo_field = "geometry"
        fields = "__all__"


class TripSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = "__all__"


class StopTimeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTime
        fields = "__all__"


class FareAttributeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareAttribute
        fields = "__all__"


class FareRuleSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareRule
        fields = "__all__"


class FeedInfoSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedInfo
        fields = "__all__"


# -------------
# GTFS Realtime
# -------------
