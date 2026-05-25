#!/usr/bin/env python
"""
Redis Cleanup Script

This script removes stale vehicle data from Redis based on configurable age thresholds.
It uses the hybrid approach: publisher marks when feeds were built, and this script
handles the actual cleanup.

Usage:
    # Dry run (see what would be deleted)
    python scripts/cleanup_redis.py --dry-run

    # Clean data older than 3 minutes (default)
    python scripts/cleanup_redis.py

    # Clean data older than 5 minutes
    python scripts/cleanup_redis.py --max-age 300

    # Run in continuous mode (clean every N seconds)
    python scripts/cleanup_redis.py --continuous 60

    # Force clean all vehicle data
    python scripts/cleanup_redis.py --force-all
"""

from __future__ import annotations

import os
import sys
import time
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Set

import redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Default max age: 3 minutes
DEFAULT_MAX_AGE_SECONDS = 180


def get_redis() -> redis.Redis:
    """Get Redis client with decode_responses=True."""
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )


def get_current_timestamp() -> int:
    """Get current POSIX timestamp."""
    return int(datetime.now(timezone.utc).timestamp())


def get_data_age(timestamp: int) -> str:
    """
    Calculate how old the data is.

    Args:
        timestamp: POSIX timestamp

    Returns:
        Human-readable age string
    """
    now = get_current_timestamp()
    age_seconds = now - timestamp

    if age_seconds < 60:
        return f"{age_seconds}s"
    elif age_seconds < 3600:
        return f"{age_seconds // 60}m"
    else:
        hours = age_seconds // 3600
        minutes = (age_seconds % 3600) // 60
        return f"{hours}h{minutes}m"


def find_stale_vehicles(r: redis.Redis, max_age_seconds: int) -> Dict[str, int]:
    """
    Find vehicles with stale position data.

    Args:
        r: Redis client
        max_age_seconds: Maximum age threshold

    Returns:
        Dict of {vehicle_id: timestamp} for stale vehicles
    """
    stale_vehicles = {}
    now = get_current_timestamp()

    # Get all position keys
    position_keys = r.keys("vehicle:*:position")

    for key in position_keys:
        # Extract vehicle_id from key (format: vehicle:{id}:position)
        vehicle_id = key.split(":")[1]

        # Get position data
        position = r.hgetall(key)

        if position and position.get("timestamp"):
            timestamp = int(position["timestamp"])
            age = now - timestamp

            if age > max_age_seconds:
                stale_vehicles[vehicle_id] = timestamp

    return stale_vehicles


def delete_vehicle_data(r: redis.Redis, vehicle_id: str, dry_run: bool = False) -> int:
    """
    Delete all data for a vehicle.

    Args:
        r: Redis client
        vehicle_id: Vehicle identifier
        dry_run: If True, don't actually delete

    Returns:
        Number of keys deleted (or would be deleted)
    """
    # Keys to delete
    keys_to_delete = [
        f"vehicle:{vehicle_id}:metadata",
        f"vehicle:{vehicle_id}:position",
        f"vehicle:{vehicle_id}:progression",
        f"vehicle:{vehicle_id}:occupancy",
    ]

    deleted_count = 0

    for key in keys_to_delete:
        if r.exists(key):
            if not dry_run:
                r.delete(key)
            deleted_count += 1

    return deleted_count


def cleanup_stale_data(
    r: redis.Redis, max_age_seconds: int, dry_run: bool = False
) -> Dict[str, any]:
    """
    Clean up stale vehicle data.

    Args:
        r: Redis client
        max_age_seconds: Maximum age threshold
        dry_run: If True, don't actually delete

    Returns:
        Dict with cleanup statistics
    """
    # Find stale vehicles
    stale_vehicles = find_stale_vehicles(r, max_age_seconds)

    stats = {
        "stale_count": len(stale_vehicles),
        "keys_deleted": 0,
        "vehicles_cleaned": [],
    }

    if not stale_vehicles:
        return stats

    # Delete data for stale vehicles
    for vehicle_id, timestamp in stale_vehicles.items():
        age = get_data_age(timestamp)
        keys_deleted = delete_vehicle_data(r, vehicle_id, dry_run)

        stats["keys_deleted"] += keys_deleted
        stats["vehicles_cleaned"].append(
            {
                "vehicle_id": vehicle_id,
                "age": age,
                "keys_deleted": keys_deleted,
            }
        )

    return stats


