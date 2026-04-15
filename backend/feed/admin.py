from django.contrib.gis import admin

from .models import *

# Register your models here.


class StopAdmin(admin.GISModelAdmin):
    exclude = ["stop_lat", "stop_lon"]


admin.site.register(GTFSProvider)
admin.site.register(Feed)
admin.site.register(Agency)
admin.site.register(Stop, StopAdmin)
admin.site.register(Route)
admin.site.register(Calendar)
admin.site.register(CalendarDate)
admin.site.register(Shape)
admin.site.register(GeoShape, admin.GISModelAdmin)
admin.site.register(Trip)
admin.site.register(StopTime)
admin.site.register(FareAttribute)
admin.site.register(FareRule)
admin.site.register(FeedInfo)
admin.site.register(RouteStop)
admin.site.register(TripDuration)
admin.site.register(TripTime)
admin.site.register(FeedMessage)
admin.site.register(TripUpdate)
admin.site.register(StopTimeUpdate)
admin.site.register(VehiclePosition, admin.GISModelAdmin)
