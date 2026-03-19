"""
Shared Redis write functions for realtime-engine.

Only realtime-engine writes to Redis; publisher and backend only read.
"""
from models import VehicleState


def write_vehicle_state(r, state: VehicleState) -> None:
    """Write vehicle data, position, and progression to Redis.

    Also registers a synthetic navsat run so the publisher includes this
    vehicle in its GTFS-RT feed. Route/trip fields are empty until a
    vehicle-to-route mapping is configured.
    """
    vid = state.vehicle_id

    r.hset(
        f"vehicle:{vid}:data",
        mapping={"id": vid, "label": state.label, "license_plate": state.license_plate},
    )
    r.hset(
        f"vehicle:{vid}:position",
        mapping={
            "latitude": str(state.latitude),
            "longitude": str(state.longitude),
            "speed": str(state.speed_ms),
            "odometer": str(state.odometer),
            "timestamp": str(state.timestamp),
        },
    )
    r.hset(
        f"vehicle:{vid}:progression",
        mapping={"current_status": state.current_status},
    )

    run_id = f"run:navsat:{vid}"
    if not r.exists(run_id):
        r.hset(
            run_id,
            mapping={
                "vehicle": vid,
                "trip_id": "",
                "route_id": "",
                "direction_id": "0",
                "start_time": "",
                "start_date": "",
                "schedule_relationship": "UNSCHEDULED",
            },
        )
    r.sadd("runs:in_progress", run_id)


def sync_active_runs(r, active_vehicle_ids: set[str]) -> None:
    """Remove navsat runs for vehicles absent from the latest poll."""
    expected_run_ids = {f"run:navsat:{vid}" for vid in active_vehicle_ids}
    all_runs = r.smembers("runs:in_progress")
    stale = {
        run_id
        for run_id in all_runs
        if run_id.startswith("run:navsat:") and run_id not in expected_run_ids
    }
    for run_id in stale:
        r.srem("runs:in_progress", run_id)
        r.delete(run_id)
