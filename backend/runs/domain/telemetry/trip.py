"""GTFS-RT TripDescriptor entity contract.

Covers the ``run:<run_id>:trip`` Redis hash.

Producer: server lifecycle action (``runs/domain/lifecycle/actions.py``).
Consumer: ``schedule_engine/tasks.py::build_vehicle_positions`` and
``build_trip_updates``.

This hash is the GTFS-RT-shaped *projection* of the TripDescriptor subset from
the flat ``run:<run_id>`` hash. It contains only what the feed builder needs
for the ``trip`` field; the full run record (assignment state, lifecycle, …)
remains in ``run:<run_id>``.

Field types
-----------
- ``trip_id``               : str  (required)
- ``route_id``              : str  (required)
- ``direction_id``          : int? (optional)
- ``schedule_relationship`` : str? (optional)
- ``start_time``            : str? (optional — HH:MM:SS)
- ``start_date``            : str? (optional — YYYYMMDD)

Note: ``vehicle_id`` and all lifecycle / non-trip fields present in
``run:<run_id>`` are *not* part of this contract.

This module imports nothing so it is safe to import from any layer without
pulling in Django or Redis.
"""

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

TRIP_ID = "trip_id"
ROUTE_ID = "route_id"
DIRECTION_ID = "direction_id"
SCHEDULE_RELATIONSHIP = "schedule_relationship"
START_TIME = "start_time"
START_DATE = "start_date"

_REQUIRED_FIELDS = (TRIP_ID, ROUTE_ID)
_OPTIONAL_STR_FIELDS = (SCHEDULE_RELATIONSHIP, START_TIME, START_DATE)

# The complete set of fields that belong to the TripDescriptor contract.
TRIP_FIELDS: frozenset[str] = frozenset(
    {
        TRIP_ID,
        ROUTE_ID,
        DIRECTION_ID,
        SCHEDULE_RELATIONSHIP,
        START_TIME,
        START_DATE,
    }
)


# ---------------------------------------------------------------------------
# Reader: str → typed (tolerant)
# ---------------------------------------------------------------------------


def from_redis(hash: dict) -> dict:
    """Convert a raw Redis trip hash (all values are strings) to typed Python.

    Tolerant: absent keys are omitted; values that fail coercion for optional
    fields are silently dropped. Required fields that are present but
    non-coercible raise ``ValueError``.

    Most fields are already strings; only ``direction_id`` is coerced to int.
    """
    result: dict = {}

    for field in _REQUIRED_FIELDS:
        raw = hash.get(field)
        if raw is not None and raw != "":
            result[field] = raw  # already a str

    # direction_id: optional int
    raw_dir = hash.get(DIRECTION_ID)
    if raw_dir is not None and raw_dir != "":
        try:
            result[DIRECTION_ID] = int(raw_dir)
        except (ValueError, TypeError):
            pass  # tolerant: drop bad optional values

    for field in _OPTIONAL_STR_FIELDS:
        raw = hash.get(field)
        if raw is not None and raw != "":
            result[field] = raw

    return result


# ---------------------------------------------------------------------------
# Writer: typed → str (strict)
# ---------------------------------------------------------------------------


def validate_for_write(payload: dict) -> dict[str, str]:
    """Validate a trip payload and return a Redis-ready ``{field: str}`` mapping.

    Strict:
    - ``trip_id`` and ``route_id`` are required; raises ``ValueError`` if missing
      or empty.
    - ``direction_id``, if present, must be coercible to int.
    - Other optional fields are written as-is if present.
    """
    result: dict[str, str] = {}

    # Required fields
    for field in _REQUIRED_FIELDS:
        value = payload.get(field)
        if not value:
            raise ValueError(
                f"trip.validate_for_write: required field '{field}' is missing or empty"
            )
        result[field] = str(value)

    # direction_id: optional int
    dir_id = payload.get(DIRECTION_ID)
    if dir_id is not None:
        try:
            result[DIRECTION_ID] = str(int(dir_id))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"trip.validate_for_write: optional field '{DIRECTION_ID}' cannot "
                f"be coerced to int: {dir_id!r}"
            ) from exc

    # Optional string fields
    for field in _OPTIONAL_STR_FIELDS:
        value = payload.get(field)
        if value is not None:
            result[field] = str(value)

    return result


# ---------------------------------------------------------------------------
# Projection helper
# ---------------------------------------------------------------------------


def project_from_run_hash(run_hash: dict) -> dict:
    """Extract and return the TripDescriptor subset from a flat run hash.

    The flat ``run:<run_id>`` hash contains all run assignment and lifecycle
    fields. This helper picks only the fields that belong to the
    TripDescriptor contract and returns a write-ready typed dict (values are
    still the raw strings from Redis, as ``from_redis`` will further type-coerce
    them on read).

    Used by the lifecycle action to produce the ``run:<run_id>:trip`` hash in
    one call:

        mapping = project_from_run_hash(run_hash)
        redis.hset(trip_key(run_id), mapping=mapping)

    Run-only fields (``run_id``, ``shape_id``, ``vehicle``, ``operator``,
    ``run_lifecycle_state``, …) are silently dropped.
    """
    subset: dict[str, str] = {}

    for field in TRIP_FIELDS:
        value = run_hash.get(field)
        if value is not None and value != "":
            subset[field] = str(value)

    return subset
