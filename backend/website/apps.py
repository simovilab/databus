"""Django AppConfig for the website app."""

from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    """Django app configuration for `website` (public landing pages)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "website"
