from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
import uuid

from gtfs.models import Provider

# Create your models here.


class Vehicle(models.Model):
    AMENITIES_CHOICES = [
        ("NO_VALUE", "No hay información"),
        ("UNKNOWN", "Desconocido"),
        ("AVAILABLE", "Disponible"),
        ("UNAVAILABLE", "No disponible"),
    ]

    id = models.CharField(max_length=100, primary_key=True)
    label = models.CharField(max_length=100, blank=True, null=True)
    license_plate = models.CharField(max_length=100, blank=True, null=True)
    wheelchair_accessible = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("NO_VALUE", "No hay información"),
            ("UNKNOWN", "Desconocido"),
            ("WHEELCHAIR_ACCESIBLE", "Accesible para silla de ruedas"),
            ("WHEELCHAIR_INACCESIBLE", "No accesible para silla de ruedas"),
        ],
    )
    wifi = models.CharField(
        max_length=100, blank=True, null=True, choices=AMENITIES_CHOICES
    )
    air_conditioning = models.CharField(
        max_length=100, blank=True, null=True, choices=AMENITIES_CHOICES
    )
    mobile_charging = models.CharField(
        max_length=100, blank=True, null=True, choices=AMENITIES_CHOICES
    )
    bike_rack = models.CharField(
        max_length=100, blank=True, null=True, choices=AMENITIES_CHOICES
    )
    has_screen = models.BooleanField(default=False)
    has_headsign_screen = models.BooleanField(default=False)
    has_audio = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.label} ({self.license_plate})"


class Equipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        Provider, on_delete=models.SET_NULL, blank=True, null=True
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, blank=True, null=True
    )
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    software_version = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _str_(self):
        return f"{self.provider}: {self.brand} {self.model}"


class Trip(models.Model):
    id = models.AutoField(primary_key=True)
    equipment = models.ForeignKey(
        Equipment, on_delete=models.SET_NULL, blank=True, null=True
    )

    trip_id = models.CharField(max_length=100, blank=True, null=True)
    route_id = models.CharField(max_length=100, blank=True, null=True)
    direction_id = models.PositiveSmallIntegerField(blank=True, null=True)
    start_time = models.DurationField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    schedule_relationship = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("SCHEDULED", "Agendado"),
            ("ADDED", "Agregado"),
            ("UNSCHEDULED", "No agendado"),
            ("CANCELED", "Cancelado"),
            ("DUPLICATED", "Duplicado"),
            ("DELETED", "Borrado"),
        ],
    )
    shape_id = models.CharField(max_length=100, blank=True, null=True)
    ongoing = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.route_id} / {self.trip_id} ({self.start_date})"


class Position(models.Model):
    id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)

    timestamp = models.DateTimeField()
    point = models.PointField(blank=True, null=True)
    bearing = models.FloatField(blank=True, null=True)
    odometer = models.FloatField(blank=True, null=True)
    speed = models.FloatField(blank=True, null=True)


class Path(models.Model):
    id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    current_stop_sequence = models.PositiveIntegerField(blank=True, null=True)
    stop_id = models.CharField(max_length=100, blank=True, null=True)
    current_status = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("INCOMING_AT", "Llegando a la parada"),
            ("STOPPED_AT", "Detenido en la parada"),
            ("IN_TRANSIT_TO", "En tránsito a la parada"),
        ],
    )
    congestion_level = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("UNKNOWN_CONGESTION_LEVEL", "Nivel de congestión desconocido"),
            ("RUNNING_SMOOTHLY", "Tráfico fluido"),
            ("STOP_AND_GO", "Tráfico fluctuante"),
            ("CONGESTION", "Congestión"),
            ("SEVERE_CONGESTION", "Congestión severa"),
        ],
    )


class Occupancy(models.Model):
    id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    occupancy_status = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("EMPTY", "Vacío"),
            ("MANY_SEATS_AVAILABLE", "Muchos asientos disponibles"),
            ("FEW_SEATS_AVAILABLE", "Pocos asientos disponibles"),
            ("STANDING_ROOM_ONLY", "Solo espacio de pie"),
            ("CRUSHED_STANDING_ROOM_ONLY", "Solo espacio de pie apretado"),
            ("FULL", "Lleno"),
            ("NOT_ACCEPTING_PASSENGERS", "No acepta pasajeros"),
            ("NO_DATA_AVAILABLE", "No hay datos disponibles"),
            ("NOT_BOARDABLE", "No es posible abordar este tipo de vehículo"),
        ],
    )
    occupancy_percentage = models.IntegerField(blank=True, null=True)
    occupancy_count = models.PositiveIntegerField(blank=True, null=True)
