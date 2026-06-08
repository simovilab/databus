"""Pure unit tests for the trip entity contract.

No Django, no Redis — runnable under plain pytest.
"""

import pytest

from runs.domain.telemetry import trip
from runs.domain.telemetry.trip import TRIP_FIELDS, project_from_run_hash


# ---------------------------------------------------------------------------
# TRIP_FIELDS constant
# ---------------------------------------------------------------------------


def test_trip_fields_contains_all_descriptor_fields():
    expected = {
        "trip_id",
        "route_id",
        "direction_id",
        "schedule_relationship",
        "start_time",
        "start_date",
    }
    assert TRIP_FIELDS == expected


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_required_fields_only():
    payload = {"trip_id": "trip_001", "route_id": "route_A"}
    redis_map = trip.validate_for_write(payload)
    result = trip.from_redis(redis_map)
    assert result["trip_id"] == "trip_001"
    assert result["route_id"] == "route_A"
    assert "direction_id" not in result
    assert "schedule_relationship" not in result


def test_round_trip_all_fields():
    payload = {
        "trip_id": "trip_001",
        "route_id": "route_A",
        "direction_id": 1,
        "schedule_relationship": "SCHEDULED",
        "start_time": "08:00:00",
        "start_date": "20260608",
    }
    redis_map = trip.validate_for_write(payload)
    result = trip.from_redis(redis_map)
    assert result["trip_id"] == "trip_001"
    assert result["route_id"] == "route_A"
    assert result["direction_id"] == 1
    assert isinstance(result["direction_id"], int)
    assert result["schedule_relationship"] == "SCHEDULED"
    assert result["start_time"] == "08:00:00"
    assert result["start_date"] == "20260608"


def test_round_trip_direction_id_zero():
    payload = {"trip_id": "t1", "route_id": "r1", "direction_id": 0}
    redis_map = trip.validate_for_write(payload)
    result = trip.from_redis(redis_map)
    assert result["direction_id"] == 0


# ---------------------------------------------------------------------------
# Coercion edge cases (from_redis)
# ---------------------------------------------------------------------------


def test_from_redis_coerces_string_direction_id():
    hash_ = {"trip_id": "t1", "route_id": "r1", "direction_id": "1"}
    result = trip.from_redis(hash_)
    assert result["direction_id"] == 1
    assert isinstance(result["direction_id"], int)


def test_from_redis_omits_missing_optional_fields():
    hash_ = {"trip_id": "t1", "route_id": "r1"}
    result = trip.from_redis(hash_)
    assert "direction_id" not in result
    assert "schedule_relationship" not in result
    assert "start_time" not in result
    assert "start_date" not in result


def test_from_redis_drops_bad_optional_direction_id_silently():
    hash_ = {"trip_id": "t1", "route_id": "r1", "direction_id": "bad"}
    result = trip.from_redis(hash_)
    assert "direction_id" not in result


def test_from_redis_drops_empty_string_optional_fields():
    hash_ = {
        "trip_id": "t1",
        "route_id": "r1",
        "direction_id": "",
        "schedule_relationship": "",
        "start_time": "",
        "start_date": "",
    }
    result = trip.from_redis(hash_)
    assert "direction_id" not in result
    assert "schedule_relationship" not in result


# ---------------------------------------------------------------------------
# validate_for_write — strict validation
# ---------------------------------------------------------------------------


def test_validate_for_write_raises_on_missing_trip_id():
    with pytest.raises(ValueError, match="trip_id"):
        trip.validate_for_write({"route_id": "r1"})


def test_validate_for_write_raises_on_missing_route_id():
    with pytest.raises(ValueError, match="route_id"):
        trip.validate_for_write({"trip_id": "t1"})


def test_validate_for_write_raises_on_empty_trip_id():
    with pytest.raises(ValueError, match="trip_id"):
        trip.validate_for_write({"trip_id": "", "route_id": "r1"})


def test_validate_for_write_raises_on_bad_direction_id():
    with pytest.raises(ValueError, match="direction_id"):
        trip.validate_for_write(
            {"trip_id": "t1", "route_id": "r1", "direction_id": "bad"}
        )


def test_validate_for_write_output_all_strings():
    payload = {
        "trip_id": "t1",
        "route_id": "r1",
        "direction_id": 0,
        "schedule_relationship": "SCHEDULED",
        "start_time": "09:00:00",
        "start_date": "20260608",
    }
    result = trip.validate_for_write(payload)
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"


# ---------------------------------------------------------------------------
# project_from_run_hash
# ---------------------------------------------------------------------------


def test_project_from_run_hash_extracts_trip_subset():
    run_hash = {
        # TripDescriptor fields
        "trip_id": "trip_001",
        "route_id": "route_A",
        "direction_id": "1",
        "schedule_relationship": "SCHEDULED",
        "start_time": "08:00:00",
        "start_date": "20260608",
        # Run-only fields that must be excluded
        "run_id": "some-uuid",
        "shape_id": "shape_x",
        "vehicle": "vehicle-uuid",
        "operator": "operator-uuid",
        "run_lifecycle_state": "IN_PROGRESS",
    }
    result = project_from_run_hash(run_hash)

    # Trip fields included
    assert result["trip_id"] == "trip_001"
    assert result["route_id"] == "route_A"
    assert result["direction_id"] == "1"
    assert result["schedule_relationship"] == "SCHEDULED"
    assert result["start_time"] == "08:00:00"
    assert result["start_date"] == "20260608"

    # Run-only fields excluded
    assert "run_id" not in result
    assert "shape_id" not in result
    assert "vehicle" not in result
    assert "operator" not in result
    assert "run_lifecycle_state" not in result


def test_project_from_run_hash_drops_empty_values():
    run_hash = {
        "trip_id": "trip_001",
        "route_id": "route_A",
        "direction_id": "",       # empty — should be dropped
        "schedule_relationship": "",  # empty — should be dropped
        "run_lifecycle_state": "IN_PROGRESS",
    }
    result = project_from_run_hash(run_hash)
    assert "direction_id" not in result
    assert "schedule_relationship" not in result
    assert result["trip_id"] == "trip_001"


def test_project_from_run_hash_partial_trip_fields():
    """When the run hash has only required fields, optional trip fields are absent."""
    run_hash = {
        "trip_id": "t2",
        "route_id": "r2",
        "vehicle": "v1",
        "run_lifecycle_state": "REQUESTED",
    }
    result = project_from_run_hash(run_hash)
    assert set(result.keys()) == {"trip_id", "route_id"}


def test_project_from_run_hash_output_all_strings():
    run_hash = {
        "trip_id": "t1",
        "route_id": "r1",
        "direction_id": "0",
        "vehicle": "v1",
    }
    result = project_from_run_hash(run_hash)
    for k, v in result.items():
        assert isinstance(v, str), f"Field '{k}' is not a str: {v!r}"
