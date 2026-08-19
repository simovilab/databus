"""DRF serializers for the operations, runs, and GTFS Schedule domains exposed by the api app."""

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
    VehicleStopStatus,
    CongestionLevel,
    OccupancyStatus,
)
from runs.domain.lifecycle import RunLifecycleEvents
from feed.models import (
    Agency,
    Stop,
    Route,
    Calendar,
    CalendarDate,
    Shape,
    GeoShape,
    Trip,
    StopTime,
    FareAttribute,
    FareRule,
    FeedInfo,
)
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField

# --------------
# Login data
# --------------


class LoginSerializer(serializers.Serializer):
    """Serialize an auth token issued alongside the authenticated operator's ID."""

    token = serializers.CharField()
    operator_id = serializers.CharField()


# --------------
# Telemetry data
# --------------


class CompanySerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a Company, the legal entity operating vehicles under a GTFS Agency."""

    agency = serializers.PrimaryKeyRelatedField(queryset=Agency.objects.all())

    class Meta:
        model = Company
        model = Company
        fields = "__all__"
        ordering = ["id"]


class OperatorSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize an Operator (driver, dispatcher, or administrator) and their companies."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), many=True
    )

    class Meta:
        model = Operator
        fields = "__all__"
        ordering = ["operator_id"]


class DataProviderSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a DataProvider, the owner of the telemetry equipment for a company."""

    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), many=True
    )

    class Meta:
        model = DataProvider
        fields = "__all__"
        ordering = ["id"]


class VehicleSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a Vehicle and its owning Company."""

    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())

    class Meta:
        model = Vehicle
        fields = "__all__"
        ordering = ["id"]


class EquipmentSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a telemetry Equipment unit and its owning provider/vehicle."""

    data_provider = serializers.PrimaryKeyRelatedField(
        queryset=DataProvider.objects.all()
    )
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = Equipment
        fields = "__all__"
        ordering = ["id"]


class EquipmentLogSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a historical snapshot of an Equipment unit's identity and status."""

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
    """Serialize a Run with its assigned vehicle and operator (currently unused; no route registers it)."""

    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    operator = serializers.PrimaryKeyRelatedField(queryset=Operator.objects.all())

    class Meta:
        model = Run
        fields = "__all__"
        ordering = ["id"]


class CreateRunSerializer(serializers.Serializer):
    """Validate the payload for requesting a new run (vehicle, operator, and GTFS trip identifiers)."""

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
    """Validate a run lifecycle update request: a lowercase `RunLifecycleEvents` value plus optional details."""

    event = serializers.ChoiceField(choices=RunLifecycleEvents)
    details = serializers.JSONField(required=False, default=dict)


class PositionSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a vehicle Position sample, exposing latitude/longitude alongside the raw point."""

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

    def get_latitude(self, obj: Position) -> float | None:
        """Return the position's latitude (point.y), or None if no point is set."""
        if obj.point:
            return obj.point.y
        return None

    def get_longitude(self, obj: Position) -> float | None:
        """Return the position's longitude (point.x), or None if no point is set."""
        if obj.point:
            return obj.point.x
        return None

    # def create(self, validated_data):
    #     latitude = validated_data.pop("latitude")
    #     longitude = validated_data.pop("longitude")
    #     point = Point(longitude, latitude)
    #     return Position.objects.create(point=point, **validated_data)


class VehicleStopStatusSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a vehicle's relationship to its current/next stop (GTFS-RT VehicleStopStatus)."""

    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = VehicleStopStatus
        fields = "__all__"
        fields = "__all__"
        ordering = ["id"]


class CongestionLevelSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a vehicle's congestion level (GTFS-RT CongestionLevel)."""

    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = CongestionLevel
        fields = "__all__"
        fields = "__all__"
        ordering = ["id"]


class OccupancyStatusSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a vehicle's passenger occupancy (GTFS-RT OccupancyStatus)."""

    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = OccupancyStatus
        fields = "__all__"
        fields = "__all__"
        ordering = ["id"]


# -------------
# GTFS Schedule
# -------------


class AgencySerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS Agency (agency.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Agency
        fields = "__all__"


class StopSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS Stop (stops.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Stop
        fields = "__all__"


class GeoStopSerializer(GeoFeatureModelSerializer):
    """Serialize GTFS Stops as GeoJSON features keyed on their point geometry."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    stop_point = GeometryField()

    class Meta:
        model = Stop
        geo_field = "stop_point"
        fields = "__all__"


class RouteSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS Route (routes.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Route
        fields = "__all__"


class CalendarSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS weekly service Calendar (calendar.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Calendar
        fields = "__all__"


class CalendarDateSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS CalendarDate service exception (calendar_dates.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CalendarDate
        fields = "__all__"


class ShapeSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS Shape point (shapes.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Shape
        fields = "__all__"


class GeoShapeSerializer(GeoFeatureModelSerializer):
    """Serialize GTFS Shapes as GeoJSON LineString features."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    geometry = GeometryField()

    class Meta:
        model = GeoShape
        geo_field = "geometry"
        fields = "__all__"


class TripSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS Trip (trips.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = "__all__"


class StopTimeSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS StopTime (stop_times.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTime
        fields = "__all__"


class FareAttributeSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS FareAttribute (fare_attributes.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareAttribute
        fields = "__all__"


class FareRuleSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize a GTFS FareRule (fare_rules.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareRule
        fields = "__all__"


class FeedInfoSerializer(serializers.HyperlinkedModelSerializer):
    """Serialize GTFS FeedInfo (feed_info.txt)."""

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedInfo
        fields = "__all__"


# --------------
# Auxiliary GTFS
# --------------


class ServiceTodaySerializer(serializers.Serializer):
    """Serialize a GTFS service ID active on a given date."""

    service_id = serializers.CharField()


class WhichShapesSerializer(serializers.Serializer):
    """Serialize the distinct shapes used by a route's stop sequence."""

    shape_id = serializers.CharField()
    direction_id = serializers.IntegerField()
    shape_name = serializers.CharField()
    shape_desc = serializers.CharField()
    shape_from = serializers.CharField()
    shape_to = serializers.CharField()


class FindTripsSerializer(serializers.Serializer):
    """Serialize a scheduled trip alongside its run's current lifecycle state, if any."""

    trip_id = serializers.CharField()
    trip_time = serializers.TimeField()
    run_lifecycle_state = serializers.CharField()
    direction_id = serializers.IntegerField()
    trip_headsign = serializers.CharField()


# -------------
# GTFS Realtime
# -------------
