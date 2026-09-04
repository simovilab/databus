"""URL routes for the website app."""

from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="inicio"),
]
