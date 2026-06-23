"""GTFS-RT CongestionLevel entity contract — STUB.

Covers the ``run:<run_id>:congestion_level`` Redis hash.

Producer: server / external (deferred — no producer yet; key reserved).
Consumer: ``schedule_engine/tasks.py::build_vehicle_positions``.

A single bus's speed is a weak signal for congestion; an honest estimate needs
fleet aggregation or a traffic feed. The key is reserved and the contract is
defined here for consistency so builders can safely attempt a read without
knowing whether the hash exists.

Field types
-----------
- ``congestion_level`` : str (enum)  (required for write, absent in read is tolerated)

Enum values match ``runs/models.py::CongestionLevel.congestion_level`` choices:
    UNKNOWN_CONGESTION_LEVEL, RUNNING_SMOOTHLY, STOP_AND_GO,
    CONGESTION, SEVERE_CONGESTION

This module imports nothing so it is safe to import from any layer without
pulling in Django or Redis.
"""

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

CONGESTION_LEVEL = "congestion_level"

# ---------------------------------------------------------------------------
# Enum value set (must match runs/models.py CongestionLevel.congestion_level)
# ---------------------------------------------------------------------------

VALID_LEVELS: frozenset[str] = frozenset(
    {
        "UNKNOWN_CONGESTION_LEVEL",
        "RUNNING_SMOOTHLY",
        "STOP_AND_GO",
        "CONGESTION",
        "SEVERE_CONGESTION",
    }
)


# ---------------------------------------------------------------------------
# Reader: str → typed (tolerant)
# ---------------------------------------------------------------------------


def from_redis(hash: dict) -> dict:
    """Convert a raw Redis congestion_level hash (all strings) to typed Python.

    Tolerant: if the hash is empty or the field is absent, returns an empty
    dict (the hash may not be set yet — the producer is deferred).
    Invalid enum values are passed through as-is (tolerant read).
    """
    result: dict = {}

    raw = hash.get(CONGESTION_LEVEL)
    if raw is not None and raw != "":
        result[CONGESTION_LEVEL] = raw

    return result


# ---------------------------------------------------------------------------
# Writer: typed → str (strict)
# ---------------------------------------------------------------------------


def validate_for_write(payload: dict) -> dict[str, str]:
    """Validate a congestion_level payload and return a Redis-ready mapping.

    Strict:
    - ``congestion_level`` must be a valid enum value; raises ``ValueError``
      on mismatch.
    - ``congestion_level`` is required; raises ``ValueError`` if missing.
    """
    result: dict[str, str] = {}

    level = payload.get(CONGESTION_LEVEL)
    if level is None:
        raise ValueError(
            f"congestion_level.validate_for_write: required field "
            f"'{CONGESTION_LEVEL}' is missing"
        )
    if level not in VALID_LEVELS:
        raise ValueError(
            f"congestion_level.validate_for_write: '{level}' is not a valid "
            f"congestion_level; expected one of {sorted(VALID_LEVELS)}"
        )
    result[CONGESTION_LEVEL] = level

    return result
