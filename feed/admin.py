from django.contrib.gis import admin
from .models import *

# Register your models here.

admin.site.register(Vehicle)
admin.site.register(Equipment)
admin.site.register(Trip)
admin.site.register(Position, admin.GISModelAdmin)
admin.site.register(Journey)
admin.site.register(Occupancy)
