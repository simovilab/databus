"""GTFS-RT StopTimeUpdate projection contract.

Covers the ``run:<run_id>:stop_time_updates`` Redis **string** key, which holds a
JSON-encoded array — a materialized projection/cache written by the stop-times
producer with a staleness TTL.  It is NOT a typed entity-hash; the key stores a
single JSON string.

The GTFS-RT builder reads this key and treats a missing or empty value as "skip
stop_time_update" (honest empty list in the feed).

Per-entry contract
------------------
Each entry in the array has exactly these fields:

    {
        "stop_sequence": int,
        "stop_id": str,
        "arrival_time": int,   # POSIX seconds
        "departure_time": int, # POSIX seconds (== arrival_time for now)
        "uncertainty": int,
    }

Producer: ``runs/domain/progression/stop_times.py``.
Consumer: ``schedule_engine/builders.py::build_trip_update_entity``.

This module imports only stdlib ``json`` — no Django, no Redis — so it is safe
to import from any layer without pulling in Django or Redis.
"""

import json

# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------

STOP_SEQUENCE = "stop_sequence"
STOP_ID = "stop_id"
ARRIVAL_TIME = "arrival_time"
DEPARTURE_TIME = "departure_time"
UNCERTAINTY = "uncertainty"

_REQUIRED_FIELDS = (STOP_SEQUENCE, STOP_ID, ARRIVAL_TIME, DEPARTURE_TIME, UNCERTAINTY)


# ---------------------------------------------------------------------------
# Reader: str | None → list[dict]  (tolerant)
# ---------------------------------------------------------------------------


def from_redis(raw_json: str | None) -> list[dict]:
    """Decode a JSON string from Redis into a typed list of stop-time-update entries.

    Tolerant:
    - ``None``, empty string, or malformed JSON ⇒ return ``[]``.
    - A JSON value that is not a list ⇒ return ``[]``.
    - Entries missing any required field are silently dropped.
    - Entries with fields that cannot be coerced to the required type are silently
      dropped.

    Parameters
    ----------
    raw_json:
        The raw string value returned by ``r.get(stop_time_updates_key(run_id))``.

    Returns
    -------
    list[dict]
        A list of typed dicts, each guaranteed to have all five required fields
        with the correct Python types.
    """
    if not raw_json:
        return []

    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(parsed, list):
        return []

    result: list[dict] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        typed = _coerce_entry(entry)
        if typed is not None:
            result.append(typed)
    return result


def _coerce_entry(entry: dict) -> dict | None:
    """Attempt to coerce a single raw dict to the typed contract.

    Returns ``None`` if any required field is missing or cannot be coerced.
    """
    # stop_id: required str
    raw_stop_id = entry.get(STOP_ID)
    if raw_stop_id is None:
        return None
    stop_id = str(raw_stop_id)
    if not stop_id:
        return None

    # Integer fields: stop_sequence, arrival_time, departure_time, uncertainty
    int_fields = (STOP_SEQUENCE, ARRIVAL_TIME, DEPARTURE_TIME, UNCERTAINTY)
    coerced_ints: dict[str, int] = {}
    for field in int_fields:
        raw = entry.get(field)
        if raw is None:
            return None
        try:
            coerced_ints[field] = int(raw)
        except (ValueError, TypeError):
            return None

    return {
        STOP_SEQUENCE: coerced_ints[STOP_SEQUENCE],
        STOP_ID: stop_id,
        ARRIVAL_TIME: coerced_ints[ARRIVAL_TIME],
        DEPARTURE_TIME: coerced_ints[DEPARTURE_TIME],
        UNCERTAINTY: coerced_ints[UNCERTAINTY],
    }


# ---------------------------------------------------------------------------
# Writer: list[dict] → str  (strict)
# ---------------------------------------------------------------------------


def to_redis(entries: list[dict]) -> str:
    """Encode a list of stop-time-update entries to a JSON string for Redis.

    Strict: every entry must have all five required fields with values that are
    coercible to the correct types.  Raises ``ValueError`` on the first bad entry
    with a message identifying the problem.

    Parameters
    ----------
    entries:
        A list of dicts, each expected to contain the five required fields.

    Returns
    -------
    str
        A JSON-encoded string suitable for ``r.set(stop_time_updates_key(run_id), ...)``.

    Raises
    ------
    ValueError
        If any entry is missing a required field or contains a value with a bad type.
    """
    validated: list[dict] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"stop_time_updates.to_redis: entry[{idx}] is not a dict: {entry!r}"
            )

        # stop_id: required str (must be non-empty)
        raw_stop_id = entry.get(STOP_ID)
        if raw_stop_id is None:
            raise ValueError(
                f"stop_time_updates.to_redis: entry[{idx}] missing required field "
                f"'{STOP_ID}'"
            )
        stop_id = str(raw_stop_id)
        if not stop_id:
            raise ValueError(
                f"stop_time_updates.to_redis: entry[{idx}] field '{STOP_ID}' is empty"
            )

        # Integer fields: stop_sequence, arrival_time, departure_time, uncertainty
        int_fields = (STOP_SEQUENCE, ARRIVAL_TIME, DEPARTURE_TIME, UNCERTAINTY)
        coerced_ints: dict[str, int] = {}
        for field in int_fields:
            raw = entry.get(field)
            if raw is None:
                raise ValueError(
                    f"stop_time_updates.to_redis: entry[{idx}] missing required field "
                    f"'{field}'"
                )
            try:
                coerced_ints[field] = int(raw)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"stop_time_updates.to_redis: entry[{idx}] field '{field}' cannot "
                    f"be coerced to int: {raw!r}"
                ) from exc

        validated.append(
            {
                STOP_SEQUENCE: coerced_ints[STOP_SEQUENCE],
                STOP_ID: stop_id,
                ARRIVAL_TIME: coerced_ints[ARRIVAL_TIME],
                DEPARTURE_TIME: coerced_ints[DEPARTURE_TIME],
                UNCERTAINTY: coerced_ints[UNCERTAINTY],
            }
        )

    return json.dumps(validated)
