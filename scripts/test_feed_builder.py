#!/usr/bin/env python
"""
Test script for GTFS-RT feed builders (VehiclePositions and TripUpdates).
This script mimics the actual builder functions using Redis seed data.

Usage:
    1. Run redis_seed_data.py to populate Redis with test data
    2. Run this script with --type vp or --type tu to test the builders

Examples:
    python scripts/test_feed_builder.py --type vp
    python scripts/test_feed_builder.py --type tu
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Any, Dict

import redis

# Import mock stop time updates builder
from mock_stop_time_updates import build_stop_time_updates


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


def get_redis() -> redis.Redis:
    """Get Redis client with decode_responses=True."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )


def get_current_timestamp() -> int:
    """Get current Unix timestamp."""
    return int(datetime.now().timestamp())


def build_vehicle_positions_test() -> Dict[str, Any]:
    """
    Test version of build_vehicle_positions() that mimics the actual function.
    Uses the consume-and-delete pattern from Redis.
    """
    r = get_redis()

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = get_current_timestamp()
    feed_message["header"]["feed_version"] = "1.0.0"

    # Feed message entity
    feed_message["entity"] = []

    # Get all in-progress runs
    runs_in_progress = r.smembers("runs:in_progress")

    print(f"\n[VP] Found {len(runs_in_progress)} runs in progress")

    for run_id in runs_in_progress:
        print(f"[VP] Processing {run_id}")
        run = r.hgetall(run_id)
        vehicle_id = run["vehicle"]
        vehicle = r.hgetall(f"vehicle:{vehicle_id}:data")
        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")
        occupancy = r.hgetall(f"vehicle:{vehicle_id}:occupancy")

        # Delete run, vehicle, position, progression, and occupancy in Redis
        print(f"[VP] Deleting keys for {run_id}")
        r.delete(run_id)
        r.delete(f"vehicle:{vehicle_id}:data")
        r.delete(f"vehicle:{vehicle_id}:position")
        r.delete(f"vehicle:{vehicle_id}:progression")
        r.delete(f"vehicle:{vehicle_id}:occupancy")

        if not position and not progression and not occupancy:
            print(f"[VP] Skipping {run_id} - no position/progression/occupancy data")
            continue

        # Build entity
        entity = {}
        entity["id"] = f"{vehicle['id']}"
        entity["vehicle"] = {}
        # Timestamp
        entity["vehicle"]["timestamp"] = int(position["timestamp"])
        # Trip
        entity["vehicle"]["trip"] = {}
        entity["vehicle"]["trip"]["trip_id"] = run["trip_id"]
        entity["vehicle"]["trip"]["route_id"] = run["route_id"]
        entity["vehicle"]["trip"]["direction_id"] = run["direction_id"]
        entity["vehicle"]["trip"]["start_time"] = run["start_time"]
        entity["vehicle"]["trip"]["start_date"] = run["start_date"]
        entity["vehicle"]["trip"]["schedule_relationship"] = run["schedule_relationship"]
        # Vehicle
        entity["vehicle"]["vehicle"] = {}
        entity["vehicle"]["vehicle"]["id"] = vehicle["id"]
        entity["vehicle"]["vehicle"]["label"] = vehicle["label"]
        entity["vehicle"]["vehicle"]["license_plate"] = vehicle["license_plate"]
        # Position
        if position:
            entity["vehicle"]["position"] = {}
            entity["vehicle"]["position"]["latitude"] = position["latitude"]
            entity["vehicle"]["position"]["longitude"] = position["longitude"]
            entity["vehicle"]["position"]["bearing"] = position["bearing"]
            entity["vehicle"]["position"]["odometer"] = position["odometer"]
            entity["vehicle"]["position"]["speed"] = position["speed"]
        # Progression
        if progression:
            entity["vehicle"]["current_stop_sequence"] = progression["current_stop_sequence"]
            entity["vehicle"]["stop_id"] = progression["stop_id"]
            entity["vehicle"]["current_status"] = progression["current_status"]
            entity["vehicle"]["congestion_level"] = progression["congestion_level"]
        # Occupancy
        if occupancy:
            entity["vehicle"]["occupancy_status"] = occupancy["occupancy_status"]
            entity["vehicle"]["occupancy_percentage"] = occupancy["occupancy_percentage"]
        # Append entity to feed message
        feed_message["entity"].append(entity)

    return feed_message


