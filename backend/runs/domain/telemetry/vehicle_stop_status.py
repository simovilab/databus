"""GTFS-RT VehicleStopStatus entity contract.

Covers the ``run:<run_id>:vehicle_stop_status`` Redis hash.

Producer: server progression step (``runs/domain/progression/compute.py``).
Consumer: ``schedule_engine/tasks.py::build_vehicle_positions``.

Field types
-----------
- ``current_stop_sequence`` : int?        (optional)
- ``stop_id``               : str?        (optional)
- ``current_status``        : str (enum)  (required)

Enum values match ``runs/models.py::VehicleStopStatus.current_status`` choices:
    INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO

This module imports nothing so it is safe to import from any layer without
pulling in Django or Redis.
"""

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

CURRENT_STOP_SEQUENCE = "current_stop_sequence"
STOP_ID = "stop_id"
CURRENT_STATUS = "current_status"

# ---------------------------------------------------------------------------
# Enum value set (must match runs/models.py VehicleStopStatus.current_status)
# ---------------------------------------------------------------------------

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "INCOMING_AT",
        "STOPPED_AT",
        "IN_TRANSIT_TO",
    }
)


# ---------------------------------------------------------------------------
# Reader: str → typed (tolerant)
# ---------------------------------------------------------------------------


def from_redis(hash: dict) -> dict:
    """Convert a raw Redis vehicle_stop_status hash (all strings) to typed Python.

    Tolerant: absent keys are omitted; values that fail coercion for optional
    fields are silently dropped. ``current_status`` is passed through as-is if
    present; invalid enum values are dropped (tolerant read).
    """
    result: dict = {}

    raw_seq = hash.get(CURRENT_STOP_SEQUENCE)
    if raw_seq is not None and raw_seq != "":
        try:
            result[CURRENT_STOP_SEQUENCE] = int(raw_seq)
        except (ValueError, TypeError):
            pass  # tolerant: drop bad optional values

    raw_stop_id = hash.get(STOP_ID)
    if raw_stop_id is not None and raw_stop_id != "":
        result[STOP_ID] = raw_stop_id

    raw_status = hash.get(CURRENT_STATUS)
    if raw_status is not None and raw_status != "":
        # Tolerant on read: accept any value present in Redis
        result[CURRENT_STATUS] = raw_status

    return result


# ---------------------------------------------------------------------------
# Writer: typed → str (strict)
# ---------------------------------------------------------------------------


def validate_for_write(payload: dict) -> dict[str, str]:
    """Validate a vehicle_stop_status payload and return a Redis-ready mapping.

    Strict:
    - ``current_status`` must be a valid enum value; raises ``ValueError``
      on mismatch.
    - ``current_stop_sequence``, if present, must be coercible to int.
    - ``current_status`` is required; raises ``ValueError`` if missing.
    """
    result: dict[str, str] = {}

    # Optional int field
    seq = payload.get(CURRENT_STOP_SEQUENCE)
    if seq is not None:
        try:
            result[CURRENT_STOP_SEQUENCE] = str(int(seq))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"vehicle_stop_status.validate_for_write: optional field "
                f"'{CURRENT_STOP_SEQUENCE}' cannot be coerced to int: {seq!r}"
            ) from exc

    # Optional str field
    stop_id = payload.get(STOP_ID)
    if stop_id is not None:
        result[STOP_ID] = str(stop_id)

    # Required enum field
    status = payload.get(CURRENT_STATUS)
    if status is None:
        raise ValueError(
            f"vehicle_stop_status.validate_for_write: required field "
            f"'{CURRENT_STATUS}' is missing"
        )
    if status not in VALID_STATUSES:
        raise ValueError(
            f"vehicle_stop_status.validate_for_write: '{status}' is not a valid "
            f"current_status; expected one of {sorted(VALID_STATUSES)}"
        )
    result[CURRENT_STATUS] = status

    return result
