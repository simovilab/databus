from django.contrib.gis.db import models
from django.contrib.gis.geos import Point

# Create your models here.


class BusData(models.Model):

    id = models.AutoField(primary_key=True)
    vehicle_id = models.CharField(max_length=100, blank=True, null=True)
    route_id = models.CharField(max_length=100, blank=True, null=True)
    trip_id = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    location_latitude = models.FloatField(blank=True, null=True)
    location_longitude = models.FloatField(blank=True, null=True)
    location_point = models.PointField(blank=True, null=True)
    inertial_bearing = models.IntegerField(blank=True, null=True)
    intertial_speed = models.FloatField(blank=True, null=True)
    vehicle_health_fuel_level = models.FloatField(blank=True, null=True)
    vehicle_health_oil_level = models.FloatField(blank=True, null=True)
    environmental_temperature = models.FloatField(blank=True, null=True)

    received_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.location_point = Point(self.location_longitude, self.location_latitude)
        super(BusData, self).save(*args, **kwargs)

    def __str__(self):
        return self.vehicle_id
