"""Pure unit tests for the vehicle_stop_status entity contract.

No Django, no Redis — runnable under plain pytest.
"""

import pytest

from runs.domain.telemetry import vehicle_stop_status
from runs.domain.telemetry.vehicle_stop_status import VALID_STATUSES


# ---------------------------------------------------------------------------
# valid_statuses matches models.py exactly
# ---------------------------------------------------------------------------


def test_valid_statuses_contains_all_three_gtfs_values():
    expected = {"INCOMING_AT", "STOPPED_AT", "IN_TRANSIT_TO"}
    assert VALID_STATUSES == expected


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_status_only():
    payload = {"current_status": "IN_TRANSIT_TO"}
    redis_map = vehicle_stop_status.validate_for_write(payload)
    result = vehicle_stop_status.from_redis(redis_map)
    assert result["current_status"] == "IN_TRANSIT_TO"
    assert "current_stop_sequence" not in result
    assert "stop_id" not in result


def test_round_trip_all_fields():
    payload = {
        "current_status": "STOPPED_AT",
        "current_stop_sequence": 5,
        "stop_id": "stop_A",
    }
    redis_map = vehicle_stop_status.validate_for_write(payload)
    result = vehicle_stop_status.from_redis(redis_map)
    assert result["current_status"] == "STOPPED_AT"
    assert result["current_stop_sequence"] == 5
    assert result["stop_id"] == "stop_A"


def test_round_trip_incoming_at():
    payload = {
        "current_status": "INCOMING_AT",
        "current_stop_sequence": 3,
        "stop_id": "stop_B",
    }
    redis_map = vehicle_stop_status.validate_for_write(payload)
    result = vehicle_stop_status.from_redis(redis_map)
    assert result["current_status"] == "INCOMING_AT"
    assert result["current_stop_sequence"] == 3


# ---------------------------------------------------------------------------
# Coercion edge cases (from_redis)
# ---------------------------------------------------------------------------


def test_from_redis_coerces_string_int_sequence():
    hash_ = {"current_status": "STOPPED_AT", "current_stop_sequence": "7"}
    result = vehicle_stop_status.from_redis(hash_)
    assert result["current_stop_sequence"] == 7
    assert isinstance(result["current_stop_sequence"], int)


def test_from_redis_omits_missing_optional_fields():
    hash_ = {"current_status": "IN_TRANSIT_TO"}
    result = vehicle_stop_status.from_redis(hash_)
    assert "current_stop_sequence" not in result
    assert "stop_id" not in result


def test_from_redis_drops_bad_optional_int_silently():
    hash_ = {"current_status": "IN_TRANSIT_TO", "current_stop_sequence": "not-a-number"}
    result = vehicle_stop_status.from_redis(hash_)
    assert "current_stop_sequence" not in result


def test_from_redis_drops_empty_string_optional_fields():
    hash_ = {
        "current_status": "STOPPED_AT",
        "current_stop_sequence": "",
        "stop_id": "",
    }
    result = vehicle_stop_status.from_redis(hash_)
    assert "current_stop_sequence" not in result
    assert "stop_id" not in result


def test_from_redis_tolerant_on_invalid_status():
    # Reads are tolerant — pass through unknown values rather than raising
    hash_ = {"current_status": "INVENTED_STATUS"}
    result = vehicle_stop_status.from_redis(hash_)
    assert result["current_status"] == "INVENTED_STATUS"


# ---------------------------------------------------------------------------
# validate_for_write — strict validation
# ---------------------------------------------------------------------------


def test_validate_for_write_raises_on_missing_status():
    with pytest.raises(ValueError, match="current_status"):
        vehicle_stop_status.validate_for_write({"current_stop_sequence": 5})


def test_validate_for_write_raises_on_invalid_enum():
    with pytest.raises(ValueError, match="INVALID_STATUS"):
        vehicle_stop_status.validate_for_write({"current_status": "INVALID_STATUS"})


def test_validate_for_write_raises_on_bad_optional_int():
    with pytest.raises(ValueError, match="current_stop_sequence"):
        vehicle_stop_status.validate_for_write(
            {"current_status": "IN_TRANSIT_TO", "current_stop_sequence": "bad"}
        )


def test_validate_for_write_output_all_strings():
    payload = {
        "current_status": "IN_TRANSIT_TO",
        "current_stop_sequence": 3,
        "stop_id": "stop_C",
    }
    result = vehicle_stop_status.validate_for_write(payload)
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"


def test_validate_for_write_accepts_all_valid_enum_values():
    for status in VALID_STATUSES:
        result = vehicle_stop_status.validate_for_write({"current_status": status})
        assert result["current_status"] == status
