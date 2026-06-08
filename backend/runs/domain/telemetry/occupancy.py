"""GTFS-RT OccupancyStatus entity contract.

Covers the ``vehicle:<vehicle_id>:occupancy`` Redis hash.

Producer: edge / MQTT (``realtime_engine/mqtt.py``), with the enum value
bucketed at ingestion time using :func:`classify_status` (server policy).
Consumer: ``schedule_engine/tasks.py::build_vehicle_positions``.

Field types
-----------
- ``occupancy_percentage`` : int?        (optional)
- ``occupancy_count``      : int?        (optional)
- ``occupancy_status``     : str (enum)  (required)

Enum values match ``runs/models.py::OccupancyStatus.occupancy_status`` choices:
    EMPTY, MANY_SEATS_AVAILABLE, FEW_SEATS_AVAILABLE, STANDING_ROOM_ONLY,
    CRUSHED_STANDING_ROOM_ONLY, FULL, NOT_ACCEPTING_PASSENGERS,
    NO_DATA_AVAILABLE, NOT_BOARDABLE

Occupancy bucketing policy (:func:`classify_status`)
-----------------------------------------------------
The ``occupancy_status`` enum value is a *server-side policy* decision, not a
raw sensor reading. The thresholds below are adopted from the simulator's
``kinematics.occupancy_status`` as the agreed starting point:

    percentage < 20   → MANY_SEATS_AVAILABLE
    percentage < 50   → FEW_SEATS_AVAILABLE
    percentage < 80   → STANDING_ROOM_ONLY
    percentage >= 80  → FULL
    percentage is None → NO_DATA_AVAILABLE

These bands cover only 4 of the 9 GTFS enum values. The remaining 5
(EMPTY, CRUSHED_STANDING_ROOM_ONLY, NOT_ACCEPTING_PASSENGERS, NOT_BOARDABLE,
and the boundary between FULL and NOT_ACCEPTING_PASSENGERS) require product
input before they can be assigned threshold ranges.

This module imports nothing so it is safe to import from any layer without
pulling in Django or Redis.
"""

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

OCCUPANCY_PERCENTAGE = "occupancy_percentage"
OCCUPANCY_COUNT = "occupancy_count"
OCCUPANCY_STATUS = "occupancy_status"

# ---------------------------------------------------------------------------
# Enum value set (must match runs/models.py OccupancyStatus.occupancy_status)
# ---------------------------------------------------------------------------

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "EMPTY",
        "MANY_SEATS_AVAILABLE",
        "FEW_SEATS_AVAILABLE",
        "STANDING_ROOM_ONLY",
        "CRUSHED_STANDING_ROOM_ONLY",
        "FULL",
        "NOT_ACCEPTING_PASSENGERS",
        "NO_DATA_AVAILABLE",
        "NOT_BOARDABLE",
    }
)

_OPTIONAL_INT_FIELDS = (OCCUPANCY_PERCENTAGE, OCCUPANCY_COUNT)


# ---------------------------------------------------------------------------
# Bucketing policy
# ---------------------------------------------------------------------------


def classify_status(percentage: int | None) -> str:
    """Map a raw occupancy percentage to the GTFS OccupancyStatus enum value.

    This is the centralised bucketing policy. Thresholds are adopted from
    the simulator's ``kinematics.occupancy_status``:

    - ``None``   → ``NO_DATA_AVAILABLE``
    - ``< 20``   → ``MANY_SEATS_AVAILABLE``
    - ``< 50``   → ``FEW_SEATS_AVAILABLE``
    - ``< 80``   → ``STANDING_ROOM_ONLY``
    - ``>= 80``  → ``FULL``

    Note: Only 4 of the 9 GTFS enum values are covered. The remaining values
    (EMPTY, CRUSHED_STANDING_ROOM_ONLY, NOT_ACCEPTING_PASSENGERS, NOT_BOARDABLE)
    require product input before threshold ranges can be assigned.
    """
    if percentage is None:
        return "NO_DATA_AVAILABLE"
    if percentage < 20:
        return "MANY_SEATS_AVAILABLE"
    if percentage < 50:
        return "FEW_SEATS_AVAILABLE"
    if percentage < 80:
        return "STANDING_ROOM_ONLY"
    return "FULL"


# ---------------------------------------------------------------------------
# Reader: str → typed (tolerant)
# ---------------------------------------------------------------------------


def from_redis(hash: dict) -> dict:
    """Convert a raw Redis occupancy hash (all values are strings) to typed Python.

    Tolerant: absent keys are omitted; values that fail coercion for optional
    fields are silently dropped. The ``occupancy_status`` field is passed
    through as-is if present; invalid values are dropped (tolerant read).
    """
    result: dict = {}

    for field in _OPTIONAL_INT_FIELDS:
        raw = hash.get(field)
        if raw is not None and raw != "":
            try:
                result[field] = int(raw)
            except (ValueError, TypeError):
                pass  # tolerant: drop bad optional values

    raw_status = hash.get(OCCUPANCY_STATUS)
    if raw_status is not None and raw_status != "":
        # Tolerant on read: accept any value present in Redis
        result[OCCUPANCY_STATUS] = raw_status

    return result


# ---------------------------------------------------------------------------
# Writer: typed → str (strict)
# ---------------------------------------------------------------------------


def validate_for_write(payload: dict) -> dict[str, str]:
    """Validate an occupancy payload and return a Redis-ready ``{field: str}`` mapping.

    Strict:
    - ``occupancy_status`` must be a valid enum value; raises ``ValueError``
      on mismatch.
    - Optional int fields raise ``ValueError`` if present but non-coercible.
    - ``occupancy_status`` is required; raises ``ValueError`` if missing.
    """
    result: dict[str, str] = {}

    # Optional int fields
    for field in _OPTIONAL_INT_FIELDS:
        value = payload.get(field)
        if value is not None:
            try:
                result[field] = str(int(value))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"occupancy.validate_for_write: optional field '{field}' cannot "
                    f"be coerced to int: {value!r}"
                ) from exc

    # Required enum field
    status = payload.get(OCCUPANCY_STATUS)
    if status is None:
        raise ValueError(
            f"occupancy.validate_for_write: required field '{OCCUPANCY_STATUS}' is missing"
        )
    if status not in VALID_STATUSES:
        raise ValueError(
            f"occupancy.validate_for_write: '{status}' is not a valid "
            f"occupancy_status; expected one of {sorted(VALID_STATUSES)}"
        )
    result[OCCUPANCY_STATUS] = status

    return result