def force_cleanup_all(r: redis.Redis, dry_run: bool = False) -> int:
    """
    Force cleanup of ALL vehicle data.

    Args:
        r: Redis client
        dry_run: If True, don't actually delete

    Returns:
        Number of keys deleted
    """
    deleted_count = 0

    # Get all vehicle-related keys
    patterns = [
        "vehicle:*:metadata",
        "vehicle:*:position",
        "vehicle:*:progression",
        "vehicle:*:occupancy",
    ]

    for pattern in patterns:
        keys = r.keys(pattern)
        for key in keys:
            if not dry_run:
                r.delete(key)
            deleted_count += 1

    return deleted_count


def print_cleanup_report(stats: Dict[str, any], dry_run: bool = False):
    """
    Print cleanup report.

    Args:
        stats: Cleanup statistics
        dry_run: Whether this was a dry run
    """
    mode = "DRY RUN - " if dry_run else ""

    print(f"\n{'=' * 80}")
    print(f"{mode}CLEANUP REPORT")
    print(f"{'=' * 80}\n")

    if stats["stale_count"] == 0:
        print("  No stale data found")
    else:
        print(f"  Stale vehicles found: {stats['stale_count']}")
        print(
            f"  Total keys {'would be deleted' if dry_run else 'deleted'}: {stats['keys_deleted']}\n"
        )

        print("  Details:")
        for vehicle in stats["vehicles_cleaned"]:
            print(
                f"    {vehicle['vehicle_id']}: {vehicle['age']} old ({vehicle['keys_deleted']} keys)"
            )

    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Redis cleanup for stale GTFS-RT vehicle data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (see what would be deleted)
  python scripts/cleanup_redis.py --dry-run

  # Clean data older than 3 minutes (default)
  python scripts/cleanup_redis.py

  # Clean data older than 5 minutes
  python scripts/cleanup_redis.py --max-age 300

  # Run continuously (clean every 60 seconds)
  python scripts/cleanup_redis.py --continuous 60

  # Force clean all vehicle data
  python scripts/cleanup_redis.py --force-all --dry-run
        """,
    )

    parser.add_argument(
        "--max-age",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
        metavar="SECONDS",
        help=f"Maximum age of data to keep in seconds (default: {DEFAULT_MAX_AGE_SECONDS})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    parser.add_argument(
        "--continuous",
        type=int,
        metavar="SECONDS",
        help="Run continuously, cleaning every N seconds",
    )

    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Force delete ALL vehicle data (use with caution)",
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

    # Force cleanup
    if args.force_all:
        print(f"\n{'⚠️  WARNING ⚠️ ' * 5}")
        print("This will delete ALL vehicle data from Redis!")
        if not args.dry_run:
            confirm = input("\nType 'yes' to confirm: ")
            if confirm.lower() != "yes":
                print("Aborted.")
                sys.exit(0)

        deleted = force_cleanup_all(r, args.dry_run)
        mode = "[DRY RUN] Would delete" if args.dry_run else "Deleted"
        print(f"\n{mode} {deleted} keys\n")
        sys.exit(0)

    # Continuous mode
    if args.continuous:
        print(f"\n{'=' * 80}")
        print(f"Redis Cleanup - Continuous Mode")
        print(f"{'=' * 80}")
        print(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        print(f"Max Age: {args.max_age}s ({args.max_age // 60}m)")
        print(f"Interval: {args.continuous}s")
        print(f"Dry Run: {args.dry_run}")
        print(f"{'=' * 80}\n")
        print("Press Ctrl+C to stop\n")

        cycle = 0

        try:
            while True:
                cycle += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"[Cycle {cycle}] {timestamp}")
                print(f"{'-' * 80}")

                stats = cleanup_stale_data(r, args.max_age, args.dry_run)

                mode = "[DRY RUN] Would delete" if args.dry_run else "Deleted"
                print(
                    f"  {mode} {stats['keys_deleted']} keys from {stats['stale_count']} vehicles"
                )
                print(f"{'-' * 80}\n")

                time.sleep(args.continuous)

        except KeyboardInterrupt:
            print("\n\nStopping cleanup...\n")
            sys.exit(0)
    else:
        # Single cleanup
        print(f"\nRedis Cleanup")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Max Age: {args.max_age}s ({args.max_age // 60}m)")
        print(f"Dry Run: {args.dry_run}")

        stats = cleanup_stale_data(r, args.max_age, args.dry_run)
        print_cleanup_report(stats, args.dry_run)


if __name__ == "__main__":
    main()
