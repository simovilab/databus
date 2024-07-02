from gtfs.models import Provider
from feed.models import Vehicle, Equipment, Trip, Position, Journey, Occupancy
from rest_framework import serializers
from django.contrib.gis.geos import Point


class VehicleSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "url",
            "label",
            "license_plate",
            "wifi",
            "air_conditioning",
            "mobile_charging",
            "bike_rack",
        ]
        ordering = ["id"]


class EquipmentSerializer(serializers.HyperlinkedModelSerializer):

    provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.all())
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())

    class Meta:
        model = Equipment
        fields = [
            "url",
            "provider",
            "vehicle",
            "brand",
            "model",
            "serial_number",
            "software_version",
        ]
        ordering = ["id"]


class TripSerializer(serializers.HyperlinkedModelSerializer):

    equipment = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = [
            "url",
            "equipment",
            "trip_id",
            "route_id",
            "direction_id",
            "start_time",
            "start_date",
            "schedule_relationship",
            "shape_id",
            "ongoing",
        ]
        ordering = ["id"]


class PositionSerializer(serializers.HyperlinkedModelSerializer):

    trip = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.filter(in_progress=True)
    )
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "url",
            "trip",
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

    def create(self, validated_data):
        latitude = validated_data.pop("latitude")
        longitude = validated_data.pop("longitude")
        point = Point(longitude, latitude)
        return Position.objects.create(point=point, **validated_data)


class JourneySerializer(serializers.HyperlinkedModelSerializer):

    trip = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.filter(in_progress=True)
    )

    class Meta:
        model = Journey
        fields = [
            "url",
            "trip",
            "timestamp",
            "current_stop_sequence",
            "stop_id",
            "current_status",
            "congestion_level",
        ]
        ordering = ["id"]


class OccupancySerializer(serializers.HyperlinkedModelSerializer):

    trip = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.filter(in_progress=True)
    )

    class Meta:
        model = Occupancy
        fields = [
            "url",
            "trip",
            "timestamp",
            "occupancy_status",
            "occupancy_percentage",
            "occupancy_count",
        ]
        ordering = ["id"]
