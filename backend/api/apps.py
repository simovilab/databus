"""Django app configuration for the api app."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configure the api app (DRF ViewSets/serializers exposing GTFS and run data)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
