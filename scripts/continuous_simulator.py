#!/usr/bin/env python
"""
Continuous GTFS-RT Data Simulator

This script continuously publishes vehicle position and progression updates
to Redis, simulating real-time telemetry data from vehicles.

The simulator runs independently of the Celery tasks, updating Redis every
N seconds (default: 15s) with new position data.

Usage:
    # Run with default settings (15s interval)
    python scripts/continuous_simulator.py

    # Run with custom interval
    python scripts/continuous_simulator.py --interval 10

    # Run as daemon (background process)
    python scripts/continuous_simulator.py --daemon

    # Initialize data on first run
    python scripts/continuous_simulator.py --init
"""

from __future__ import annotations

import os
import sys
import time
import signal
import argparse
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Simulation parameters
DEFAULT_INTERVAL = 15  # seconds between updates
LAT_LON_DELTA = 0.0002  # ~22 meters per update
MIN_SPEED = 0.0  # m/s
MAX_SPEED = 25.0  # m/s (~90 km/h)
STOP_PROBABILITY = 0.15  # 15% chance to be at a stop
ADVANCE_STOP_PROBABILITY = 0.25  # 25% chance to advance to next stop


# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    print("\n\nReceived shutdown signal. Stopping simulator...")
    running = False


def get_redis() -> redis.Redis:
    """Get Redis client with decode_responses=True."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )


def initialize_data() -> None:
    """Initialize Redis with base vehicle data (one-time setup)."""
    from redis_seed_data import seed

    print(f"\n{'=' * 80}")
    print("Initializing Redis with base data...")
    print(f"{'=' * 80}\n")

    seed()

    print("\n✓ Initialization complete!")


def update_vehicle_position(r: redis.Redis, vehicle_id: str) -> Dict[str, Any]:
    """
    Update vehicle position with realistic movement simulation.

    Args:
        r: Redis client
        vehicle_id: Vehicle identifier

    Returns:
        Updated position data
    """
    # Get current position
    position = r.hgetall(f"vehicle:{vehicle_id}:position")

    if not position:
        print(f"  ⚠️  No position data for {vehicle_id}")
        return {}

    # Parse current values
    current_lat = float(position.get("latitude", 9.9365))
    current_lon = float(position.get("longitude", -84.0511))
    current_bearing = float(position.get("bearing", 0))
    current_speed = float(position.get("speed", 0))
    current_odometer = float(position.get("odometer", 0))

    # Simulate movement based on current bearing and speed
    # Convert bearing to radians for calculation
    import math

    bearing_rad = math.radians(current_bearing)

    # Calculate new position (approximate)
    # 1 degree latitude ≈ 111 km, 1 degree longitude ≈ 111 km * cos(latitude)
    distance_km = (current_speed * DEFAULT_INTERVAL) / 1000  # speed is in m/s

    if current_speed > 0:
        # Moving: update position based on bearing
        delta_lat = (distance_km / 111) * math.cos(bearing_rad)
        delta_lon = (
            distance_km / (111 * math.cos(math.radians(current_lat)))
        ) * math.sin(bearing_rad)
    else:
        # Stopped: small random jitter
        delta_lat = random.uniform(-LAT_LON_DELTA / 10, LAT_LON_DELTA / 10)
        delta_lon = random.uniform(-LAT_LON_DELTA / 10, LAT_LON_DELTA / 10)

    new_lat = current_lat + delta_lat
    new_lon = current_lon + delta_lon

    # Update bearing (small random changes, ±30 degrees)
    new_bearing = (current_bearing + random.uniform(-30, 30)) % 360

    # Update speed (gradual changes)
    speed_change = random.uniform(-3, 3)  # ±3 m/s change
    new_speed = max(MIN_SPEED, min(MAX_SPEED, current_speed + speed_change))

    # Update odometer
    distance_m = current_speed * DEFAULT_INTERVAL
    new_odometer = current_odometer + distance_m

    # Update timestamp
    new_timestamp = int(datetime.now(timezone.utc).timestamp())

    # Build updated position
    updated_position = {
        "timestamp": new_timestamp,
        "latitude": f"{new_lat:.6f}",
        "longitude": f"{new_lon:.6f}",
        "bearing": f"{new_bearing:.1f}",
        "speed": f"{new_speed:.1f}",
        "odometer": f"{new_odometer:.1f}",
    }

    # Write to Redis
    r.hset(f"vehicle:{vehicle_id}:position", mapping=updated_position)

    return updated_position


def update_vehicle_progression(
    r: redis.Redis, run: Dict[str, str], vehicle_id: str
) -> Dict[str, Any]:
    """
    Update vehicle progression (stop sequence and status).

    Args:
        r: Redis client
        run: Run data from Redis
        vehicle_id: Vehicle identifier

    Returns:
        Updated progression data
    """
    # Get current progression
    progression = r.hgetall(f"vehicle:{vehicle_id}:progression")

    if not progression:
        print(f"  ⚠️  No progression data for {vehicle_id}")
        return {}

    current_stop_sequence = int(progression.get("current_stop_sequence", 1))
    current_status = progression.get("current_status", "IN_TRANSIT_TO")
    current_stop_id = progression.get("stop_id", "UCR_0_01")
    congestion_level = progression.get("congestion_level", "RUNNING_SMOOTHLY")

    # Get route info to know max stops
    route_id = run.get("route_id")
    max_stops = 10  # Default
    if route_id == "bUCR_L1":
        max_stops = 12
    elif route_id == "bUCR_L2":
        max_stops = 10

    # Decide if vehicle should advance
    should_advance = random.random() < ADVANCE_STOP_PROBABILITY

    if should_advance:
        if current_status == "IN_TRANSIT_TO":
            # Arriving at stop
            new_status = "STOPPED_AT"
            new_stop_sequence = current_stop_sequence
        elif current_status == "STOPPED_AT":
            # Departing from stop
            new_status = "IN_TRANSIT_TO"
            new_stop_sequence = min(current_stop_sequence + 1, max_stops)
        elif current_status == "INCOMING_AT":
            # Arriving at stop
            new_status = "STOPPED_AT"
            new_stop_sequence = current_stop_sequence
        else:
            # Default to in transit
            new_status = "IN_TRANSIT_TO"
            new_stop_sequence = current_stop_sequence
    else:
        # No change
        new_status = current_status
        new_stop_sequence = current_stop_sequence

    # Update stop_id based on sequence
    new_stop_id = f"UCR_0_{new_stop_sequence:02d}"

    # Randomly vary congestion level
    congestion_options = [
        "RUNNING_SMOOTHLY",
        "STOP_AND_GO",
        "CONGESTION",
        "SEVERE_CONGESTION",
    ]
    if random.random() < 0.1:  # 10% chance to change
        new_congestion_level = random.choice(congestion_options)
    else:
        new_congestion_level = congestion_level

    # Build updated progression
    updated_progression = {
        "current_stop_sequence": new_stop_sequence,
        "stop_id": new_stop_id,
        "current_status": new_status,
        "congestion_level": new_congestion_level,
    }

    # Write to Redis
    r.hset(f"vehicle:{vehicle_id}:progression", mapping=updated_progression)

    return updated_progression


def update_vehicle_occupancy(r: redis.Redis, vehicle_id: str) -> Dict[str, Any]:
    """
    Update vehicle occupancy status.

    Args:
        r: Redis client
        vehicle_id: Vehicle identifier

    Returns:
        Updated occupancy data
    """
    # Get current occupancy
    occupancy = r.hgetall(f"vehicle:{vehicle_id}:occupancy")

    if not occupancy:
        return {}

    current_percentage = int(occupancy.get("occupancy_percentage", 50))

    # Simulate occupancy changes (±15%)
    percentage_change = random.randint(-15, 15)
    new_percentage = max(0, min(100, current_percentage + percentage_change))

    # Map percentage to status
    if new_percentage < 20:
        new_status = "MANY_SEATS_AVAILABLE"
    elif new_percentage < 50:
        new_status = "FEW_SEATS_AVAILABLE"
    elif new_percentage < 80:
        new_status = "STANDING_ROOM_ONLY"
    else:
        new_status = "FULL"

    # Build updated occupancy
    updated_occupancy = {
        "occupancy_status": new_status,
        "occupancy_percentage": new_percentage,
    }

    # Write to Redis
    r.hset(f"vehicle:{vehicle_id}:occupancy", mapping=updated_occupancy)

    return updated_occupancy


def run_simulation_cycle(
    r: redis.Redis,
    stop_vehicles: set = None,
    only_vehicles: set = None,
    random_drop_rate: int = 0,
    stop_all: bool = False,
) -> int:
    """
    Run one simulation cycle - update all vehicles.

    Args:
        r: Redis client
        stop_vehicles: Set of vehicle IDs to NOT update (simulate stopped vehicles)
        only_vehicles: Set of vehicle IDs to ONLY update (simulate partial system)
        random_drop_rate: Percentage (0-100) chance to skip each vehicle
        stop_all: If True, don't update any vehicles (simulate complete failure)

    Returns:
        Number of vehicles updated
    """
    # Get all in-progress runs
    runs_in_progress = r.smembers("runs:in_progress")

    if not runs_in_progress:
        print("  ⚠️  No runs in progress!")
        return 0

    # If stop_all is set, don't update anything
    if stop_all:
        print("  ⚠️  Skipping all updates (--stop-all-after triggered)")
        return 0

    updated_count = 0
    skipped_count = 0

    for run_id in runs_in_progress:
        run = r.hgetall(run_id)
        vehicle_id = run.get("vehicle")

        if not vehicle_id:
            continue

        # Test case: skip if in stop_vehicles list
        if stop_vehicles and vehicle_id in stop_vehicles:
            print(f"  ⏸️  {vehicle_id}: Skipped (--stop-vehicle)")
            skipped_count += 1
            continue

        # Test case: skip if NOT in only_vehicles list
        if only_vehicles and vehicle_id not in only_vehicles:
            print(f"  ⏸️  {vehicle_id}: Skipped (--only-vehicle)")
            skipped_count += 1
            continue

        # Test case: random drop
        if random_drop_rate > 0 and random.randint(1, 100) <= random_drop_rate:
            print(f"  ⏸️  {vehicle_id}: Skipped (random drop)")
            skipped_count += 1
            continue

        # Update position
        position = update_vehicle_position(r, vehicle_id)

        if position:
            # Update progression
            progression = update_vehicle_progression(r, run, vehicle_id)

            # Update occupancy
            occupancy = update_vehicle_occupancy(r, vehicle_id)

            # Log the update
            print(
                f"  ✓ {vehicle_id}: "
                f"({position['latitude']}, {position['longitude']}) "
                f"@ {position['speed']}m/s | "
                f"Stop {progression.get('current_stop_sequence', '?')} "
                f"{progression.get('current_status', '?')} | "
                f"{occupancy.get('occupancy_percentage', '?')}% full"
            )

            updated_count += 1

    if skipped_count > 0:
        print(f"  ⏸️  Skipped {skipped_count} vehicles (test mode)")

    return updated_count


def run_continuous_simulation(
    interval: int = DEFAULT_INTERVAL,
    stop_vehicles: set = None,
    only_vehicles: set = None,
    random_drop_rate: int = 0,
    stop_all_after: int = 0,
) -> None:
    """
    Run continuous simulation loop.

    Args:
        interval: Seconds between update cycles
        stop_vehicles: Set of vehicle IDs to NOT update
        only_vehicles: Set of vehicle IDs to ONLY update
        random_drop_rate: Percentage (0-100) chance to skip each vehicle
        stop_all_after: Stop all updates after N cycles
    """
    global running

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"\n{'=' * 80}")
    print("GTFS-RT Continuous Data Simulator")
    print(f"{'=' * 80}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    print(f"Update Interval: {interval} seconds")
    if stop_vehicles:
        print(f"Test Mode: Stopping vehicles: {', '.join(sorted(stop_vehicles))}")
    if only_vehicles:
        print(f"Test Mode: Only updating vehicles: {', '.join(sorted(only_vehicles))}")
    if random_drop_rate > 0:
        print(f"Test Mode: Random drop rate: {random_drop_rate}%")
    if stop_all_after > 0:
        print(f"Test Mode: Stop all updates after cycle {stop_all_after}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")
    print("Press Ctrl+C to stop\n")

    r = get_redis()

    cycle = 0

    try:
        while running:
            cycle += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[Cycle {cycle}] {timestamp}")
            print(f"{'-' * 80}")

            # Check if we should stop all updates
            stop_all = stop_all_after > 0 and cycle > stop_all_after

            # Run simulation cycle
            updated = run_simulation_cycle(
                r, stop_vehicles, only_vehicles, random_drop_rate, stop_all
            )

            print(f"{'-' * 80}")
            print(f"Updated {updated} vehicles\n")

            # Wait for next cycle
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nStopping simulation...")

    print(f"\n{'=' * 80}")
    print(f"Simulation stopped after {cycle} cycles")
    print(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Continuous GTFS-RT data simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (15s interval)
  python scripts/continuous_simulator.py

  # Run with custom interval (10s)
  python scripts/continuous_simulator.py --interval 10

  # Initialize Redis data first
  python scripts/continuous_simulator.py --init

  # Initialize and start simulation
  python scripts/continuous_simulator.py --init --interval 15

Test Cases (Edge Case Simulation):
  # Stop updating a specific vehicle (simulate data loss)
  python scripts/continuous_simulator.py --stop-vehicle unit-10

  # Stop multiple vehicles
  python scripts/continuous_simulator.py --stop-vehicle unit-10 --stop-vehicle unit-22

  # Only update specific vehicle(s) (all others stop)
  python scripts/continuous_simulator.py --only-vehicle unit-10

  # Random drop rate (30% chance to skip each vehicle each cycle)
  python scripts/continuous_simulator.py --random-drop-rate 30

  # Stop all updates after 5 cycles (simulate complete system failure)
  python scripts/continuous_simulator.py --stop-all-after 5
        """,
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between updates (default: {DEFAULT_INTERVAL})",
    )

    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize Redis with base data before starting simulation",
    )

    # Test case arguments
    parser.add_argument(
        "--stop-vehicle",
        action="append",
        dest="stop_vehicles",
        metavar="VEHICLE_ID",
        help="Stop updating specific vehicle (can be repeated). Example: --stop-vehicle unit-10",
    )

    parser.add_argument(
        "--only-vehicle",
        action="append",
        dest="only_vehicles",
        metavar="VEHICLE_ID",
        help="Only update specific vehicle(s), stop all others (can be repeated). Example: --only-vehicle unit-10",
    )

    parser.add_argument(
        "--random-drop-rate",
        type=int,
        default=0,
        metavar="PERCENT",
        help="Percentage (0-100) chance to skip each vehicle each cycle. Example: --random-drop-rate 30",
    )

    parser.add_argument(
        "--stop-all-after",
        type=int,
        default=0,
        metavar="CYCLES",
        help="Stop all updates after N cycles (simulate complete failure). Example: --stop-all-after 5",
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

    # Initialize data if requested
    if args.init:
        initialize_data()
        print("\nStarting simulation in 3 seconds...\n")
        time.sleep(3)

    # Check if we have data
    r = get_redis()
    runs = r.smembers("runs:in_progress")
    if not runs:
        print("\n⚠️  No data in Redis!")
        print("\nRun with --init to initialize data:")
        print("  python scripts/continuous_simulator.py --init")
        print("\nOr seed manually:")
        print("  python scripts/redis_seed_data.py")
        sys.exit(1)

    # Validate random drop rate
    if args.random_drop_rate < 0 or args.random_drop_rate > 100:
        print("\n⚠️  Invalid --random-drop-rate. Must be between 0 and 100.")
        sys.exit(1)

    # Convert lists to sets
    stop_vehicles = set(args.stop_vehicles) if args.stop_vehicles else None
    only_vehicles = set(args.only_vehicles) if args.only_vehicles else None

    # Validate vehicle IDs if provided
    if stop_vehicles or only_vehicles:
        all_vehicles = set()
        for run_id in runs:
            run = r.hgetall(run_id)
            if run.get("vehicle"):
                all_vehicles.add(run.get("vehicle"))

        if stop_vehicles:
            invalid = stop_vehicles - all_vehicles
            if invalid:
                print(
                    f"\n⚠️  Warning: Unknown vehicle IDs in --stop-vehicle: {', '.join(invalid)}"
                )
                print(f"Available vehicles: {', '.join(sorted(all_vehicles))}")

        if only_vehicles:
            invalid = only_vehicles - all_vehicles
            if invalid:
                print(
                    f"\n⚠️  Warning: Unknown vehicle IDs in --only-vehicle: {', '.join(invalid)}"
                )
                print(f"Available vehicles: {', '.join(sorted(all_vehicles))}")

    # Run simulation
    run_continuous_simulation(
        interval=args.interval,
        stop_vehicles=stop_vehicles,
        only_vehicles=only_vehicles,
        random_drop_rate=args.random_drop_rate,
        stop_all_after=args.stop_all_after,
    )


if __name__ == "__main__":
    main()
