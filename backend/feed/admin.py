"""Django admin registrations for the feed app's GTFS Schedule and Realtime models."""

from django.contrib.gis import admin

from .models import (
    TransitSystem,
    Agency,
    Calendar,
    CalendarDate,
    FareAttribute,
    FareRule,
    Feed,
    FeedInfo,
    FeedMessage,
    GeoShape,
    FeedPublisher,
    Route,
    RouteStop,
    Shape,
    Stop,
    StopTime,
    StopTimeUpdate,
    Trip,
    TripDuration,
    TripTime,
    TripUpdate,
    VehiclePosition,
)

# Register your models here.


class StopAdmin(admin.GISModelAdmin):
    """Admin form for Stop that hides the raw lat/lon fields in favor of stop_point."""

    exclude = ["stop_lat", "stop_lon"]


admin.site.register(TransitSystem)
admin.site.register(FeedPublisher)
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
