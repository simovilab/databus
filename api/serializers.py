from feed.models import (
    Company,
    Operator,
    DataProvider,
    Vehicle,
    Equipment,
    EquipmentLog,
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
from django.utils import timezone
from datetime import timedelta

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
    agency = serializers.PrimaryKeyRelatedField(queryset=Agency.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Company
        fields = "__all__"
        ordering = ["id"]
    
    def validate_id(self, value):
        """Validate company ID format."""
        if not value or len(value) < 2:
            raise serializers.ValidationError("Company ID must be at least 2 characters long.")
        if ' ' in value:
            raise serializers.ValidationError("Company ID cannot contain spaces.")
        return value


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
    equipment_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vehicle
        fields = "__all__"
        ordering = ["id"]
    
    def get_equipment_count(self, obj):
        """Return count of equipment assigned to this vehicle."""
        return obj.equipment_set.count()
    
    def validate_license_plate(self, value):
        """Validate license plate format."""
        if value and len(value) < 3:
            raise serializers.ValidationError("License plate must be at least 3 characters long.")
        return value


class EquipmentSerializer(serializers.HyperlinkedModelSerializer):
    data_provider = serializers.PrimaryKeyRelatedField(
        queryset=DataProvider.objects.all()
    )
class EquipmentSerializer(serializers.HyperlinkedModelSerializer):
    data_provider = serializers.PrimaryKeyRelatedField(
        queryset=DataProvider.objects.all()
    )
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Equipment
        fields = "__all__"
        ordering = ["id"]
    
    def get_status_display(self, obj):
        """Return human-readable status."""
        return obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status


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


class JourneySerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    operator = serializers.PrimaryKeyRelatedField(queryset=Operator.objects.all(), required=False, allow_null=True)
    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(), required=False, allow_null=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    connection_status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Journey
        fields = "__all__"
        ordering = ["-start_time"]
    
    def get_status_display(self, obj):
        """Return human-readable status."""
        return obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
    
    def get_connection_status_display(self, obj):
        """Return human-readable connection status."""
        return obj.get_connection_status_display() if hasattr(obj, 'get_connection_status_display') else obj.connection_status
    
    def validate(self, data):
        """Validate journey data."""
        # End time must be after start time if both provided
        if 'start_time' in data and 'end_time' in data:
            if data['end_time'] and data['start_time']:
                if data['end_time'] < data['start_time']:
                    raise serializers.ValidationError({
                        "end_time": "End time must be after start time."
                    })
        return data


class PositionSerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    journey = serializers.PrimaryKeyRelatedField(queryset=Journey.objects.all(), required=False, allow_null=True)
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)
    lat = serializers.SerializerMethodField(read_only=True)
    lon = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Position
        fields = [
            "url",
            "id",
            "vehicle",
            "journey",
            "timestamp",
            "point",
            "latitude",
            "longitude",
            "lat",
            "lon",
            "bearing",
            "odometer",
            "speed",
        ]
        ordering = ["-timestamp"]

    def get_lat(self, obj):
        """Get latitude from point."""
        if obj.point:
            return obj.point.y
        return None

    def get_lon(self, obj):
        """Get longitude from point."""
        if obj.point:
            return obj.point.x
        return None
    
    def validate(self, data):
        """Validate position data and create point from lat/lon if provided."""
        latitude = data.pop('latitude', None)
        longitude = data.pop('longitude', None)
        
        # If lat/lon provided, create Point
        if latitude is not None and longitude is not None:
            # Validate coordinates
            if not (-90 <= latitude <= 90):
                raise serializers.ValidationError({
                    "latitude": "Latitude must be between -90 and 90 degrees."
                })
            if not (-180 <= longitude <= 180):
                raise serializers.ValidationError({
                    "longitude": "Longitude must be between -180 and 180 degrees."
                })
            data['point'] = Point(longitude, latitude, srid=4326)
        elif 'point' not in data:
            raise serializers.ValidationError({
                "point": "Either provide 'point' or both 'latitude' and 'longitude'."
            })
        
        # Validate timestamp is not in future
        if 'timestamp' in data:
            if data['timestamp'] > timezone.now() + timedelta(minutes=5):
                raise serializers.ValidationError({
                    "timestamp": "Timestamp cannot be more than 5 minutes in the future."
                })
        
        # Validate speed is non-negative
        if 'speed' in data and data['speed'] is not None:
            if data['speed'] < 0:
                raise serializers.ValidationError({
                    "speed": "Speed cannot be negative."
                })
        
        # Validate bearing is between 0 and 360
        if 'bearing' in data and data['bearing'] is not None:
            if not (0 <= data['bearing'] <= 360):
                raise serializers.ValidationError({
                    "bearing": "Bearing must be between 0 and 360 degrees."
                })
        
        return data


class ProgressionSerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    journey = serializers.PrimaryKeyRelatedField(queryset=Journey.objects.all(), required=False, allow_null=True)
    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(), required=False, allow_null=True)
    stop = serializers.PrimaryKeyRelatedField(queryset=Stop.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Progression
        fields = "__all__"
        ordering = ["-timestamp"]
    
    def validate(self, data):
        """Validate progression data."""
        # Validate timestamp
        if 'timestamp' in data:
            if data['timestamp'] > timezone.now() + timedelta(minutes=5):
                raise serializers.ValidationError({
                    "timestamp": "Timestamp cannot be more than 5 minutes in the future."
                })
        
        # Validate stop_sequence is positive
        if 'stop_sequence' in data and data['stop_sequence'] is not None:
            if data['stop_sequence'] < 1:
                raise serializers.ValidationError({
                    "stop_sequence": "Stop sequence must be a positive integer."
                })
        
        return data


class OccupancySerializer(serializers.HyperlinkedModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    journey = serializers.PrimaryKeyRelatedField(queryset=Journey.objects.all(), required=False, allow_null=True)
    occupancy_status_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Occupancy
        fields = "__all__"
        ordering = ["-timestamp"]
    
    def get_occupancy_status_display(self, obj):
        """Return human-readable occupancy status."""
        return obj.get_occupancy_status_display() if hasattr(obj, 'get_occupancy_status_display') else obj.occupancy_status
    
    def validate(self, data):
        """Validate occupancy data."""
        # Validate timestamp
        if 'timestamp' in data:
            if data['timestamp'] > timezone.now() + timedelta(minutes=5):
                raise serializers.ValidationError({
                    "timestamp": "Timestamp cannot be more than 5 minutes in the future."
                })
        
        # Validate occupancy_count is non-negative
        if 'occupancy_count' in data and data['occupancy_count'] is not None:
            if data['occupancy_count'] < 0:
                raise serializers.ValidationError({
                    "occupancy_count": "Occupancy count cannot be negative."
                })
        
        # Validate occupancy_percentage is between 0 and 100
        if 'occupancy_percentage' in data and data['occupancy_percentage'] is not None:
            if not (0 <= data['occupancy_percentage'] <= 100):
                raise serializers.ValidationError({
                    "occupancy_percentage": "Occupancy percentage must be between 0 and 100."
                })
        
        return data


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
    journey_status = serializers.CharField()
    direction_id = serializers.IntegerField()
    trip_headsign = serializers.CharField()


# -------------
# GTFS Realtime
# -------------
