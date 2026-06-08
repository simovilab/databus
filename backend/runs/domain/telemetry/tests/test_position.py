"""Pure unit tests for the position entity contract.

No Django, no Redis — runnable under plain pytest.
"""

import pytest

from runs.domain.telemetry import position


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_required_fields_only():
    payload = {"latitude": 51.5074, "longitude": -0.1278}
    redis_map = position.validate_for_write(payload)
    result = position.from_redis(redis_map)
    assert result["latitude"] == pytest.approx(51.5074)
    assert result["longitude"] == pytest.approx(-0.1278)
    # Optional fields absent
    assert "bearing" not in result
    assert "speed" not in result
    assert "timestamp" not in result


def test_round_trip_all_fields():
    payload = {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "bearing": 270.5,
        "speed": 12.3,
        "odometer": 1234.56,
        "timestamp": 1700000000,
    }
    redis_map = position.validate_for_write(payload)
    result = position.from_redis(redis_map)
    assert result["latitude"] == pytest.approx(51.5074)
    assert result["longitude"] == pytest.approx(-0.1278)
    assert result["bearing"] == pytest.approx(270.5)
    assert result["speed"] == pytest.approx(12.3)
    assert result["odometer"] == pytest.approx(1234.56)
    assert result["timestamp"] == 1700000000


# ---------------------------------------------------------------------------
# Coercion edge cases (from_redis)
# ---------------------------------------------------------------------------


def test_from_redis_coerces_string_floats():
    hash_ = {"latitude": "51.5074", "longitude": "-0.1278", "speed": "12.3"}
    result = position.from_redis(hash_)
    assert result["latitude"] == pytest.approx(51.5074)
    assert result["speed"] == pytest.approx(12.3)


def test_from_redis_coerces_string_int_timestamp():
    hash_ = {"latitude": "0.0", "longitude": "0.0", "timestamp": "1700000000"}
    result = position.from_redis(hash_)
    assert result["timestamp"] == 1700000000
    assert isinstance(result["timestamp"], int)


def test_from_redis_omits_missing_optional_fields():
    hash_ = {"latitude": "1.0", "longitude": "2.0"}
    result = position.from_redis(hash_)
    assert "speed" not in result
    assert "bearing" not in result
    assert "odometer" not in result
    assert "timestamp" not in result


def test_from_redis_drops_bad_optional_float_silently():
    hash_ = {"latitude": "1.0", "longitude": "2.0", "speed": "not-a-float"}
    result = position.from_redis(hash_)
    assert "speed" not in result


def test_from_redis_drops_bad_optional_int_silently():
    hash_ = {"latitude": "1.0", "longitude": "2.0", "timestamp": "not-an-int"}
    result = position.from_redis(hash_)
    assert "timestamp" not in result


def test_from_redis_drops_empty_string_optional_fields():
    hash_ = {"latitude": "1.0", "longitude": "2.0", "bearing": ""}
    result = position.from_redis(hash_)
    assert "bearing" not in result


def test_from_redis_raises_on_bad_required_field():
    hash_ = {"latitude": "not-a-float", "longitude": "0.0"}
    with pytest.raises(ValueError, match="latitude"):
        position.from_redis(hash_)


# ---------------------------------------------------------------------------
# validate_for_write — strict validation
# ---------------------------------------------------------------------------


def test_validate_for_write_raises_on_missing_required_field():
    with pytest.raises(ValueError, match="latitude"):
        position.validate_for_write({"longitude": 0.0})


def test_validate_for_write_raises_on_bad_required_float():
    with pytest.raises(ValueError, match="longitude"):
        position.validate_for_write({"latitude": 1.0, "longitude": "bad"})


def test_validate_for_write_raises_on_bad_optional_float():
    with pytest.raises(ValueError, match="speed"):
        position.validate_for_write({"latitude": 1.0, "longitude": 2.0, "speed": "bad"})


def test_validate_for_write_raises_on_bad_optional_int():
    with pytest.raises(ValueError, match="timestamp"):
        position.validate_for_write(
            {"latitude": 1.0, "longitude": 2.0, "timestamp": "bad"}
        )


def test_validate_for_write_output_all_strings():
    payload = {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "bearing": 270.5,
        "speed": 12.3,
        "odometer": 1234.56,
        "timestamp": 1700000000,
    }
    result = position.validate_for_write(payload)
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"


def test_validate_for_write_accepts_integer_coords():
    # Integer lat/lon should be accepted (coerced to float)
    result = position.validate_for_write({"latitude": 51, "longitude": -1})
    assert result["latitude"] == "51.0"
    assert result["longitude"] == "-1.0"
