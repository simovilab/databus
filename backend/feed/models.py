import re
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from gtfs.models import (
    BaseAgency,
    BaseStop,
    BaseRoute,
    BaseCalendar,
    BaseCalendarDate,
    BaseShape,
    BaseTrip,
    BaseStopTime,
    BaseFareAttribute,
    BaseFareRule,
    BaseFeedInfo,
)


def validate_no_spaces_or_special_symbols(value):
    if re.search(r"[^a-zA-Z0-9_]", value):
        raise ValidationError(
            "Este campo no puede contener espacios ni símbolos especiales, solamente letras, números y guiones bajos."
        )


class GTFSProvider(models.Model):
    """A provider provides transportation services GTFS data.

    It might or might not be the same as the agency in the GTFS feed. A GTFS provider can serve multiple agencies.
    """

    provider_id = models.BigAutoField(primary_key=True)
    code = models.CharField(
        max_length=31,
        help_text="Código (típicamente el acrónimo) de la empresa. No debe tener espacios ni símbolos especiales.",
        validators=[validate_no_spaces_or_special_symbols],
    )
    name = models.CharField(max_length=255, help_text="Nombre de la empresa.")
    description = models.TextField(
        blank=True, null=True, help_text="Descripción de la institución o empresa."
    )
    website = models.URLField(
        blank=True, null=True, help_text="Sitio web de la empresa."
    )
    schedule_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL del suministro (Feed) de GTFS Schedule (.zip).",
    )
    trip_updates_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL del suministro (FeedMessage) de la entidad GTFS Realtime TripUpdates (.pb).",
    )
    vehicle_positions_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL del suministro (FeedMessage) de la entidad GTFS Realtime VehiclePositions (.pb).",
    )
    service_alerts_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL del suministro (FeedMessage) de la entidad GTFS Realtime ServiceAlerts (.pb).",
    )
    timezone = models.CharField(
        max_length=63,
        help_text="Zona horaria del proveedor de datos (asume misma zona horaria para todas las agencias). Ejemplo: America/Costa_Rica.",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="¿Está activo el proveedor de datos? Si no, no se importarán los datos de este proveedor.",
    )

    def __str__(self):
        return f"{self.name} ({self.code})"


# -------------
# GTFS Schedule
# -------------


class Feed(models.Model):
    feed_id = models.CharField(max_length=100, primary_key=True, unique=True)
    gtfs_provider = models.ForeignKey(
        GTFSProvider, on_delete=models.SET_NULL, blank=True, null=True
    )
    http_etag = models.CharField(max_length=1023, blank=True, null=True)
    http_last_modified = models.DateTimeField(blank=True, null=True)
    is_current = models.BooleanField(blank=True, null=True)
    retrieved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.feed_id


class Agency(BaseAgency):
    """One or more transit agencies that provide the data in this feed.
    Maps to agency.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, to_field="feed_id", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "agency_id"], name="unique_agency_in_feed")
        ]
        verbose_name_plural = "agencies"

    def __str__(self):
        return self.agency_name


class Stop(BaseStop):
    """Individual locations where vehicles pick up or drop off riders.
    Maps to stops.txt in the GTFS feed.
    """

    STOP_HEADING_CHOICES = (
        ("N", "norte"),
        ("NE", "noreste"),
        ("E", "este"),
        ("SE", "sureste"),
        ("S", "sur"),
        ("SW", "suroeste"),
        ("W", "oeste"),
        ("NW", "noroeste"),
    )

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    stop_point = models.PointField(
        blank=True, null=True, help_text="Punto georreferenciado de la parada."
    )
    stop_heading = models.CharField(
        max_length=2, blank=True, null=True, choices=STOP_HEADING_CHOICES
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "stop_id"], name="unique_stop_in_feed")
        ]

    # Build stop_point or stop_lat and stop_lon
    def save(self, *args, **kwargs):
        if self.stop_point:
            self.stop_lat = self.stop_point.y
            self.stop_lon = self.stop_point.x
        else:
            self.stop_point = Point(self.stop_lon, self.stop_lat)
        super(Stop, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.stop_id}: {self.stop_name}"


class Route(BaseRoute):
    """A group of trips that are displayed to riders as a single service.
    Maps to routes.txt in the GTFS feed.

    agency is a field to store the Agency object related to the route.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_agency = models.ForeignKey(
        Agency, on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "route_id"], name="unique_route_in_feed")
        ]

    def save(self, *args, **kwargs):
        self.linked_agency = Agency.objects.get(
            feed=self.feed, agency_id=self.agency_id
        )
        super(Route, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.route_short_name}: {self.route_long_name}"


