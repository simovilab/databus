from django.contrib.gis import admin
from .models import (
    Run,
    Position,
    Progression,
    Occupancy,
)

# Register your models here.

admin.site.register(Run)
admin.site.register(Position, admin.GISModelAdmin)
admin.site.register(Progression)
admin.site.register(Occupancy)