def build_trip_updates_test() -> Dict[str, Any]:
    """
    Test version of build_trip_updates() that mimics the actual function.
    Uses the consume-and-delete pattern from Redis.
    Includes mock stop_time_updates.
    """
    r = get_redis()

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = get_current_timestamp()
    feed_message["header"]["feed_version"] = "1.0.0"

    # Feed message entity
    feed_message["entity"] = []

    # Get all in-progress runs
    runs_in_progress = r.smembers("runs:in_progress")

    print(f"\n[TU] Found {len(runs_in_progress)} runs in progress")

    for run_id in runs_in_progress:
        print(f"[TU] Processing {run_id}")
        run = r.hgetall(run_id)
        vehicle_id = run["vehicle"]
        vehicle = r.hgetall(f"vehicle:{vehicle_id}:data")
        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        progression = r.hgetall(f"vehicle:{vehicle_id}:progression")

        # Delete run, vehicle, position and progression in Redis
        print(f"[TU] Deleting keys for {run_id}")
        r.delete(run_id)
        r.delete(f"vehicle:{vehicle_id}:data")
        r.delete(f"vehicle:{vehicle_id}:position")
        r.delete(f"vehicle:{vehicle_id}:progression")

        entity = {}
        entity["id"] = vehicle["id"]
        entity["trip_update"] = {}
        entity["trip_update"]["timestamp"] = int(position["timestamp"])
        entity["trip_update"]["trip"] = {}
        entity["trip_update"]["trip"]["trip_id"] = run["trip_id"]
        entity["trip_update"]["trip"]["route_id"] = run["route_id"]
        entity["trip_update"]["trip"]["direction_id"] = run["direction_id"]
        entity["trip_update"]["trip"]["start_time"] = run["start_time"]
        entity["trip_update"]["trip"]["start_date"] = run["start_date"]
        entity["trip_update"]["trip"]["schedule_relationship"] = run["schedule_relationship"]
        entity["trip_update"]["vehicle"] = {}
        entity["trip_update"]["vehicle"]["id"] = vehicle["id"]
        entity["trip_update"]["vehicle"]["label"] = vehicle["label"]
        entity["trip_update"]["vehicle"]["license_plate"] = vehicle["license_plate"]

        # Build stop_time_updates using mock builder
        entity["trip_update"]["stop_time_update"] = []
        stop_time_updates = build_stop_time_updates(
            run=run, position=position, progression=progression
        )
        for update in stop_time_updates:
            stop_time_update = {}
            stop_time_update["stop_sequence"] = update["stop_sequence"]
            stop_time_update["stop_id"] = update["stop_id"]
            stop_time_update["arrival"] = {}
            stop_time_update["arrival"]["time"] = update["eta_posix"]
            stop_time_update["arrival"]["uncertainty"] = update["uncertainty"]
            stop_time_update["departure"] = {}
            stop_time_update["departure"]["time"] = update["eta_posix"]
            stop_time_update["departure"]["uncertainty"] = update["uncertainty"]

            # Append stop time update to stop time updates
            entity["trip_update"]["stop_time_update"].append(stop_time_update)

        # Append entity to feed message
        feed_message["entity"].append(entity)

    return feed_message


def check_redis_data():
    """Check what data is currently in Redis."""
    r = get_redis()
    runs = r.smembers("runs:in_progress")
    print(f"\n{'='*80}")
    print(f"Redis Status Check")
    print(f"{'='*80}")
    print(f"Runs in progress: {len(runs)}")
    for run_id in runs:
        print(f"  - {run_id}")
    print(f"{'='*80}\n")
    return len(runs) > 0


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description="Test GTFS-RT feed builders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/test_feed_builder.py --type vp    # Test VehiclePositions
  python scripts/test_feed_builder.py --type tu    # Test TripUpdates
        """
    )
    parser.add_argument(
        "--type",
        choices=["vp", "tu"],
        required=True,
        help="Feed type to test: 'vp' for VehiclePositions, 'tu' for TripUpdates"
    )

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"GTFS-RT Feed Builder Test")
    print(f"{'='*80}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    print(f"Feed Type: {'VehiclePositions' if args.type == 'vp' else 'TripUpdates'}")

    # Check if we have data in Redis
    has_data = check_redis_data()

    if not has_data:
        print("\n⚠️  No data found in Redis!")
        print("Please run: python scripts/redis_seed_data.py")
        sys.exit(1)

    if args.type == "vp":
        # Test VehiclePositions
        print(f"\n{'='*80}")
        print("Testing VehiclePositions Builder")
        print(f"{'='*80}")
        vp_feed = build_vehicle_positions_test()
        print(f"\n✓ Built VP feed with {len(vp_feed['entity'])} entities")

        # Save VehiclePositions to file
        vp_output = "scripts/test_vehicle_positions.json"
        with open(vp_output, "w") as f:
            json.dump(vp_feed, f, indent=2)
        print(f"✓ Saved to {vp_output}")

        # Show VP sample
        if vp_feed["entity"]:
            print(f"\nSample VehiclePosition entity:")
            print(json.dumps(vp_feed["entity"][0], indent=2))

        print(f"\n{'='*80}")
        print("⚠️  WARNING: Redis data has been consumed!")
        print("Re-seed Redis before testing again")
        print(f"{'='*80}")

    elif args.type == "tu":
        # Test TripUpdates
        print(f"\n{'='*80}")
        print("Testing TripUpdates Builder")
        print(f"{'='*80}")
        tu_feed = build_trip_updates_test()
        print(f"\n✓ Built TU feed with {len(tu_feed['entity'])} entities")

        # Save TripUpdates to file
        tu_output = "scripts/test_trip_updates.json"
        with open(tu_output, "w") as f:
            json.dump(tu_feed, f, indent=2)
        print(f"✓ Saved to {tu_output}")

        # Show TU sample
        if tu_feed["entity"]:
            print(f"\nSample TripUpdate entity:")
            print(json.dumps(tu_feed["entity"][0], indent=2))

        print(f"\n{'='*80}")
        print("⚠️  WARNING: Redis data has been consumed!")
        print("Re-seed Redis before testing again")
        print(f"{'='*80}")


if __name__ == "__main__":
    main()