class Calendar(BaseCalendar):
    """Dates for service IDs using a weekly schedule.
    Maps to calendar.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "service_id"], name="unique_service_in_feed"
            )
        ]

    def __str__(self):
        return self.service_id


class CalendarDate(BaseCalendarDate):
    """Exceptions for the service IDs defined in the calendar.txt file.
    Maps to calendar_dates.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_service = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, blank=True, null=True
    )
    holiday_name = models.CharField(
        max_length=255,
        default="Feriado",
        help_text="Nombre de la festividad o feriado.",
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "service_id", "date"], name="unique_date_in_feed"
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_service = Calendar.objects.get(
            feed=self.feed, service_id=self.service_id
        )
        super(CalendarDate, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.holiday_name} ({self.service_id})"


class Shape(BaseShape):
    """Rules for drawing lines on a map to represent a transit organization's routes.
    Maps to shapes.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "shape_id", "shape_pt_sequence"],
                name="unique_shape_in_feed",
            )
        ]

    def __str__(self):
        return f"{self.shape_id}: {self.shape_pt_sequence}"


class Trip(BaseTrip):
    """Trips for each route. A trip is a sequence of two or more stops that occurs at specific time.
    Maps to trips.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )
    linked_service = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, blank=True, null=True
    )
    geoshape = models.ForeignKey(
        "GeoShape", on_delete=models.SET_NULL, blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "trip_id"], name="unique_trip_in_feed")
        ]

    def save(self, *args, **kwargs):
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        self.linked_service = Calendar.objects.get(
            feed=self.feed, service_id=self.service_id
        )
        super(Trip, self).save(*args, **kwargs)

    def __str__(self):
        return self.trip_id


class StopTime(BaseStopTime):
    """Times that a vehicle arrives at and departs from individual stops for each trip.
    Maps to stop_times.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, blank=True, null=True
    )
    linked_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "trip_id", "stop_sequence"],
                name="unique_stoptime_in_feed",
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_trip = Trip.objects.get(feed=self.feed, trip_id=self.trip_id)
        self.linked_stop = Stop.objects.get(feed=self.feed, stop_id=self.stop_id)
        super(StopTime, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_id}: {self.stop_id} ({self.stop_sequence})"


class FareAttribute(BaseFareAttribute):
    """Rules for how to calculate the fare for a certain kind of trip.
    Maps to fare_attributes.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_agency = models.ForeignKey(
        Agency, on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "fare_id"], name="unique_fareattribute_in_feed"
            )
        ]

    def save(self, *args, **kwargs):
        if self.agency_id:
            self.linked_agency = Agency.objects.get(
                feed=self.feed, agency_id=self.agency_id
            )
        super(FareAttribute, self).save(*args, **kwargs)

    def __str__(self):
        return self.fare_id


class FareRule(BaseFareRule):
    """Rules for which fare to apply in a given situation.
    Maps to fare_rules.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    linked_fare = models.ForeignKey(
        FareAttribute, on_delete=models.CASCADE, blank=True, null=True
    )
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "feed",
                    "fare_id",
                    "route_id",
                    "origin_id",
                    "destination_id",
                    "contains_id",
                ],
                name="unique_fare_rule_in_feed",
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_fare = FareAttribute.objects.get(
            feed=self.feed, fare_id=self.fare_id
        )
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        super(FareRule, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.fare_id}: {self.route_id}"


class FeedInfo(BaseFeedInfo):
    """Additional information about the feed itself, including publisher, version, and expiration information.
    Maps to feed_info.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.feed_publisher_name}: {self.feed_version}"


# ----------------
# Auxiliary models
# ----------------


