from django.db import models

# Create your models here.


class EstimationModel(models.Model):
    id = models.AutoField(primary_key=True)
    route_id = models.CharField(max_length=100)
    shape_id = models.CharField(max_length=100)
    service_id = models.CharField(max_length=100)
    stop_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
