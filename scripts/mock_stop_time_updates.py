#!/usr/bin/env python
"""
Mock stop_time_updates builder for testing.
Generates fake stop time updates based on current progression.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


# Mock route configuration - maps route_id to list of stops
MOCK_ROUTE_STOPS = {
    "bUCR_L2": [
        {"stop_id": "UCR_0_01", "stop_sequence": 1},
        {"stop_id": "UCR_0_02", "stop_sequence": 2},
        {"stop_id": "UCR_0_03", "stop_sequence": 3},
        {"stop_id": "UCR_0_04", "stop_sequence": 4},
        {"stop_id": "UCR_0_05", "stop_sequence": 5},
        {"stop_id": "UCR_0_06", "stop_sequence": 6},
        {"stop_id": "UCR_0_07", "stop_sequence": 7},
        {"stop_id": "UCR_0_08", "stop_sequence": 8},
        {"stop_id": "UCR_0_09", "stop_sequence": 9},
        {"stop_id": "UCR_0_10", "stop_sequence": 10},
    ],
    "bUCR_L1": [
        {"stop_id": "UCR_0_01", "stop_sequence": 1},
        {"stop_id": "UCR_0_02", "stop_sequence": 2},
        {"stop_id": "UCR_0_03", "stop_sequence": 3},
        {"stop_id": "UCR_0_04", "stop_sequence": 4},
        {"stop_id": "UCR_0_05", "stop_sequence": 5},
        {"stop_id": "UCR_0_06", "stop_sequence": 6},
        {"stop_id": "UCR_0_07", "stop_sequence": 7},
        {"stop_id": "UCR_0_08", "stop_sequence": 8},
        {"stop_id": "UCR_0_09", "stop_sequence": 9},
        {"stop_id": "UCR_0_10", "stop_sequence": 10},
        {"stop_id": "UCR_0_11", "stop_sequence": 11},
        {"stop_id": "UCR_0_12", "stop_sequence": 12},
    ],
}

# Constants for time calculations
UNCERTAINTY_SECONDS = 120  # 2 minutes uncertainty
TIME_BETWEEN_STOPS_SECONDS = 180  # 3 minutes between stops
INITIAL_ETA_MINUTES = 2  # First stop ETA in 2 minutes


def build_stop_time_updates(
    run: Dict[str, str],
    position: Dict[str, str],
    progression: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Build mock stop time updates for a run based on current progression.

    Args:
        run: Hash data from run:{run_id} key containing route_id, trip_id, etc.
        position: Hash data from vehicle:{vehicle_id}:position key (not used but kept for API compatibility).
        progression: Hash data from vehicle:{vehicle_id}:progression key containing current_stop_sequence and current_status.

    Returns:
        List of stop time update dictionaries with eta_posix, stop_id, stop_sequence, and uncertainty.

    Logic:
        - If current_status = "IN_TRANSIT_TO" or "INCOMING_AT": Include current stop and all following stops
        - If current_status = "STOPPED_AT": Skip current stop, include all following stops
        - Generate ETAs with 3-minute intervals between stops
    """
    route_id = run.get("route_id")

    if not route_id or route_id not in MOCK_ROUTE_STOPS:
        print(f"Warning: No mock stops configured for route {route_id}")
        return []

    if not progression:
        print("Warning: No progression data available")
        return []

    current_stop_sequence = int(progression.get("current_stop_sequence", 1))
    current_status = progression.get("current_status", "IN_TRANSIT_TO")

    # Get all stops for this route
    all_stops = MOCK_ROUTE_STOPS[route_id]

    # Determine starting stop based on current status
    if current_status == "STOPPED_AT":
        # Skip the current stop, start from next one
        starting_sequence = current_stop_sequence + 1
    else:
        # Include current stop (IN_TRANSIT_TO, INCOMING_AT, etc.)
        starting_sequence = current_stop_sequence

    # Calculate initial ETA
    now = datetime.now(timezone.utc)
    current_eta = now + timedelta(minutes=INITIAL_ETA_MINUTES)

    # Build stop time updates
    stop_time_updates = []

    for stop in all_stops:
        stop_sequence = stop["stop_sequence"]

        # Only include stops from starting_sequence onwards
        if stop_sequence < starting_sequence:
            continue

        stop_time_update = {
            "stop_sequence": stop_sequence,
            "stop_id": stop["stop_id"],
            "eta_posix": int(current_eta.timestamp()),
            "uncertainty": UNCERTAINTY_SECONDS,
        }

        stop_time_updates.append(stop_time_update)

        # Increment ETA for next stop
        current_eta += timedelta(seconds=TIME_BETWEEN_STOPS_SECONDS)

    return stop_time_updates


def print_stop_time_updates(updates: List[Dict[str, Any]]) -> None:
    """Pretty print stop time updates for debugging."""
    if not updates:
        print("No stop time updates")
        return

    print(f"\nGenerated {len(updates)} stop time updates:")
    print("-" * 80)
    for update in updates:
        eta_dt = datetime.fromtimestamp(update["eta_posix"], tz=timezone.utc)
        print(f"  Stop {update['stop_sequence']:2d} ({update['stop_id']}): "
              f"ETA {eta_dt.strftime('%H:%M:%S')} ± {update['uncertainty']}s")
    print("-" * 80)


if __name__ == "__main__":
    # Test the mock builder
    print("Testing mock stop_time_updates builder")
    print("=" * 80)

    # Test case 1: IN_TRANSIT_TO
    print("\nTest Case 1: IN_TRANSIT_TO stop 4")
    run1 = {"route_id": "bUCR_L2", "trip_id": "TRIP-EDU-01"}
    position1 = {"timestamp": str(int(datetime.now(timezone.utc).timestamp()))}
    progression1 = {"current_stop_sequence": "4", "current_status": "IN_TRANSIT_TO"}

    updates1 = build_stop_time_updates(run1, position1, progression1)
    print_stop_time_updates(updates1)

    # Test case 2: STOPPED_AT
    print("\nTest Case 2: STOPPED_AT stop 6")
    progression2 = {"current_stop_sequence": "6", "current_status": "STOPPED_AT"}

    updates2 = build_stop_time_updates(run1, position1, progression2)
    print_stop_time_updates(updates2)

    # Test case 3: Different route
    print("\nTest Case 3: bUCR_L1 route, IN_TRANSIT_TO stop 8")
    run3 = {"route_id": "bUCR_L1", "trip_id": "TRIP-ART-11"}
    progression3 = {"current_stop_sequence": "8", "current_status": "IN_TRANSIT_TO"}

    updates3 = build_stop_time_updates(run3, position1, progression3)
    print_stop_time_updates(updates3)
