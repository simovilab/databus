from django.urls import path

from . import views

urlpatterns = [
    path("", views.gtfs, name="gtfs"),
    path("schedule/bUCR_GTFS.zip", views.schedule, name="schedule"),
    path("realtime/vehicle_positions.json", views.vehicle_json, name="vehicle_json"),
    path("realtime/vehicle_positions.pb", views.vehicle_pb, name="vehicle_pb"),
    path("realtime/trip_updates.json", views.trip_updates_json, name="trip_updates_json"),
    path("realtime/trip_updates.pb", views.trip_updates_pb, name="trip_updates_pb"),
]
