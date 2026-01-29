#!/usr/bin/env python
"""
Test script for GTFS-RT publisher tasks (VehiclePositions and TripUpdates).
This script simulates continuous vehicle position updates to Redis and allows
testing the Celery tasks in the publisher container.

Usage:
    1. Start the Docker Compose stack: docker compose -f compose.dev.yml up
    2. Seed initial data: python scripts/redis_seed_data.py
    3. Run this test script:
       - Test VP task: python scripts/test_publisher_tasks.py --task vp
       - Test TU task: python scripts/test_publisher_tasks.py --task tu
       - Simulate updates: python scripts/test_publisher_tasks.py --simulate
       - Run both tasks: python scripts/test_publisher_tasks.py --task both

Examples:
    # Test VehiclePosition builder directly
    python scripts/test_publisher_tasks.py --task vp

    # Test TripUpdate builder directly
    python scripts/test_publisher_tasks.py --task tu

    # Simulate continuous position updates every 5 seconds
    python scripts/test_publisher_tasks.py --simulate --interval 5

    # Test both tasks
    python scripts/test_publisher_tasks.py --task both
"""

from __future__ import annotations

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
import random

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


def check_redis_connection() -> bool:
    """Check if Redis is available."""
    try:
        r = get_redis()
        r.ping()
        return True
    except Exception as e:
        print(f"\n⚠️  Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}")
        print(f"Error: {e}")
        print("\nMake sure Redis is running:")
        print("  - Docker: docker compose -f compose.dev.yml up state")
        print("  - Local: redis-server")
        return False


def check_redis_data() -> bool:
    """Check what data is currently in Redis."""
    r = get_redis()
    runs = r.smembers("runs:in_progress")
    print(f"\n{'=' * 80}")
    print(f"Redis Status Check")
    print(f"{'=' * 80}")
    print(f"Runs in progress: {len(runs)}")
    for run_id in runs:
        print(f"  - {run_id}")
    print(f"{'=' * 80}\n")
    return len(runs) > 0


def simulate_position_update(run_id: str, vehicle_id: str) -> None:
    """
    Simulate a position update for a vehicle.
    Updates timestamp, latitude, longitude, and optionally bearing/speed.
    """
    r = get_redis()

    # Get current position
    position = r.hgetall(f"vehicle:{vehicle_id}:position")

    if not position:
        print(f"Warning: No position data for {vehicle_id}")
        return

    # Update timestamp to current time
    new_timestamp = int(datetime.now(timezone.utc).timestamp())

    # Simulate small position changes (± 0.0001 degrees ~ 11 meters)
    current_lat = float(position.get("latitude", 9.9365))
    current_lon = float(position.get("longitude", -84.0511))

    new_lat = current_lat + random.uniform(-0.0001, 0.0001)
    new_lon = current_lon + random.uniform(-0.0001, 0.0001)

    # Simulate bearing changes
    new_bearing = random.uniform(0, 360)

    # Simulate speed changes (0-20 m/s)
    new_speed = random.uniform(0, 20)

    # Update position in Redis
    r.hset(f"vehicle:{vehicle_id}:position", mapping={
        "timestamp": new_timestamp,
        "latitude": f"{new_lat:.6f}",
        "longitude": f"{new_lon:.6f}",
        "bearing": f"{new_bearing:.1f}",
        "speed": f"{new_speed:.1f}",
        "odometer": position.get("odometer", "0"),
    })

    print(f"  ✓ Updated position for {vehicle_id}: ({new_lat:.6f}, {new_lon:.6f})")


def simulate_progression_update(vehicle_id: str) -> None:
    """
    Simulate a progression update for a vehicle.
    Optionally advances the vehicle to the next stop.
    """
    r = get_redis()

    progression = r.hgetall(f"vehicle:{vehicle_id}:progression")

    if not progression:
        print(f"Warning: No progression data for {vehicle_id}")
        return

    current_stop = int(progression.get("current_stop_sequence", 1))
    current_status = progression.get("current_status", "IN_TRANSIT_TO")

    # Randomly advance progression
    if random.random() > 0.7:  # 30% chance to advance
        if current_status == "IN_TRANSIT_TO":
            new_status = "STOPPED_AT"
        else:
            new_status = "IN_TRANSIT_TO"
            current_stop += 1

        r.hset(f"vehicle:{vehicle_id}:progression", mapping={
            "current_stop_sequence": current_stop,
            "stop_id": progression.get("stop_id", f"UCR_0_{current_stop:02d}"),
            "current_status": new_status,
            "congestion_level": progression.get("congestion_level", "RUNNING_SMOOTHLY"),
        })

        print(f"  ✓ Updated progression for {vehicle_id}: Stop {current_stop}, {new_status}")


def simulate_continuous_updates(interval: int = 5, max_iterations: int = None) -> None:
    """
    Simulate continuous position updates to Redis.

    Args:
        interval: Seconds between updates
        max_iterations: Maximum number of update cycles (None for infinite)
    """
    r = get_redis()

    print(f"\n{'=' * 80}")
    print(f"Simulating Continuous Position Updates")
    print(f"{'=' * 80}")
    print(f"Update interval: {interval} seconds")
    print(f"Max iterations: {max_iterations if max_iterations else 'Infinite'}")
    print(f"Press Ctrl+C to stop\n")

    iteration = 0

    try:
        while True:
            if max_iterations and iteration >= max_iterations:
                break

            iteration += 1
            print(f"\n[Iteration {iteration}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'-' * 80}")

            # Get all in-progress runs
            runs_in_progress = r.smembers("runs:in_progress")

            if not runs_in_progress:
                print("⚠️  No runs in progress! Run: python scripts/redis_seed_data.py")
                break

            for run_id in runs_in_progress:
                run = r.hgetall(run_id)
                vehicle_id = run.get("vehicle")

                if not vehicle_id:
                    continue

                # Update position
                simulate_position_update(run_id, vehicle_id)

                # Occasionally update progression
                if random.random() > 0.5:  # 50% chance
                    simulate_progression_update(vehicle_id)

            print(f"{'-' * 80}")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nStopping simulation...")
        print(f"Completed {iteration} update cycles")


