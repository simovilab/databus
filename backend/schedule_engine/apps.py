"""Django app configuration for schedule_engine."""

from django.apps import AppConfig


class ScheduleEngineConfig(AppConfig):
    """Django app config for schedule_engine, the GTFS-RT feed-projection app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "schedule_engine"
