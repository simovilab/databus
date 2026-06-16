#!/usr/bin/env python
"""
Redis State Inspector

This script displays the current state of the Redis database,
showing all vehicles, runs, and their associated data.

Usage:
    # Show all data
    python scripts/inspect_redis.py

    # Show only vehicles
    python scripts/inspect_redis.py --vehicles

    # Show only runs
    python scripts/inspect_redis.py --runs

    # Show data age (how stale)
    python scripts/inspect_redis.py --show-age

    # Continuous monitoring mode (refresh every N seconds)
    python scripts/inspect_redis.py --watch 5
"""

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any

import redis


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


def get_data_age(timestamp: int) -> str:
    """
    Calculate how old the data is.

    Args:
        timestamp: POSIX timestamp

    Returns:
        Human-readable age string
    """
    now = int(datetime.now(timezone.utc).timestamp())
    age_seconds = now - timestamp

    if age_seconds < 60:
        return f"{age_seconds}s ago"
    elif age_seconds < 3600:
        return f"{age_seconds // 60}m ago"
    else:
        hours = age_seconds // 3600
        minutes = (age_seconds % 3600) // 60
        return f"{hours}h {minutes}m ago"


def inspect_runs(r: redis.Redis, show_age: bool = False) -> None:
    """
    Display all runs in Redis.

    Args:
        r: Redis client
        show_age: Whether to show data age
    """
    print(f"\n{'=' * 80}")
    print("RUNS IN PROGRESS")
    print(f"{'=' * 80}\n")

    runs_in_progress = r.smembers("runs:in_progress")

    if not runs_in_progress:
        print("  No runs in progress")
        return

    print(f"Total runs: {len(runs_in_progress)}\n")

    for run_id in sorted(runs_in_progress):
        run = r.hgetall(run_id)

        if not run:
            print(f"  {run_id}: [NO DATA]")
            continue

        print(f"  {run_id}")
        print(f"    Vehicle:      {run.get('vehicle', 'N/A')}")
        print(f"    Trip ID:      {run.get('trip_id', 'N/A')}")
        print(f"    Route ID:     {run.get('route_id', 'N/A')}")
        print(f"    Direction:    {run.get('direction_id', 'N/A')}")
        print(f"    Start Time:   {run.get('start_time', 'N/A')}")
        print(f"    Start Date:   {run.get('start_date', 'N/A')}")
        print(f"    Schedule Rel: {run.get('schedule_relationship', 'N/A')}")
        print()


