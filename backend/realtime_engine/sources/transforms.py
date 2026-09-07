"""Pure data-shape helpers for HTTP telemetry sources.

Ported from navsat-bridge's ``transforms`` module (``kmh_to_ms``, ``km_to_m``,
``parse_cr_datetime``) plus a small dotted-path getter used by the generic
HTTP+JSON adapter (``http_json.py``) to pull values out of arbitrary JSON
records.

This module imports nothing beyond the stdlib, so it is safe to unit test
in isolation and safe to import from anywhere without pulling in Django,
requests, or paho-mqtt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Costa_Rica"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def kmh_to_ms(speed_kmh: float) -> float:
    """Kilometres per hour -> metres per second."""
    return speed_kmh / 3.6


def km_to_m(odometer_km: float) -> float:
    """Kilometres -> metres."""
    return odometer_km * 1000.0


def parse_cr_datetime(
    value: str,
    fmt: str = DEFAULT_DATETIME_FORMAT,
    tz: str = DEFAULT_TZ,
) -> int:
    """Parse a naive local datetime string to Unix epoch seconds.

    Defaults match NavSat's naive ``America/Costa_Rica`` (UTC-6, no DST)
    timestamps, but ``fmt``/``tz`` are overridable so the same helper can
    serve any HTTP source whose mapping config specifies its own timestamp
    shape. Raises ``ValueError`` on malformed or empty input.
    """
    naive = datetime.strptime(value, fmt)
    aware = naive.replace(tzinfo=ZoneInfo(tz))
    return int(aware.timestamp())


def get_by_path(data: dict, path: str) -> Any:
    """Dotted-path getter over nested dicts, tolerant of missing keys.

    ``get_by_path({"a": {"b": 1}}, "a.b")`` -> ``1``.
    Any missing key, non-dict intermediate value, or empty path yields
    ``None`` instead of raising.
    """
    if not path:
        return None
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current
