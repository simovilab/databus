from django.urls import path

from . import views

urlpatterns = [
    path("", views.gtfs, name="gtfs"),
    path("vehicle_positions.json", views.vehicle_json, name="vehicle_json"),
    path("vehicle_positions.pb", views.vehicle_pb, name="vehicle_pb"),
]