def inspect_vehicles(r: redis.Redis, show_age: bool = False) -> None:
    """
    Display all vehicles and their data in Redis.

    Args:
        r: Redis client
        show_age: Whether to show data age
    """
    print(f"\n{'=' * 80}")
    print("VEHICLES")
    print(f"{'=' * 80}\n")

    # Get all vehicle keys
    vehicle_keys = set()
    for key in r.keys("vehicle:*:metadata"):
        vehicle_id = key.split(":")[1]
        vehicle_keys.add(vehicle_id)

    if not vehicle_keys:
        print("  No vehicles found")
        return

    print(f"Total vehicles: {len(vehicle_keys)}\n")

    for vehicle_id in sorted(vehicle_keys):
        # Get vehicle data
        vehicle_data = r.hgetall(f"vehicle:{vehicle_id}:metadata")
        position = r.hgetall(f"vehicle:{vehicle_id}:position")
        occupancy = r.hgetall(f"vehicle:{vehicle_id}:occupancy")

        # Resolve the current run for this vehicle (vehicle → run linkage).
        # Stop status and congestion are run-keyed because they depend on the
        # assigned trip; vehicle:*:progression is decommissioned.
        run_id = r.get(f"vehicle:{vehicle_id}:current_run")
        stop_status = r.hgetall(f"run:{run_id}:vehicle_stop_status") if run_id else {}
        congestion = r.hgetall(f"run:{run_id}:congestion_level") if run_id else {}

        print(f"  {vehicle_id}")

        # Basic data
        if vehicle_data:
            print(f"    Label:         {vehicle_data.get('label', 'N/A')}")
            print(f"    License Plate: {vehicle_data.get('license_plate', 'N/A')}")
        else:
            print(f"    [NO BASIC DATA]")

        # Position
        if position:
            timestamp = int(position.get("timestamp", 0))
            age_str = (
                f" ({get_data_age(timestamp)})" if show_age and timestamp > 0 else ""
            )
            print(f"    Position{age_str}:")
            print(
                f"      Lat/Lon:  {position.get('latitude', 'N/A')}, {position.get('longitude', 'N/A')}"
            )
            print(f"      Bearing:  {position.get('bearing', 'N/A')}°")
            print(f"      Speed:    {position.get('speed', 'N/A')} m/s")
            print(f"      Odometer: {position.get('odometer', 'N/A')} m")
            if not show_age:
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                print(f"      Updated:  {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            print(f"    Position: [NO DATA]")

        # Stop status (run:<run_id>:vehicle_stop_status — server-computed, run-keyed)
        if stop_status:
            print(f"    Stop Status (run:{run_id}):")
            print(f"      Stop Seq:  {stop_status.get('current_stop_sequence', 'N/A')}")
            print(f"      Stop ID:   {stop_status.get('stop_id', 'N/A')}")
            print(f"      Status:    {stop_status.get('current_status', 'N/A')}")
        else:
            run_label = f"run:{run_id}" if run_id else "no current run"
            print(f"    Stop Status ({run_label}): [NO DATA]")

        # Congestion level (run:<run_id>:congestion_level — server-computed, deferred)
        if congestion:
            print(f"    Congestion:")
            print(f"      Level:     {congestion.get('congestion_level', 'N/A')}")
        else:
            print(f"    Congestion: [NO DATA]")

        # Occupancy
        if occupancy:
            print(f"    Occupancy:")
            print(f"      Status:    {occupancy.get('occupancy_status', 'N/A')}")
            print(f"      Percent:   {occupancy.get('occupancy_percentage', 'N/A')}%")
        else:
            print(f"    Occupancy: [NO DATA]")

        print()


def inspect_all_keys(r: redis.Redis) -> None:
    """
    Display all keys in Redis (debug mode).

    Args:
        r: Redis client
    """
    print(f"\n{'=' * 80}")
    print("ALL REDIS KEYS")
    print(f"{'=' * 80}\n")

    all_keys = r.keys("*")

    if not all_keys:
        print("  No keys found")
        return

    print(f"Total keys: {len(all_keys)}\n")

    # Group keys by type
    sets = []
    hashes = []
    others = []

    for key in sorted(all_keys):
        key_type = r.type(key)
        if key_type == "set":
            sets.append(key)
        elif key_type == "hash":
            hashes.append(key)
        else:
            others.append(key)

    if sets:
        print(f"  Sets ({len(sets)}):")
        for key in sets:
            members = r.smembers(key)
            print(f"    {key} ({len(members)} members)")
        print()

    if hashes:
        print(f"  Hashes ({len(hashes)}):")
        for key in hashes:
            field_count = r.hlen(key)
            print(f"    {key} ({field_count} fields)")
        print()

    if others:
        print(f"  Other ({len(others)}):")
        for key in others:
            print(f"    {key} ({r.type(key)})")
        print()


def inspect_summary(r: redis.Redis, show_age: bool = False) -> None:
    """
    Display summary statistics.

    Args:
        r: Redis client
        show_age: Whether to show data age
    """
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")

    # Count runs
    runs_count = len(r.smembers("runs:in_progress"))

    # Count vehicles
    vehicle_keys = len(r.keys("vehicle:*:metadata"))

    # Count vehicles with recent data
    recent_count = 0
    stale_count = 0
    no_data_count = 0

    now = int(datetime.now(timezone.utc).timestamp())

    for key in r.keys("vehicle:*:position"):
        position = r.hgetall(key)
        if position:
            timestamp = int(position.get("timestamp", 0))
            age = now - timestamp
            if age < 120:  # 2 minutes
                recent_count += 1
            elif age < 300:  # 5 minutes
                stale_count += 1
            else:
                no_data_count += 1
        else:
            no_data_count += 1

    print(f"  Runs in progress:    {runs_count}")
    print(f"  Total vehicles:      {vehicle_keys}")

    if show_age:
        print(f"  Recent data (<2m):   {recent_count}")
        print(f"  Stale data (2-5m):   {stale_count}")
        print(f"  Very stale (>5m):    {no_data_count}")

    print()


def clear_screen():
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Redis state inspector for GTFS-RT data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all data
  python scripts/inspect_redis.py

  # Show only vehicles
  python scripts/inspect_redis.py --vehicles

  # Show only runs
  python scripts/inspect_redis.py --runs

  # Show data age
  python scripts/inspect_redis.py --show-age

  # Watch mode (refresh every 5 seconds)
  python scripts/inspect_redis.py --watch 5

  # Show all Redis keys (debug)
  python scripts/inspect_redis.py --all-keys
        """,
    )

    parser.add_argument(
        "--vehicles",
        action="store_true",
        help="Show only vehicle data",
    )

    parser.add_argument(
        "--runs",
        action="store_true",
        help="Show only run data",
    )

    parser.add_argument(
        "--all-keys",
        action="store_true",
        help="Show all Redis keys (debug mode)",
    )

    parser.add_argument(
        "--show-age",
        action="store_true",
        help="Show how old the data is",
    )

    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Continuous monitoring mode (refresh every N seconds)",
    )

    args = parser.parse_args()

    # Check Redis connection
    try:
        r = get_redis()
        r.ping()
    except Exception as e:
        print(f"\n⚠️  Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print(f"Error: {e}")
        print("\nMake sure Redis is running:")
        print("  - Docker: docker compose -f compose.dev.yml up state")
        print("  - Local: redis-server")
        sys.exit(1)

    # Watch mode
    if args.watch:
        try:
            while True:
                clear_screen()
                print(f"Redis Inspector - Auto-refresh every {args.watch}s")
                print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Press Ctrl+C to stop\n")

                inspect_summary(r, args.show_age)

                if args.vehicles or not (args.runs or args.all_keys):
                    inspect_vehicles(r, args.show_age)

                if args.runs or not (args.vehicles or args.all_keys):
                    inspect_runs(r, args.show_age)

                if args.all_keys:
                    inspect_all_keys(r)

                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n\nStopped monitoring.\n")
            sys.exit(0)
    else:
        # Single inspection
        print(f"\nRedis Inspector")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        inspect_summary(r, args.show_age)

        if args.all_keys:
            inspect_all_keys(r)
        elif args.vehicles:
            inspect_vehicles(r, args.show_age)
        elif args.runs:
            inspect_runs(r, args.show_age)
        else:
            inspect_vehicles(r, args.show_age)
            inspect_runs(r, args.show_age)


if __name__ == "__main__":
    main()
