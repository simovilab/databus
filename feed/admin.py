from django.contrib.gis import admin
from .models import *

# Register your models here.

admin.site.register(Vehicle)
admin.site.register(Operator)
admin.site.register(DataProvider)
admin.site.register(Equipment)
admin.site.register(Journey)
admin.site.register(Position, admin.GISModelAdmin)
admin.site.register(Progression)
admin.site.register(Occupancy)
