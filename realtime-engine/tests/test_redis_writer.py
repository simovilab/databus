"""
Tests for Redis writer functions.

RED phase: define expected Redis key/value writes before implementation.
"""
from unittest.mock import MagicMock, call

from models import VehicleState
from redis_writer import write_vehicle_state, sync_active_runs


SAMPLE_STATE = VehicleState(
    vehicle_id="299-604",
    label="299-604",
    license_plate="299-604",
    latitude=9.9471766,
    longitude=-84.0458883,
    speed_ms=4.7222,
    odometer=262655,
    timestamp=1773951654,
    current_status="IN_TRANSIT_TO",
)


def test_write_vehicle_state_writes_data():
    r = MagicMock()
    r.exists.return_value = False
    write_vehicle_state(r, SAMPLE_STATE)
    r.hset.assert_any_call(
        "vehicle:299-604:data",
        mapping={"id": "299-604", "label": "299-604", "license_plate": "299-604"},
    )


def test_write_vehicle_state_writes_position():
    r = MagicMock()
    r.exists.return_value = False
    write_vehicle_state(r, SAMPLE_STATE)
    r.hset.assert_any_call(
        "vehicle:299-604:position",
        mapping={
            "latitude": "9.9471766",
            "longitude": "-84.0458883",
            "speed": "4.7222",
            "odometer": "262655",
            "timestamp": "1773951654",
        },
    )


def test_write_vehicle_state_writes_progression():
    r = MagicMock()
    r.exists.return_value = False
    write_vehicle_state(r, SAMPLE_STATE)
    r.hset.assert_any_call(
        "vehicle:299-604:progression",
        mapping={"current_status": "IN_TRANSIT_TO"},
    )


def test_write_vehicle_state_registers_run_if_not_exists():
    r = MagicMock()
    r.exists.return_value = False
    write_vehicle_state(r, SAMPLE_STATE)
    r.hset.assert_any_call(
        "run:navsat:299-604",
        mapping={
            "vehicle": "299-604",
            "trip_id": "",
            "route_id": "",
            "direction_id": "0",
            "start_time": "",
            "start_date": "",
            "schedule_relationship": "UNSCHEDULED",
        },
    )
    r.sadd.assert_called_once_with("runs:in_progress", "run:navsat:299-604")


def test_write_vehicle_state_skips_run_creation_if_exists():
    r = MagicMock()
    r.exists.return_value = True
    write_vehicle_state(r, SAMPLE_STATE)
    # sadd is still called (to ensure membership), but hset for run is NOT called again
    r.sadd.assert_called_once_with("runs:in_progress", "run:navsat:299-604")
    # hset only called 3 times (data, position, progression), not 4
    run_hset_calls = [
        c for c in r.hset.call_args_list if c[0][0] == "run:navsat:299-604"
    ]
    assert len(run_hset_calls) == 0


def test_sync_active_runs_removes_stale():
    r = MagicMock()
    r.smembers.return_value = {
        "run:navsat:299-604",
        "run:navsat:OLD-111",
        "run:manual:some-run",  # non-navsat run — must not be touched
    }
    sync_active_runs(r, {"299-604"})

    r.srem.assert_called_once_with("runs:in_progress", "run:navsat:OLD-111")
    r.delete.assert_called_once_with("run:navsat:OLD-111")


def test_sync_active_runs_no_stale():
    r = MagicMock()
    r.smembers.return_value = {"run:navsat:299-604"}
    sync_active_runs(r, {"299-604"})
    r.srem.assert_not_called()
    r.delete.assert_not_called()


def test_sync_active_runs_ignores_non_navsat_runs():
    r = MagicMock()
    r.smembers.return_value = {"run:manual:abc", "run:navsat:299-604"}
    sync_active_runs(r, {"299-604"})
    r.srem.assert_not_called()
    r.delete.assert_not_called()
