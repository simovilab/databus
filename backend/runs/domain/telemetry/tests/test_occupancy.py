"""Pure unit tests for the occupancy entity contract and classify_status.

No Django, no Redis — runnable under plain pytest.
"""

import pytest

from runs.domain.telemetry import occupancy
from runs.domain.telemetry.occupancy import classify_status, VALID_STATUSES


# ---------------------------------------------------------------------------
# classify_status — threshold boundary tests
# ---------------------------------------------------------------------------


def test_classify_status_none_returns_no_data():
    assert classify_status(None) == "NO_DATA_AVAILABLE"


def test_classify_status_zero():
    assert classify_status(0) == "MANY_SEATS_AVAILABLE"


def test_classify_status_19_boundary():
    assert classify_status(19) == "MANY_SEATS_AVAILABLE"


def test_classify_status_20_boundary():
    assert classify_status(20) == "FEW_SEATS_AVAILABLE"


def test_classify_status_49_boundary():
    assert classify_status(49) == "FEW_SEATS_AVAILABLE"


def test_classify_status_50_boundary():
    assert classify_status(50) == "STANDING_ROOM_ONLY"


def test_classify_status_79_boundary():
    assert classify_status(79) == "STANDING_ROOM_ONLY"


def test_classify_status_80_boundary():
    assert classify_status(80) == "FULL"


def test_classify_status_100():
    assert classify_status(100) == "FULL"


def test_classify_status_above_100():
    # Edge: values above 100 are still mapped to FULL (no upper clamp)
    assert classify_status(150) == "FULL"


def test_classify_status_mid_range():
    assert classify_status(35) == "FEW_SEATS_AVAILABLE"
    assert classify_status(65) == "STANDING_ROOM_ONLY"


# ---------------------------------------------------------------------------
# valid_statuses matches models.py exactly
# ---------------------------------------------------------------------------


def test_valid_statuses_contains_all_nine_gtfs_values():
    expected = {
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
    assert VALID_STATUSES == expected


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_with_status_only():
    payload = {"occupancy_status": "FULL"}
    redis_map = occupancy.validate_for_write(payload)
    result = occupancy.from_redis(redis_map)
    assert result["occupancy_status"] == "FULL"
    assert "occupancy_percentage" not in result
    assert "occupancy_count" not in result


def test_round_trip_all_fields():
    payload = {
        "occupancy_status": "STANDING_ROOM_ONLY",
        "occupancy_percentage": 65,
        "occupancy_count": 42,
    }
    redis_map = occupancy.validate_for_write(payload)
    result = occupancy.from_redis(redis_map)
    assert result["occupancy_status"] == "STANDING_ROOM_ONLY"
    assert result["occupancy_percentage"] == 65
    assert result["occupancy_count"] == 42


# ---------------------------------------------------------------------------
# Coercion edge cases (from_redis)
# ---------------------------------------------------------------------------


def test_from_redis_coerces_string_ints():
    hash_ = {
        "occupancy_status": "FEW_SEATS_AVAILABLE",
        "occupancy_percentage": "30",
        "occupancy_count": "20",
    }
    result = occupancy.from_redis(hash_)
    assert result["occupancy_percentage"] == 30
    assert result["occupancy_count"] == 20
    assert isinstance(result["occupancy_percentage"], int)


def test_from_redis_omits_missing_optional_fields():
    hash_ = {"occupancy_status": "EMPTY"}
    result = occupancy.from_redis(hash_)
    assert "occupancy_percentage" not in result
    assert "occupancy_count" not in result


def test_from_redis_drops_bad_optional_int_silently():
    hash_ = {
        "occupancy_status": "FULL",
        "occupancy_percentage": "not-a-number",
    }
    result = occupancy.from_redis(hash_)
    assert "occupancy_percentage" not in result


def test_from_redis_drops_empty_string_optional_fields():
    hash_ = {
        "occupancy_status": "FULL",
        "occupancy_percentage": "",
        "occupancy_count": "",
    }
    result = occupancy.from_redis(hash_)
    assert "occupancy_percentage" not in result
    assert "occupancy_count" not in result


def test_from_redis_tolerant_on_invalid_status():
    # Reads are tolerant — pass through unknown values rather than raising
    hash_ = {"occupancy_status": "INVENTED_VALUE"}
    result = occupancy.from_redis(hash_)
    assert result["occupancy_status"] == "INVENTED_VALUE"


# ---------------------------------------------------------------------------
# validate_for_write — strict validation
# ---------------------------------------------------------------------------


def test_validate_for_write_raises_on_missing_status():
    with pytest.raises(ValueError, match="occupancy_status"):
        occupancy.validate_for_write({"occupancy_percentage": 50})


def test_validate_for_write_raises_on_invalid_enum():
    with pytest.raises(ValueError, match="INVENTED_STATUS"):
        occupancy.validate_for_write({"occupancy_status": "INVENTED_STATUS"})


def test_validate_for_write_raises_on_bad_optional_int():
    with pytest.raises(ValueError, match="occupancy_percentage"):
        occupancy.validate_for_write(
            {"occupancy_status": "FULL", "occupancy_percentage": "bad"}
        )


def test_validate_for_write_output_all_strings():
    payload = {
        "occupancy_status": "MANY_SEATS_AVAILABLE",
        "occupancy_percentage": 10,
        "occupancy_count": 5,
    }
    result = occupancy.validate_for_write(payload)
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"


def test_validate_for_write_accepts_all_valid_enum_values():
    for status in VALID_STATUSES:
        result = occupancy.validate_for_write({"occupancy_status": status})
        assert result["occupancy_status"] == status