class GeoShape(models.Model):
    """Rules for drawing lines on a map to represent a transit organization's routes.
    Maps to shapes.txt in the GTFS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    shape_id = models.CharField(
        max_length=255, help_text="Identificador único de la trayectoria."
    )
    geometry = models.LineStringField(
        help_text="Trayectoria de la ruta.",
        # dim=3, # To store 3D coordinates (x, y, z)
    )
    shape_name = models.CharField(max_length=255, blank=True, null=True)
    shape_desc = models.TextField(blank=True, null=True)
    shape_from = models.CharField(max_length=255, blank=True, null=True)
    shape_to = models.CharField(max_length=255, blank=True, null=True)
    has_altitude = models.BooleanField(
        help_text="Indica si la trayectoria tiene datos de altitud", default=False
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "shape_id"], name="unique_geoshape_in_feed"
            )
        ]

    def __str__(self):
        return self.shape_id


class RouteStop(models.Model):
    """Describes the sequence of stops for a route and a shape."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    route_id = models.CharField(max_length=200)
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )
    shape_id = models.CharField(max_length=200)
    linked_shape = models.ForeignKey(
        GeoShape, on_delete=models.CASCADE, blank=True, null=True
    )
    direction_id = models.PositiveIntegerField()
    stop_id = models.CharField(max_length=200)
    linked_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_sequence = models.PositiveIntegerField()
    timepoint = models.BooleanField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "route_id", "shape_id", "stop_sequence"],
                name="unique_routestop_in_feed",
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        self.linked_shape = GeoShape.objects.get(feed=self.feed, shape_id=self.shape_id)
        self.linked_stop = Stop.objects.get(feed=self.feed, stop_id=self.stop_id)
        super(RouteStop, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.route_id}: {self.stop_id} ({self.shape_id} {self.stop_sequence})"


