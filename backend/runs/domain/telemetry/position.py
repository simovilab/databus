"""GTFS-RT Position entity contract.

Covers the ``vehicle:<vehicle_id>:position`` Redis hash.

Producer: edge / MQTT (``realtime_engine/mqtt.py``).
Consumer: ``schedule_engine/tasks.py::build_vehicle_positions``.

Field types
-----------
- ``latitude``   : float  (required)
- ``longitude``  : float  (required)
- ``bearing``    : float? (optional)
- ``speed``      : float? (optional)
- ``odometer``   : float? (optional)
- ``timestamp``  : int?   (optional) — Unix epoch seconds.

Note on ``timestamp``: it lives in this hash because that is where the edge
writes it, but in GTFS-RT the value is the top-level ``VehiclePosition.timestamp``
(the ``Position`` sub-message has no timestamp field). The builder is responsible
for lifting it out of the position dict; this contract does not lift it.

This module imports nothing so it is safe to import from any layer without
pulling in Django or Redis.
"""

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

LATITUDE = "latitude"
LONGITUDE = "longitude"
BEARING = "bearing"
SPEED = "speed"
ODOMETER = "odometer"
TIMESTAMP = "timestamp"

_REQUIRED_FIELDS = (LATITUDE, LONGITUDE)
_OPTIONAL_FLOAT_FIELDS = (BEARING, SPEED, ODOMETER)
_OPTIONAL_INT_FIELDS = (TIMESTAMP,)


# ---------------------------------------------------------------------------
# Reader: str → typed (tolerant)
# ---------------------------------------------------------------------------


def from_redis(hash: dict) -> dict:
    """Convert a raw Redis position hash (all values are strings) to typed Python.

    Tolerant: absent keys are omitted from the result; values that fail
    coercion for optional fields are silently dropped (callers should handle
    missing keys with ``.get()``).

    Required fields (``latitude``, ``longitude``) that are present but
    non-coercible raise ``ValueError`` — the hash is corrupt.
    """
    result: dict = {}

    for field in _REQUIRED_FIELDS:
        raw = hash.get(field)
        if raw is not None:
            try:
                result[field] = float(raw)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"position.from_redis: required field '{field}' is not a "
                    f"valid float: {raw!r}"
                ) from exc

    for field in _OPTIONAL_FLOAT_FIELDS:
        raw = hash.get(field)
        if raw is not None and raw != "":
            try:
                result[field] = float(raw)
            except (ValueError, TypeError):
                pass  # tolerant: drop bad optional values

    for field in _OPTIONAL_INT_FIELDS:
        raw = hash.get(field)
        if raw is not None and raw != "":
            try:
                result[field] = int(raw)
            except (ValueError, TypeError):
                pass  # tolerant: drop bad optional values

    return result


# ---------------------------------------------------------------------------
# Writer: typed → str (strict)
# ---------------------------------------------------------------------------


def validate_for_write(payload: dict) -> dict[str, str]:
    """Validate a position payload and return a Redis-ready ``{field: str}`` mapping.

    Strict: raises ``ValueError`` if a required field is missing or
    non-coercible. Optional fields that are absent are simply omitted from
    the output mapping; those that fail coercion also raise ``ValueError``
    (the caller is responsible for sending clean data).
    """
    result: dict[str, str] = {}

    # Required fields
    for field in _REQUIRED_FIELDS:
        value = payload.get(field)
        if value is None:
            raise ValueError(
                f"position.validate_for_write: required field '{field}' is missing"
            )
        try:
            result[field] = str(float(value))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"position.validate_for_write: required field '{field}' cannot be "
                f"coerced to float: {value!r}"
            ) from exc

    # Optional float fields
    for field in _OPTIONAL_FLOAT_FIELDS:
        value = payload.get(field)
        if value is not None:
            try:
                result[field] = str(float(value))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"position.validate_for_write: optional field '{field}' cannot "
                    f"be coerced to float: {value!r}"
                ) from exc

    # Optional int fields
    for field in _OPTIONAL_INT_FIELDS:
        value = payload.get(field)
        if value is not None:
            try:
                result[field] = str(int(value))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"position.validate_for_write: optional field '{field}' cannot "
                    f"be coerced to int: {value!r}"
                ) from exc

    return result
