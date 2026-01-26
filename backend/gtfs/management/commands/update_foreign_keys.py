from django.core.management.base import BaseCommand
from gtfs.models import (
    Route,
    CalendarDate,
    Trip,
    StopTime,
    FareAttribute,
    FareRule,
    RouteStop,
    TripDuration,
    TripTime,
)


class Command(BaseCommand):
    help = "Update existing records to run the customized save method"

    def handle(self, *args, **kwargs):
        routes = Route.objects.all()
        calendar_dates = CalendarDate.objects.all()
        trips = Trip.objects.all()
        stop_times = StopTime.objects.all()
        fare_attributes = FareAttribute.objects.all()
        fare_rules = FareRule.objects.all()
        route_stops = RouteStop.objects.all()
        trip_durations = TripDuration.objects.all()
        trip_times = TripTime.objects.all()

        for route in routes:
            route.save()
        for calendar_date in calendar_dates:
            calendar_date.save()
        for trip in trips:
            trip.save()
        for stop_time in stop_times:
            stop_time.save()
        for fare_attribute in fare_attributes:
            fare_attribute.save()
        for fare_rule in fare_rules:
            fare_rule.save()
        for route_stop in route_stops:
            route_stop.save()
        for trip_duration in trip_durations:
            trip_duration.save()
        for trip_time in trip_times:
            trip_time.save()

        self.stdout.write(self.style.SUCCESS("Successfully updated records"))
