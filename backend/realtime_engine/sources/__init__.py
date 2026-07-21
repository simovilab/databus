"""Pluggable telemetry source adapters.

Importing this package registers all built-in adapters (currently the
generic HTTP+JSON adapter, kind ``"http"``) with the ``base`` registry, so
``get_adapter("http")`` works immediately after
``import realtime_engine.sources``.
"""

from . import http_json  # noqa: F401 -- import for its registration side effect
from .base import get_adapter, register

__all__ = ["get_adapter", "register"]