class TripDuration(models.Model):
    """Describes the duration of a trip for a route and a service."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    route_id = models.CharField(max_length=200)
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )
    shape_id = models.CharField(max_length=200)
    linked_shape = models.ForeignKey(
        Shape, on_delete=models.CASCADE, blank=True, null=True
    )
    service_id = models.CharField(max_length=200)
    linked_service = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, blank=True, null=True
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    stretch = models.PositiveIntegerField()
    stretch_duration = models.DurationField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "feed",
                    "route_id",
                    "shape_id",
                    "service_id",
                    "start_time",
                    "stretch",
                ],
                name="unique_tripduration_in_feed",
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        self.linked_shape = Shape.objects.get(feed=self.feed, shape_id=self.shape_id)
        self.linked_service = Calendar.objects.get(
            feed=self.feed, service_id=self.service_id
        )
        super(TripDuration, self).save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.route_id}: {self.service_id} ({self.start_time} - {self.end_time})"
        )


class TripTime(models.Model):
    """
    TODO: llenar cuando se hace el proceso de importación de GTFS. Este modelo se llena con los datos de stop_times.txt, con las filas donde timepoint = True.
    """

    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    trip_id = models.CharField(max_length=200)
    linked_trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_id = models.CharField(max_length=200)
    linked_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_sequence = models.PositiveIntegerField()
    departure_time = models.TimeField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "trip_id", "stop_id"],
                name="unique_triptime_in_feed",
            )
        ]

    def save(self, *args, **kwargs):
        self.linked_trip = Trip.objects.get(feed=self.feed, trip_id=self.trip_id)
        self.linked_stop = Stop.objects.get(feed=self.feed, stop_id=self.stop_id)
        super(TripTime, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_id}: {self.stop_id} ({self.departure_time})"


# -------------
# GTFS Realtime
# -------------


class FeedMessage(models.Model):
    """
    Header of a GTFS Realtime FeedMessage.

    This is metadata to link records of other models to a retrieved FeedMessage containing several entities, typically (necessarily, in this implementation) of a single kind.
    """

    ENTITY_TYPE_CHOICES = (
        ("trip_update", "TripUpdate"),
        ("vehicle", "VehiclePosition"),
        ("alert", "Alert"),
    )

    feed_message_id = models.CharField(max_length=63, primary_key=True)
    provider = models.ForeignKey(
        GTFSProvider, on_delete=models.SET_NULL, blank=True, null=True
    )
    entity_type = models.CharField(max_length=63, choices=ENTITY_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now=True)
    incrementality = models.CharField(max_length=15)
    gtfs_realtime_version = models.CharField(max_length=15)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.entity_type} ({self.timestamp})"


class TripUpdate(models.Model):
    """
    GTFS Realtime TripUpdate entity v2.0 (normalized).

    Trip updates represent fluctuations in the timetable.
    """

    id = models.BigAutoField(primary_key=True)
    entity_id = models.CharField(max_length=127)

    # Foreign key to FeedMessage model
    feed_message = models.ForeignKey("FeedMessage", on_delete=models.CASCADE)

    # TripDescriptor (message)
    trip_trip_id = models.CharField(max_length=255, blank=True, null=True)
    trip_route_id = models.CharField(max_length=255, blank=True, null=True)
    trip_direction_id = models.IntegerField(blank=True, null=True)
    trip_start_time = models.DurationField(blank=True, null=True)
    trip_start_date = models.DateField(blank=True, null=True)
    trip_schedule_relationship = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # VehicleDescriptor (message)
    vehicle_id = models.CharField(max_length=255, blank=True, null=True)
    vehicle_label = models.CharField(max_length=255, blank=True, null=True)
    vehicle_license_plate = models.CharField(max_length=255, blank=True, null=True)
    vehicle_wheelchair_accessible = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # Timestamp (uint64)
    timestamp = models.DateTimeField(blank=True, null=True)

    # Delay (int32)
    delay = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.entity_id} ({self.feed_message})"


class StopTimeUpdate(models.Model):
    """
    GTFS Realtime TripUpdate message v2.0 (normalized).

    Realtime update for arrival and/or departure events for a given stop on a trip, linked to a TripUpdate entity in a FeedMessage.
    """

    id = models.BigAutoField(primary_key=True)

    # Foreign key to FeedMessage and TripUpdate models
    feed_message = models.ForeignKey(FeedMessage, on_delete=models.CASCADE)
    trip_update = models.ForeignKey(TripUpdate, on_delete=models.CASCADE)

    # Stop ID (string)
    stop_sequence = models.IntegerField(blank=True, null=True)
    stop_id = models.CharField(max_length=127, blank=True, null=True)

    # StopTimeEvent (message): arrival
    arrival_delay = models.IntegerField(blank=True, null=True)
    arrival_time = models.DateTimeField(blank=True, null=True)
    arrival_uncertainty = models.IntegerField(blank=True, null=True)

    # StopTimeEvent (message): departure
    departure_delay = models.IntegerField(blank=True, null=True)
    departure_time = models.DateTimeField(blank=True, null=True)
    departure_uncertainty = models.IntegerField(blank=True, null=True)

    # OccupancyStatus (enum)
    departure_occupancy_status = models.CharField(max_length=255, blank=True, null=True)

    # ScheduleRelationship (enum)
    schedule_relationship = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.stop_id} ({self.trip_update})"


class VehiclePosition(models.Model):
    """
    GTFS Realtime VehiclePosition entity v2.0 (normalized).

    Vehicle position represents a few basic pieces of information about a particular vehicle on the network.
    """

    id = models.BigAutoField(primary_key=True)
    entity_id = models.CharField(max_length=127)

    # Foreign key to FeedMessage model
    feed_message = models.ForeignKey(
        FeedMessage, on_delete=models.CASCADE, blank=True, null=True
    )

    # TripDescriptor (message)
    vehicle_trip_trip_id = models.CharField(max_length=255)
    vehicle_trip_route_id = models.CharField(max_length=255, blank=True, null=True)
    vehicle_trip_direction_id = models.IntegerField(blank=True, null=True)
    vehicle_trip_start_time = models.DurationField(blank=True, null=True)
    vehicle_trip_start_date = models.DateField(blank=True, null=True)
    vehicle_trip_schedule_relationship = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # VehicleDescriptor (message)
    vehicle_vehicle_id = models.CharField(max_length=255, blank=True, null=True)
    vehicle_vehicle_label = models.CharField(max_length=255, blank=True, null=True)
    vehicle_vehicle_license_plate = models.CharField(
        max_length=255, blank=True, null=True
    )
    vehicle_vehicle_wheelchair_accessible = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # Position (message)
    vehicle_position_latitude = models.FloatField(blank=True, null=True)
    vehicle_position_longitude = models.FloatField(blank=True, null=True)
    vehicle_position_point = models.PointField(srid=4326, blank=True, null=True)
    vehicle_position_bearing = models.FloatField(blank=True, null=True)
    vehicle_position_odometer = models.FloatField(blank=True, null=True)
    vehicle_position_speed = models.FloatField(blank=True, null=True)  # (meters/second)

    # Current stop sequence (uint32)
    vehicle_current_stop_sequence = models.IntegerField(blank=True, null=True)

    # Stop ID (string)
    vehicle_stop_id = models.CharField(max_length=255, blank=True, null=True)

    # VehicleStopStatus (enum)
    vehicle_current_status = models.CharField(max_length=255, blank=True, null=True)

    # Timestamp (uint64)
    vehicle_timestamp = models.DateTimeField(blank=True, null=True)

    # CongestionLevel (enum)
    vehicle_congestion_level = models.CharField(max_length=255, blank=True, null=True)

    # OccupancyStatus (enum)
    vehicle_occupancy_status = models.CharField(max_length=255, blank=True, null=True)

    # OccupancyPercentage (uint32)
    vehicle_occupancy_percentage = models.FloatField(blank=True, null=True)

    # CarriageDetails (message): not implemented

    def save(self, *args, **kwargs):
        self.vehicle_position_point = Point(
            self.vehicle_position_longitude, self.vehicle_position_latitude
        )
        super(VehiclePosition, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.entity_id} ({self.feed_message})"


class Alert(models.Model):
    """Alerts and warnings about the service.
    Maps to alerts.txt in the GTFS feed.

    TODO: ajustar con Alerts de GTFS Realtime
    """

    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    alert_id = models.CharField(
        max_length=255, help_text="Identificador único de la alerta."
    )
    route_id = models.CharField(max_length=255, help_text="Identificador de la ruta.")
    trip_id = models.CharField(max_length=255, help_text="Identificador del viaje.")
    service_date = models.DateField(
        help_text="Fecha del servicio descrito por la alerta."
    )
    service_start_time = models.TimeField(
        help_text="Hora de inicio del servicio descrito por la alerta."
    )
    service_end_time = models.TimeField(
        help_text="Hora de finalización del servicio descrito por la alerta."
    )
    alert_header = models.CharField(
        max_length=255, help_text="Encabezado de la alerta."
    )
    alert_description = models.TextField(help_text="Descripción de la alerta.")
    alert_url = models.URLField(blank=True, null=True, help_text="URL de la alerta.")
    cause = models.PositiveIntegerField(
        choices=(
            (1, "Otra causa"),
            (2, "Accidente"),
            (3, "Congestión"),
            (4, "Evento"),
            (5, "Mantenimiento"),
            (6, "Planificado"),
            (7, "Huelga"),
            (8, "Manifestación"),
            (9, "Demora"),
            (10, "Cierre"),
        ),
        help_text="Causa de la alerta.",
    )
    effect = models.PositiveIntegerField(
        choices=(
            (1, "Otro efecto"),
            (2, "Desviación"),
            (3, "Adelanto"),
            (4, "Cancelación"),
            (5, "Cierre"),
            (6, "Desvío"),
            (7, "Detención"),
            (8, "Desconocido"),
        ),
        help_text="Efecto de la alerta.",
    )
    severity = models.PositiveIntegerField(
        choices=(
            (1, "Desconocido"),
            (2, "Información"),
            (3, "Advertencia"),
            (4, "Grave"),
            (5, "Muy grave"),
        ),
        help_text="Severidad de la alerta.",
    )
    published = models.DateTimeField(
        help_text="Fecha y hora de publicación de la alerta."
    )
    updated = models.DateTimeField(
        help_text="Fecha y hora de actualización de la alerta."
    )
    informed_entity = models.JSONField(help_text="Entidades informadas por la alerta.")

    def __str__(self):
        return self.alert_id
