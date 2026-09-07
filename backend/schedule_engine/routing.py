"""ASGI WebSocket URL routing for schedule_engine's status broadcast channel."""

from django.urls import re_path

from .consumers import StatusConsumer

websocket_urlpatterns = [
    re_path(r"ws/status/$", StatusConsumer.as_asgi()),
]
