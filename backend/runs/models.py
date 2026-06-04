from django.contrib.gis.db import models
from operations.models import Vehicle, Operator
from runs.domain.lifecycle import RunLifecycleStates, choices
import uuid

# Create your models here.


class Run(models.Model):
    """A run is an instance of GTFS trip."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)

    # Operational information
    vehicle = models.ManyToManyField(Vehicle, blank=True)
    operator = models.ManyToManyField(Operator, blank=True)

    # GTFS Schedule information
    route_id = models.CharField(max_length=100, blank=True, null=True)
    trip_id = models.CharField(max_length=100, blank=True, null=True)
    direction_id = models.PositiveSmallIntegerField(blank=True, null=True)
    shape_id = models.CharField(max_length=100, blank=True, null=True)

    # Run information
    request_timestamp = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    start_time = models.DurationField(blank=True, null=True)
    schedule_relationship = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("SCHEDULED", "Scheduled in GTFS"),
            ("ADDED", "Added to schedule"),
            ("UNSCHEDULED", "Unscheduled"),
            ("CANCELED", "Canceled"),
            ("DUPLICATED", "Duplicated"),
            ("DELETED", "Deleted"),
        ],
    )
    run_lifecycle_state = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        choices=choices,
        default=RunLifecycleStates.REQUESTED,
    )
    last_event_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.route_id} / {self.trip_id} ({self.start_date})"


class RunLifecycleTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=128)
    from_state = models.CharField(max_length=64, null=True)
    to_state = models.CharField(max_length=64, null=True)
    guards = models.JSONField(default=dict, blank=True, null=True)
    actions = models.JSONField(default=dict, blank=True, null=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "timestamp"]),
            models.Index(fields=["event_name"]),
        ]


class RunProgressEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    run = models.ForeignKey(Run, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=128)
    stop_id = models.CharField(max_length=64, null=True)
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "timestamp"]),
            models.Index(fields=["event_type"]),
        ]


class Position(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    timestamp = models.DateTimeField()
    point = models.PointField(blank=True, null=True)
    altitude = models.FloatField(blank=True, null=True)
    speed = models.FloatField(blank=True, null=True)
    bearing = models.FloatField(blank=True, null=True)
    odometer = models.FloatField(blank=True, null=True)
    is_new = models.BooleanField(default=True)


class VehicleStopStatus(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
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


class CongestionLevel(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
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


class OccupancyStatus(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
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
    is_wheelchair_accesible = models.CharField(
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

    is_new = models.BooleanField(default=True)


"""
Mapping for GTFS Realtime VehiclePosition to our data model:

Run:
- trip (Redis (hash): run:<run_id>:trip)
- vehicle (Redis (hash): run:<run_id>:vehicle)

Position:
- position (Redis (hash): run:<run_id>:position)

VehicleStopStatus:
- current_stop_sequence (Redis (string): run:<run_id>:current_stop_sequence)
- stop_id (Redis (string): run:<run_id>:stop_id)
- current_status (Redis (string): run:<run_id>:current_status)

CongestionLevel:
- congestion_level (Redis (string): run:<run_id>:congestion_level)

OccupancyStatus:
- occupancy_status (Redis (string): run:<run_id>:occupancy_status)
- occupancy_percentage (Redis (string): run:<run_id>:occupancy_percentage)

Not mapped:
- multi_carriage_details (omitted)
- timestamp
"""
