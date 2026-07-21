from django.contrib.gis import admin
from .models import (
    Vehicle,
    Operator,
    DataProvider,
    Company,
    Equipment,
    EquipmentLog,
    Sensor,
)

# Register your models here.

admin.site.register(Vehicle)
admin.site.register(Operator)
admin.site.register(DataProvider)
admin.site.register(Company, admin.GISModelAdmin)
admin.site.register(Equipment)
admin.site.register(EquipmentLog)
admin.site.register(Sensor)
