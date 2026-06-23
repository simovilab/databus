"""Pure unit tests for the telemetry key templates.

No Django, no Redis — runnable under plain pytest.
"""

from runs.domain.telemetry import keys


def test_position_key():
    assert keys.position_key("v42") == "vehicle:v42:position"


def test_occupancy_key():
    assert keys.occupancy_key("v42") == "vehicle:v42:occupancy"


def test_metadata_key():
    assert keys.metadata_key("v42") == "vehicle:v42:metadata"


def test_current_run_key():
    assert keys.current_run_key("v42") == "vehicle:v42:current_run"


def test_trip_key():
    assert keys.trip_key("r99") == "run:r99:trip"


def test_stop_status_key():
    assert keys.stop_status_key("r99") == "run:r99:vehicle_stop_status"


def test_congestion_key():
    assert keys.congestion_key("r99") == "run:r99:congestion_level"


def test_run_key():
    assert keys.run_key("r99") == "run:r99"


def test_last_seen_key():
    assert keys.last_seen_key("r99") == "runs:last_seen:r99"


def test_keys_use_string_representation_of_id():
    """Keys should work with any string representation of an id."""
    uid = "550e8400-e29b-41d4-a716-446655440000"
    assert keys.run_key(uid) == f"run:{uid}"
    assert keys.position_key(uid) == f"vehicle:{uid}:position"
