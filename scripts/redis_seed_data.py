#!/usr/bin/env python
"""
Populate Redis with fake telemetry data so the feed builders can be exercised
without having to rely on the relational database. The script writes the
following key patterns:

- runs:in_progress -> set with all active run identifiers (e.g., "run:1001").
- run:{run_id} -> hash with trip metadata (route, trip, start times, vehicle).
- vehicle:{vehicle_id}:data -> hash with vehicle descriptors.
- vehicle:{vehicle_id}:position -> hash with the latest GPS sample.
- vehicle:{vehicle_id}:progression -> hash with stop-level progress details.
- vehicle:{vehicle_id}:occupancy -> hash with crowding information.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


def _build_run_fixtures() -> List[Dict[str, Dict[str, Any]]]:
    """Return a deterministic set of runs we can load into Redis."""
    now = datetime.now(timezone.utc)
    start_date = now.date().strftime("%Y%m%d")
    base_timestamp = int(now.timestamp())

    def fixture(
        run_id: str,
        vehicle_id: str,
        label: str,
        license_plate: str,
        route_id: str,
        trip_id: str,
        direction_id: int,
        shape_id: str,
        start_time: timedelta,
        schedule_relationship: str,
        current_stop_sequence: int,
        stop_id: str,
        current_status: str,
        congestion_level: str,
        occupancy_status: str,
        occupancy_percentage: int,
        latitude: float,
        longitude: float,
        bearing: float,
        odometer: float,
        speed: float,
    ) -> Dict[str, Dict[str, Any]]:
        run = {
            "vehicle": vehicle_id,
            "route_id": route_id,
            "trip_id": trip_id,
            "direction_id": str(direction_id),
            "shape_id": shape_id,
            "start_date": start_date,
            "start_time": str(start_time),
            "schedule_relationship": schedule_relationship,
        }
        vehicle = {
            "id": vehicle_id,
            "label": label,
            "license_plate": license_plate,
        }
        position = {
            "timestamp": base_timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "bearing": bearing,
            "odometer": odometer,
            "speed": speed,
        }
        progression = {
            "current_stop_sequence": current_stop_sequence,
            "stop_id": stop_id,
            "current_status": current_status,
            "congestion_level": congestion_level,
        }
        occupancy = {
            "occupancy_status": occupancy_status,
            "occupancy_percentage": occupancy_percentage,
        }
        return {
            "run_id": run_id,
            "run": run,
            "vehicle": vehicle,
            "position": position,
            "progression": progression,
            "occupancy": occupancy,
        }

    return [
        fixture(
            run_id="run-1001",
            vehicle_id="unit-10",
            label="Unit 10",
            license_plate="ABC-010",
            route_id="bUCR_L2",
            trip_id="TRIP-EDU-01",
            direction_id=0,
            shape_id="desde_educacion_sin_milla",
            start_time=timedelta(hours=6, minutes=45),
            schedule_relationship="SCHEDULED",
            current_stop_sequence=4,
            stop_id="UCR_0_07",
            current_status="IN_TRANSIT_TO",
            congestion_level="RUNNING_SMOOTHLY",
            occupancy_status="MANY_SEATS_AVAILABLE",
            occupancy_percentage=42,
            latitude=9.9365,
            longitude=-84.0511,
            bearing=180.0,
            odometer=12876.5,
            speed=12.8,
        ),
        fixture(
            run_id="run-2002",
            vehicle_id="unit-22",
            label="Unit 22",
            license_plate="DEF-022",
            route_id="bUCR_L1",
            trip_id="TRIP-ART-11",
            direction_id=0,
            shape_id="desde_artes_con_milla",
            start_time=timedelta(hours=7, minutes=15),
            schedule_relationship="ADDED",
            current_stop_sequence=6,
            stop_id="UCR_0_08",
            current_status="STOPPED_AT",
            congestion_level="STOP_AND_GO",
            occupancy_status="FEW_SEATS_AVAILABLE",
            occupancy_percentage=78,
            latitude=9.9351,
            longitude=-84.0556,
            bearing=90.0,
            odometer=22344.2,
            speed=0.0,
        ),
    ]


def _clear_previous_seed(client: redis.Redis, fixtures: List[Dict[str, Dict[str, Any]]]):
    """Remove the keys created by a previous seeding run."""
    keys_to_delete = {"runs:in_progress"}
    for fixture in fixtures:
        run_id = fixture["run_id"]
        vehicle_id = fixture["vehicle"]["id"]
        keys_to_delete.update(
            {
                f"run:{run_id}",
                f"vehicle:{vehicle_id}:data",
                f"vehicle:{vehicle_id}:position",
                f"vehicle:{vehicle_id}:progression",
                f"vehicle:{vehicle_id}:occupancy",
            }
        )
    client.delete(*keys_to_delete)


def seed():
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )
    fixtures = _build_run_fixtures()
    _clear_previous_seed(client, fixtures)
    pipeline = client.pipeline()
    for fixture in fixtures:
        run_id = fixture["run_id"]
        run = fixture["run"]
        vehicle = fixture["vehicle"]
        vehicle_id = vehicle["id"]
        pipeline.sadd("runs:in_progress", f"run:{run_id}")
        pipeline.hset(f"run:{run_id}", mapping=run)
        pipeline.hset(f"vehicle:{vehicle_id}:data", mapping=vehicle)
        pipeline.hset(f"vehicle:{vehicle_id}:position", mapping=fixture["position"])
        pipeline.hset(f"vehicle:{vehicle_id}:progression", mapping=fixture["progression"])
        pipeline.hset(f"vehicle:{vehicle_id}:occupancy", mapping=fixture["occupancy"])
    pipeline.execute()
    print(
        f"Seeded {len(fixtures)} runs into Redis at {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )


if __name__ == "__main__":
    seed()
