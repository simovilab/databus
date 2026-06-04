from django.contrib.gis import admin
from .models import Run, Position, VehicleStopStatus, CongestionLevel, OccupancyStatus

# Register your models here.

admin.site.register(Run)
admin.site.register(Position, admin.GISModelAdmin)
admin.site.register(VehicleStopStatus)
admin.site.register(CongestionLevel)
admin.site.register(OccupancyStatus)
