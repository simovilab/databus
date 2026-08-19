"""Generic HTTP+JSON telemetry source adapter.

Registered under kind ``"http"``. Driven entirely by a Sensor's
``source_http_url`` and ``source_json_mapping`` fields — no per-provider
code is needed for JSON-over-HTTP feeds that fit the mapping schema below.

Mapping schema (NavSat is the first concrete instance)::

    {
      "type": "array",                 # or anything else for a single object
      "paths": {
        "vehicle_id": "plateNumber",
        "timestamp": "crDateTime",
        "lat": "latitude",
        "lon": "longitude",
        "speed": "speed",
        "odometer": "odometer"
      },
      "units": {"speed": "kmh", "odometer": "km"},
      "timestamp": {"format": "%Y-%m-%d %H:%M:%S", "tz": "America/Costa_Rica"}
    }

Only ``lat``/``lon`` are effectively required in ``paths`` — a record that
can't yield both is skipped. ``vehicle_id`` is resolved from the mapped
path when present; otherwise the adapter falls back to the sensor's own
equipment/vehicle association. Any malformed record is logged and skipped
rather than failing the whole batch.

Django models are never imported here; ``sensor`` is accessed structurally
(duck-typed) and only inside ``fetch``, so this module stays importable and
testable without Django configured.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from . import base
from .transforms import get_by_path, km_to_m, kmh_to_ms, parse_cr_datetime

if TYPE_CHECKING:
    # Type-checking only: the runtime import graph stays Django-free (see
    # module docstring), but the real model gives accurate hover/mypy types.
    from operations.models import Sensor

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 5


def _convert_unit(field: str, value: Any, units: dict) -> Any:
    """Convert `value` from the unit declared for `field` in `units` to SI, if known."""
    if value is None:
        return None
    unit = units.get(field)
    if unit == "kmh":
        return kmh_to_ms(float(value))
    if unit == "km":
        return km_to_m(float(value))
    return value


def _extract_record(record: dict, mapping: dict) -> dict | None:
    """Extract a position payload + vehicle_id (if mapped) from one record.

    Returns ``None`` when latitude/longitude can't be resolved — the caller
    treats that as "skip this record".
    """
    paths = mapping.get("paths", {})
    units = mapping.get("units", {})
    ts_cfg = mapping.get("timestamp", {})

    lat_path = paths.get("lat")
    lon_path = paths.get("lon")
    lat = get_by_path(record, lat_path) if lat_path else None
    lon = get_by_path(record, lon_path) if lon_path else None
    if lat is None or lon is None:
        return None

    payload: dict = {
        "latitude": float(lat),
        "longitude": float(lon),
    }

    speed_path = paths.get("speed")
    if speed_path:
        raw_speed = get_by_path(record, speed_path)
        converted = _convert_unit("speed", raw_speed, units)
        if converted is not None:
            payload["speed"] = converted

    odometer_path = paths.get("odometer")
    if odometer_path:
        raw_odometer = get_by_path(record, odometer_path)
        converted = _convert_unit("odometer", raw_odometer, units)
        if converted is not None:
            payload["odometer"] = converted

    bearing_path = paths.get("bearing")
    if bearing_path:
        raw_bearing = get_by_path(record, bearing_path)
        if raw_bearing is not None:
            payload["bearing"] = float(raw_bearing)

    timestamp_path = paths.get("timestamp")
    if timestamp_path:
        raw_ts = get_by_path(record, timestamp_path)
        if raw_ts is not None:
            fmt = ts_cfg.get("format", "%Y-%m-%d %H:%M:%S")
            tz = ts_cfg.get("tz", "America/Costa_Rica")
            try:
                payload["timestamp"] = parse_cr_datetime(str(raw_ts), fmt=fmt, tz=tz)
            except (ValueError, TypeError):
                logger.warning("Could not parse timestamp %r — omitting field", raw_ts)

    vehicle_id = None
    vehicle_id_path = paths.get("vehicle_id")
    if vehicle_id_path:
        raw_vehicle_id = get_by_path(record, vehicle_id_path)
        if raw_vehicle_id is not None:
            vehicle_id = str(raw_vehicle_id)

    return {"vehicle_id": vehicle_id, "payload": payload}


@base.register("http")
class HttpJsonSourceAdapter:
    """Fetches vehicle positions from a generic HTTP+JSON endpoint."""

    def fetch(self, sensor: "Sensor") -> list[tuple[str, dict]]:
        """Fetch and normalize position records from `sensor`'s HTTP+JSON endpoint."""
        url = sensor.source_http_url
        mapping = sensor.source_json_mapping or {}

        try:
            # source_http_url is a nullable DB field; a None here falls through
            # to the except below rather than being type-safe. See task report.
            response = requests.get(url, timeout=DEFAULT_TIMEOUT_S)  # type: ignore[arg-type]
            response.raise_for_status()
            body = response.json()
        except Exception:
            logger.exception("HTTP telemetry fetch failed for url=%s", url)
            return []

        records = body if mapping.get("type", "array") == "array" else [body]
        if not isinstance(records, list):
            logger.warning(
                "Expected a list of records for url=%s, got %s — skipping",
                url,
                type(records),
            )
            return []

        results: list[tuple[str, dict]] = []
        for record in records:
            try:
                if not isinstance(record, dict):
                    logger.warning("Skipping non-dict record: %r", record)
                    continue

                extracted = _extract_record(record, mapping)
                if extracted is None:
                    logger.warning(
                        "Skipping record missing latitude/longitude: %r", record
                    )
                    continue

                vehicle_id = extracted["vehicle_id"]
                if not vehicle_id:
                    # Lazy access — never imported/evaluated at module scope,
                    # so this stays safe for isolated (non-DB) test runs.
                    # equipment is nullable; a None here is caught by the
                    # except below rather than being type-safe. See task report.
                    vehicle_id = str(sensor.equipment.vehicle_id)  # type: ignore[union-attr]

                results.append((vehicle_id, extracted["payload"]))
            except Exception:
                logger.exception("Skipping malformed record: %r", record)
                continue

        return results
