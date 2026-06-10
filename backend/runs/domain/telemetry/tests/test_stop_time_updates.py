"""Pure unit tests for the stop_time_updates entity contract.

No Django, no Redis — runnable under plain pytest.

Coverage target: ≥80% of runs/domain/telemetry/stop_time_updates.py.
"""

import json

import pytest

from runs.domain.telemetry import stop_time_updates
from runs.domain.telemetry.stop_time_updates import (
    ARRIVAL_TIME,
    DEPARTURE_TIME,
    STOP_ID,
    STOP_SEQUENCE,
    UNCERTAINTY,
    from_redis,
    to_redis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ENTRY = {
    STOP_SEQUENCE: 3,
    STOP_ID: "stop-99",
    ARRIVAL_TIME: 1700000000,
    DEPARTURE_TIME: 1700000000,
    UNCERTAINTY: 120,
}

_VALID_ENTRY_2 = {
    STOP_SEQUENCE: 4,
    STOP_ID: "stop-100",
    ARRIVAL_TIME: 1700000300,
    DEPARTURE_TIME: 1700000300,
    UNCERTAINTY: 60,
}


def _json(*entries) -> str:
    return json.dumps(list(entries))


# ---------------------------------------------------------------------------
# Field-name constants
# ---------------------------------------------------------------------------


def test_field_name_constants_are_correct_strings():
    assert stop_time_updates.STOP_SEQUENCE == "stop_sequence"
    assert stop_time_updates.STOP_ID == "stop_id"
    assert stop_time_updates.ARRIVAL_TIME == "arrival_time"
    assert stop_time_updates.DEPARTURE_TIME == "departure_time"
    assert stop_time_updates.UNCERTAINTY == "uncertainty"


# ---------------------------------------------------------------------------
# Round-trip: to_redis → from_redis
# ---------------------------------------------------------------------------


def test_round_trip_single_entry():
    entries = [_VALID_ENTRY]
    result = from_redis(to_redis(entries))
    assert len(result) == 1
    e = result[0]
    assert e[STOP_SEQUENCE] == 3
    assert e[STOP_ID] == "stop-99"
    assert e[ARRIVAL_TIME] == 1700000000
    assert e[DEPARTURE_TIME] == 1700000000
    assert e[UNCERTAINTY] == 120


def test_round_trip_multiple_entries():
    entries = [_VALID_ENTRY, _VALID_ENTRY_2]
    result = from_redis(to_redis(entries))
    assert len(result) == 2
    assert result[0][STOP_SEQUENCE] == 3
    assert result[1][STOP_SEQUENCE] == 4


def test_round_trip_empty_list():
    result = from_redis(to_redis([]))
    assert result == []


def test_round_trip_types_are_correct():
    result = from_redis(to_redis([_VALID_ENTRY]))
    e = result[0]
    assert isinstance(e[STOP_SEQUENCE], int)
    assert isinstance(e[STOP_ID], str)
    assert isinstance(e[ARRIVAL_TIME], int)
    assert isinstance(e[DEPARTURE_TIME], int)
    assert isinstance(e[UNCERTAINTY], int)


# ---------------------------------------------------------------------------
# from_redis — tolerant behaviour
# ---------------------------------------------------------------------------


def test_from_redis_none_returns_empty_list():
    assert from_redis(None) == []


def test_from_redis_empty_string_returns_empty_list():
    assert from_redis("") == []


def test_from_redis_malformed_json_returns_empty_list():
    assert from_redis("{not valid json") == []


def test_from_redis_json_object_not_list_returns_empty_list():
    # A JSON dict, not a list
    assert from_redis(json.dumps({"key": "value"})) == []


def test_from_redis_json_null_returns_empty_list():
    assert from_redis("null") == []


def test_from_redis_json_integer_not_list_returns_empty_list():
    assert from_redis("42") == []


def test_from_redis_json_string_not_list_returns_empty_list():
    assert from_redis('"hello"') == []


def test_from_redis_drops_entry_missing_stop_id():
    bad_entry = {
        STOP_SEQUENCE: 1,
        # STOP_ID missing
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_missing_stop_sequence():
    bad_entry = {
        # STOP_SEQUENCE missing
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_missing_arrival_time():
    bad_entry = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        # ARRIVAL_TIME missing
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_missing_departure_time():
    bad_entry = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        # DEPARTURE_TIME missing
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_missing_uncertainty():
    bad_entry = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        # UNCERTAINTY missing
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_with_non_int_stop_sequence():
    bad_entry = {
        STOP_SEQUENCE: "not-a-number",
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_drops_entry_with_non_int_arrival_time():
    bad_entry = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        ARRIVAL_TIME: "bad-time",
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    result = from_redis(_json(bad_entry))
    assert result == []


def test_from_redis_coerces_string_numerics():
    """Int fields given as numeric strings must be coerced successfully on read."""
    entry = {
        STOP_SEQUENCE: "5",
        STOP_ID: "stop-A",
        ARRIVAL_TIME: "1700000500",
        DEPARTURE_TIME: "1700000500",
        UNCERTAINTY: "90",
    }
    result = from_redis(_json(entry))
    assert len(result) == 1
    e = result[0]
    assert e[STOP_SEQUENCE] == 5
    assert isinstance(e[STOP_SEQUENCE], int)
    assert e[ARRIVAL_TIME] == 1700000500
    assert isinstance(e[ARRIVAL_TIME], int)
    assert e[UNCERTAINTY] == 90


def test_from_redis_keeps_valid_drops_invalid_entries():
    """Mixed list: valid entry is kept, invalid entry is dropped."""
    valid = dict(_VALID_ENTRY)
    bad = {STOP_ID: "stop-X"}  # missing most fields
    result = from_redis(_json(valid, bad))
    assert len(result) == 1
    assert result[0][STOP_ID] == "stop-99"


def test_from_redis_drops_non_dict_entries():
    """Non-dict items inside the list are silently skipped."""
    raw = json.dumps([_VALID_ENTRY, "not-a-dict", 42, None])
    result = from_redis(raw)
    assert len(result) == 1
    assert result[0][STOP_ID] == "stop-99"


# ---------------------------------------------------------------------------
# to_redis — strict validation
# ---------------------------------------------------------------------------


def test_to_redis_raises_on_missing_stop_id():
    bad = {
        STOP_SEQUENCE: 1,
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    with pytest.raises(ValueError, match=STOP_ID):
        to_redis([bad])


def test_to_redis_raises_on_missing_stop_sequence():
    bad = {
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    with pytest.raises(ValueError, match=STOP_SEQUENCE):
        to_redis([bad])


def test_to_redis_raises_on_missing_arrival_time():
    bad = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        DEPARTURE_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    with pytest.raises(ValueError, match=ARRIVAL_TIME):
        to_redis([bad])


def test_to_redis_raises_on_missing_departure_time():
    bad = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        UNCERTAINTY: 120,
    }
    with pytest.raises(ValueError, match=DEPARTURE_TIME):
        to_redis([bad])


def test_to_redis_raises_on_missing_uncertainty():
    bad = {
        STOP_SEQUENCE: 1,
        STOP_ID: "stop-1",
        ARRIVAL_TIME: 1700000000,
        DEPARTURE_TIME: 1700000000,
    }
    with pytest.raises(ValueError, match=UNCERTAINTY):
        to_redis([bad])


def test_to_redis_raises_on_bad_int_stop_sequence():
    bad = dict(_VALID_ENTRY)
    bad[STOP_SEQUENCE] = "not-an-int"
    with pytest.raises(ValueError, match=STOP_SEQUENCE):
        to_redis([bad])


def test_to_redis_raises_on_bad_int_arrival_time():
    bad = dict(_VALID_ENTRY)
    bad[ARRIVAL_TIME] = "bad-ts"
    with pytest.raises(ValueError, match=ARRIVAL_TIME):
        to_redis([bad])


def test_to_redis_raises_on_non_dict_entry():
    with pytest.raises(ValueError, match="not a dict"):
        to_redis(["not-a-dict"])


def test_to_redis_returns_json_string():
    result = to_redis([_VALID_ENTRY])
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert len(parsed) == 1


def test_to_redis_accepts_string_numerics():
    """String-numeric values must be accepted by to_redis (coerced to int)."""
    entry = {
        STOP_SEQUENCE: "7",
        STOP_ID: "stop-B",
        ARRIVAL_TIME: "1700001000",
        DEPARTURE_TIME: "1700001000",
        UNCERTAINTY: "60",
    }
    result = to_redis([entry])
    parsed = json.loads(result)
    assert parsed[0][STOP_SEQUENCE] == 7
    assert isinstance(parsed[0][STOP_SEQUENCE], int)


def test_to_redis_empty_stop_id_raises():
    bad = dict(_VALID_ENTRY)
    bad[STOP_ID] = ""
    with pytest.raises(ValueError, match=STOP_ID):
        to_redis([bad])
