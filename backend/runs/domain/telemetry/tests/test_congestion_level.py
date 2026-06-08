"""Pure unit tests for the congestion_level entity contract (stub).

No Django, no Redis — runnable under plain pytest.
"""

import pytest

from runs.domain.telemetry import congestion_level
from runs.domain.telemetry.congestion_level import VALID_LEVELS


# ---------------------------------------------------------------------------
# valid_levels matches models.py exactly
# ---------------------------------------------------------------------------


def test_valid_levels_contains_all_five_gtfs_values():
    expected = {
        "UNKNOWN_CONGESTION_LEVEL",
        "RUNNING_SMOOTHLY",
        "STOP_AND_GO",
        "CONGESTION",
        "SEVERE_CONGESTION",
    }
    assert VALID_LEVELS == expected


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_congestion():
    payload = {"congestion_level": "CONGESTION"}
    redis_map = congestion_level.validate_for_write(payload)
    result = congestion_level.from_redis(redis_map)
    assert result["congestion_level"] == "CONGESTION"


def test_round_trip_all_valid_levels():
    for level in VALID_LEVELS:
        redis_map = congestion_level.validate_for_write({"congestion_level": level})
        result = congestion_level.from_redis(redis_map)
        assert result["congestion_level"] == level


# ---------------------------------------------------------------------------
# from_redis — tolerant behaviour
# ---------------------------------------------------------------------------


def test_from_redis_empty_hash_returns_empty_dict():
    result = congestion_level.from_redis({})
    assert result == {}


def test_from_redis_omits_empty_string_value():
    hash_ = {"congestion_level": ""}
    result = congestion_level.from_redis(hash_)
    assert "congestion_level" not in result


def test_from_redis_tolerant_on_invalid_value():
    # Reads are tolerant — pass through unknown values
    hash_ = {"congestion_level": "INVENTED_LEVEL"}
    result = congestion_level.from_redis(hash_)
    assert result["congestion_level"] == "INVENTED_LEVEL"


# ---------------------------------------------------------------------------
# validate_for_write — strict validation
# ---------------------------------------------------------------------------


def test_validate_for_write_raises_on_missing_level():
    with pytest.raises(ValueError, match="congestion_level"):
        congestion_level.validate_for_write({})


def test_validate_for_write_raises_on_invalid_enum():
    with pytest.raises(ValueError, match="INVENTED_LEVEL"):
        congestion_level.validate_for_write({"congestion_level": "INVENTED_LEVEL"})


def test_validate_for_write_output_all_strings():
    result = congestion_level.validate_for_write({"congestion_level": "STOP_AND_GO"})
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"
