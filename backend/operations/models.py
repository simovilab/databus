"""Fleet/operator/vehicle/equipment domain models: Company, Operator, Vehicle, Equipment, Sensor, EquipmentLog."""

from typing import Any

from django.contrib.gis.db import models
from django.contrib.auth.models import User
import uuid

from feed.models import Agency

# Create your models here.


class Company(models.Model):
    """
    A wrapper for the Agency model from GTFS. The legal entity behind it.
    """

    id = models.CharField(max_length=100, primary_key=True)
    # django-stubs can't infer the implicit through-model type parameter for
    # this M2M from the call alone; the explicit annotation resolves it.
    linked_agency: models.ManyToManyField[Agency, Any] = models.ManyToManyField(
        Agency, blank=True
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    legal_id = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    location = models.PointField(blank=True, null=True)
    logo = models.ImageField(upload_to="companies/", blank=True, null=True)

    def __str__(self) -> str:
        """Return the company's name."""
        return self.name


class Operator(models.Model):
    """
    A person. A driver, dispatcher or administrator of a given company.
    """

    id = models.CharField(max_length=100, primary_key=True, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ManyToManyField(Company)
    phone = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(upload_to="operators/", blank=True, null=True)
    is_driver = models.BooleanField(default=False)
    is_dispatcher = models.BooleanField(default=False)
    is_administrator = models.BooleanField(default=False)

    def __str__(self) -> str:
        """Return the operator's full name and ID."""
        return f"{self.user.first_name} {self.user.last_name} ({self.id})"


class DataProvider(models.Model):
    """
    A GTFS and telemetry data provider for a given company. Owner of the equipments.
    """

    id = models.CharField(max_length=127, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    logo = models.ImageField(upload_to="data-providers/", blank=True, null=True)

    def __str__(self) -> str:
        """Return the data provider's name."""
        return self.name


class Vehicle(models.Model):
    """
    A vehicle belonging to a company. Used in GTFS.
    """

    AMENITIES_CHOICES = [
        ("NO_VALUE", "No hay información"),
        ("UNKNOWN", "Desconocido"),
        ("AVAILABLE", "Disponible"),
        ("UNAVAILABLE", "No disponible"),
    ]

    id = models.CharField(max_length=100, primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, blank=True, null=True
    )
    label = models.CharField(max_length=100, blank=True, null=True)
    license_plate = models.CharField(max_length=31)
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
    status = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("IN_SERVICE", "En servicio"),
            ("OUT_OF_SERVICE", "Fuera de servicio"),
            ("ON_FIRE", "En llamas"),
        ],
    )

    def __str__(self) -> str:
        """Return the vehicle's company and license plate."""
        return f"{self.company}: {self.license_plate}"


class Equipment(models.Model):
    """An onboard telemetry device (GPS/sensor unit) installed in a vehicle."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_provider = models.ForeignKey(
        DataProvider, on_delete=models.PROTECT, blank=True, null=True
    )
    name = models.CharField(max_length=100, blank=True, null=True)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, blank=True, null=True
    )
    # Hardware/firmware information
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True)
    app_version = models.CharField(max_length=100, blank=True, null=True)

    status = models.CharField(
        max_length=100,
        choices=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
        default="ACTIVE",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the equipment, then append a snapshot of its current fields to EquipmentLog."""
        super(Equipment, self).save(*args, **kwargs)
        EquipmentLog.objects.create(
            equipment=self,
            data_provider=self.data_provider,
            vehicle=self.vehicle,
            serial_number=self.serial_number,
            brand=self.brand,
            model=self.model,
            os_version=self.os_version,
            app_version=self.app_version,
            status=self.status,
        )

    def __str__(self) -> str:
        """Return the equipment's data provider, brand, model, and ID."""
        return f"{self.data_provider}: {self.name} ({self.id})"


class Sensor(models.Model):
    """A logical data feed (of one or more telemetry types) registered on a piece of Equipment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, blank=True, null=True
    )
    # Data provided (type of sensor)
    provides_vehicle = models.BooleanField(default=False)
    provides_operator = models.BooleanField(default=False)
    provides_run = models.BooleanField(default=False)
    provides_position = models.BooleanField(default=False)
    provides_progression = models.BooleanField(default=False)
    provides_occupancy = models.BooleanField(default=False)
    provides_conditions = models.BooleanField(default=False)
    provides_emissions = models.BooleanField(default=False)
    provides_travelers = models.BooleanField(default=False)
    provides_authorizations = models.BooleanField(default=False)
    provides_fares = models.BooleanField(default=False)
    provides_transfers = models.BooleanField(default=False)
    provides_alerts = models.BooleanField(default=False)
    # Registration
    source_type = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        choices=[("mqtt", "MQTT"), ("http", "HTTP"), ("both", "Both")],
    )
    source_http_url = models.URLField(blank=True, null=True)
    source_json_mapping = models.JSONField(blank=True, null=True)

    status = models.CharField(
        max_length=100,
        choices=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
        default="ACTIVE",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the sensor's name and ID."""
        return f"{self.name} ({self.id})"


class EquipmentLog(models.Model):
    """An immutable snapshot of an Equipment's fields, written each time the equipment is saved."""

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT)
    data_provider = models.ForeignKey(
        DataProvider, on_delete=models.PROTECT, blank=True, null=True
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, blank=True, null=True
    )
    # Equipment information
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True)
    app_version = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=100,
        choices=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
        default="ACTIVE",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return the log entry's data provider, brand, model, and timestamp."""
        return f"{self.data_provider}: {self.brand} {self.model} ({self.updated_at})"
