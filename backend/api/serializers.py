from operations.models import (
    Company,
    Operator,
    DataProvider,
    Vehicle,
    Equipment,
    EquipmentLog,
)
from runs.models import (
    Run,
    Position,
    Progression,
    Occupancy,
)
from runs.domain import RunLifecycleEvents
from feed.models import *
from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.gis.geos import Point
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField

# --------------
# Login data
# --------------


class LoginSerializer(serializers.Serializer):
    token = serializers.CharField()
    operator_id = serializers.CharField()


# --------------
# Telemetry data
# --------------


class CompanySerializer(serializers.HyperlinkedModelSerializer):
    agency = serializers.PrimaryKeyRelatedField(queryset=Agency.objects.all())

    class Meta:
        model = Company
        model = Company
        fields = "__all__"
        ordering = ["id"]


class OperatorSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), many=True
    )

    class Meta:
        model = Operator
        fields = "__all__"
        ordering = ["operator_id"]


class DataProviderSerializer(serializers.HyperlinkedModelSerializer):
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), many=True
    )

    class Meta:
        model = DataProvider
        fields = "__all__"
        ordering = ["id"]


class VehicleSerializer(serializers.HyperlinkedModelSerializer):
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())

    class Meta:
        model = Vehicle
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


class EquipmentLogSerializer(serializers.HyperlinkedModelSerializer):
    equipment = serializers.PrimaryKeyRelatedField(queryset=Equipment.objects.all())
    data_provider = serializers.PrimaryKeyRelatedField(
        queryset=DataProvider.objects.all()
    )
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = EquipmentLog
        fields = "__all__"
        ordering = ["id"]


class RunSerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    operator = serializers.PrimaryKeyRelatedField(queryset=Operator.objects.all())

    class Meta:
        model = Run
        fields = "__all__"
        ordering = ["id"]


class CreateRunSerializer(serializers.Serializer):
    vehicle_id = serializers.CharField(max_length=100)
    operator_id = serializers.CharField(max_length=100)
    route_id = serializers.CharField(max_length=100)
    trip_id = serializers.CharField(max_length=100)
    direction_id = serializers.IntegerField(min_value=0)
    shape_id = serializers.CharField(max_length=100)
    schedule_relationship = serializers.ChoiceField(
        choices=[
            "SCHEDULED",
            "ADDED",
            "UNSCHEDULED",
            "CANCELED",
            "DUPLICATED",
            "DELETED",
        ]
    )


class RunUpdateSerializer(serializers.Serializer):
    event = serializers.ChoiceField(choices=RunLifecycleEvents)
    details = serializers.JSONField(required=False, default=dict)


class PositionSerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "url",
            "vehicle",
            "vehicle",
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
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = Progression
        fields = "__all__"
        fields = "__all__"
        ordering = ["id"]


class OccupancySerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = Occupancy
        fields = "__all__"
        fields = "__all__"
        ordering = ["id"]


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


# --------------
# Auxiliary GTFS
# --------------


class ServiceTodaySerializer(serializers.Serializer):
    service_id = serializers.CharField()


class WhichShapesSerializer(serializers.Serializer):
    shape_id = serializers.CharField()
    direction_id = serializers.IntegerField()
    shape_name = serializers.CharField()
    shape_desc = serializers.CharField()
    shape_from = serializers.CharField()
    shape_to = serializers.CharField()


class FindTripsSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    trip_time = serializers.TimeField()
    run_lifecycle_state = serializers.CharField()
    direction_id = serializers.IntegerField()
    trip_headsign = serializers.CharField()


# -------------
# GTFS Realtime
# -------------