def test_task_directly(task_name: str) -> None:
    """
    Test a publisher task by importing and calling it directly.
    This bypasses Celery and runs the task synchronously.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing {task_name} Task Directly")
    print(f"{'=' * 80}\n")

    # Add publisher to Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "publisher"))

    try:
        from publisher import build_vehicle_positions, build_trip_updates

        if task_name == "vp":
            result = build_vehicle_positions()
        elif task_name == "tu":
            result = build_trip_updates()
        else:
            print(f"Unknown task: {task_name}")
            return

        print(f"\n✓ Task completed: {result}")

        # Show output files
        if task_name == "vp":
            json_file = "feed/files/vehicle_positions.json"
            pb_file = "feed/files/vehicle_positions.pb"
        else:
            json_file = "feed/files/trip_updates.json"
            pb_file = "feed/files/trip_updates.pb"

        if os.path.exists(json_file):
            with open(json_file, "r") as f:
                data = json.load(f)
            print(f"\n✓ JSON file created: {json_file}")
            print(f"  - Entities: {len(data.get('entity', []))}")
            print(f"  - Timestamp: {data.get('header', {}).get('timestamp')}")

            # Show sample entity
            if data.get("entity"):
                print(f"\nSample entity:")
                print(json.dumps(data["entity"][0], indent=2)[:500] + "...")

        if os.path.exists(pb_file):
            file_size = os.path.getsize(pb_file)
            print(f"\n✓ Protobuf file created: {pb_file} ({file_size} bytes)")

    except ImportError as e:
        print(f"\n⚠️  Cannot import publisher module: {e}")
        print("\nMake sure the publisher container is running or dependencies are installed:")
        print("  cd publisher && uv pip install -r requirements.txt")
    except Exception as e:
        print(f"\n⚠️  Error running task: {e}")
        import traceback
        traceback.print_exc()


def test_task_via_celery(task_name: str) -> None:
    """
    Test a publisher task by calling it via Celery.
    Requires the publisher worker to be running.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing {task_name} Task via Celery")
    print(f"{'=' * 80}\n")

    print("⚠️  This requires the publisher worker to be running:")
    print("  docker compose -f compose.dev.yml up publisher")
    print("\nSending task to Celery...")

    try:
        from celery import Celery

        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_pass = os.getenv("RABBITMQ_PASS", "guest")
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")

        broker_url = f"amqp://{rabbitmq_user}:{rabbitmq_pass}@{rabbitmq_host}:{rabbitmq_port}/"

        app = Celery(broker=broker_url)

        if task_name == "vp":
            task = app.send_task("publisher.build_vehicle_positions")
        elif task_name == "tu":
            task = app.send_task("publisher.build_trip_updates")
        else:
            print(f"Unknown task: {task_name}")
            return

        print(f"✓ Task sent: {task.id}")
        print(f"Waiting for result (timeout: 30s)...")

        result = task.get(timeout=30)
        print(f"\n✓ Task completed: {result}")

    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        print("\nMake sure:")
        print("  1. RabbitMQ is running: docker compose -f compose.dev.yml up message-broker")
        print("  2. Publisher worker is running: docker compose -f compose.dev.yml up publisher")


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description="Test GTFS-RT publisher tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test VehiclePosition builder directly
  python scripts/test_publisher_tasks.py --task vp

  # Test TripUpdate builder directly
  python scripts/test_publisher_tasks.py --task tu

  # Test both tasks
  python scripts/test_publisher_tasks.py --task both

  # Simulate continuous updates every 5 seconds
  python scripts/test_publisher_tasks.py --simulate --interval 5

  # Simulate 10 updates then stop
  python scripts/test_publisher_tasks.py --simulate --max-iterations 10
        """,
    )

    parser.add_argument(
        "--task",
        choices=["vp", "tu", "both"],
        help="Task to test: 'vp' for VehiclePositions, 'tu' for TripUpdates, 'both' for both",
    )

    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Simulate continuous position updates to Redis",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in seconds between simulated updates (default: 5)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Maximum number of update cycles (default: infinite)",
    )

    parser.add_argument(
        "--celery",
        action="store_true",
        help="Test task via Celery instead of directly (requires worker running)",
    )

    args = parser.parse_args()

    # Check Redis connection
    if not check_redis_connection():
        sys.exit(1)

    # Check Redis data
    has_data = check_redis_data()

    if not has_data and not args.simulate:
        print("\n⚠️  No data found in Redis!")
        print("Please run: python scripts/redis_seed_data.py")
        sys.exit(1)

    # Simulate updates mode
    if args.simulate:
        simulate_continuous_updates(
            interval=args.interval,
            max_iterations=args.max_iterations
        )
        return

    # Test task mode
    if args.task:
        if args.task == "both":
            tasks = ["vp", "tu"]
        else:
            tasks = [args.task]

        for task in tasks:
            if args.celery:
                test_task_via_celery(task)
            else:
                test_task_directly(task)

            if len(tasks) > 1:
                print("\n" + "=" * 80 + "\n")
                time.sleep(1)
    else:
        print("\n⚠️  Please specify --task or --simulate")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
