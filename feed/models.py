from django.contrib.gis.db import models
from django.contrib.gis.geos import Point

# Create your models here.


class OnBoardEquipment(models.Model):
    id = models.AutoField(primary_key=True)
    serial_number = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    owner = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.serial_number}: {self.brand} {self.model} ({self.owner})"
