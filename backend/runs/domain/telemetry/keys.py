"""Central Redis key templates for the GTFS-RT entity division.

No other module should hardcode these key strings. Import from here.

Ownership is visible in the namespace:
- Edge-sensed data  → ``vehicle:<id>:*``
- Server-computed   → ``run:<id>:*`` or ``runs:*``

This module imports nothing, keeping it safe to import from any layer
without pulling in Django or Redis.
"""


# ---------------------------------------------------------------------------
# Vehicle-keyed keys (edge / MQTT producers)
# ---------------------------------------------------------------------------


def position_key(vehicle_id: str) -> str:
    """Redis hash: GPS and motion data from the edge.

    Fields: latitude, longitude, bearing?, speed?, odometer?, timestamp?
    """
    return f"vehicle:{vehicle_id}:position"


def occupancy_key(vehicle_id: str) -> str:
    """Redis hash: Passenger load data from the edge.

    Fields: occupancy_percentage?, occupancy_count?, occupancy_status
    """
    return f"vehicle:{vehicle_id}:occupancy"


def metadata_key(vehicle_id: str) -> str:
    """Redis hash: Vehicle descriptor data (server-enriched on run start).

    Fields: id, label, license_plate?, wheelchair_accessible?
    """
    return f"vehicle:{vehicle_id}:metadata"


def current_run_key(vehicle_id: str) -> str:
    """Redis string: The run_id currently assigned to this vehicle.

    Written by lifecycle action; used by ingestion to route telemetry.
    """
    return f"vehicle:{vehicle_id}:current_run"


# ---------------------------------------------------------------------------
# Run-keyed keys (server producers)
# ---------------------------------------------------------------------------


def trip_key(run_id: str) -> str:
    """Redis hash: GTFS-RT TripDescriptor for the assigned trip.

    Fields: trip_id, route_id, direction_id?, schedule_relationship?,
            start_time?, start_date?

    This is a GTFS-RT-shaped projection of the trip subset from run:<id>.
    Written by the lifecycle action.
    """
    return f"run:{run_id}:trip"


def stop_status_key(run_id: str) -> str:
    """Redis hash: Current vehicle-stop relationship for the run.

    Fields: current_stop_sequence?, stop_id?, current_status
    Written by the server progression step.
    """
    return f"run:{run_id}:vehicle_stop_status"


def congestion_key(run_id: str) -> str:
    """Redis hash: Congestion level for the run (deferred; producer TBD).

    Fields: congestion_level
    """
    return f"run:{run_id}:congestion_level"


def run_key(run_id: str) -> str:
    """Redis hash: Full run assignment / lifecycle record.

    Contains: trip_id, route_id, direction_id, shape_id,
              schedule_relationship, start_time, start_date,
              vehicle, operator, run_lifecycle_state, …

    ``run:<id>:trip`` is the GTFS-RT-shaped projection of its trip subset.
    """
    return f"run:{run_id}"


def last_seen_key(run_id: str) -> str:
    """Redis string: ISO-8601 timestamp of the last telemetry received for this run.

    Updated by the MQTT consumer on every message to enable stale detection.
    """
    return f"runs:last_seen:{run_id}"


def stop_time_updates_key(run_id: str) -> str:
    """Redis string: JSON array of upcoming stop-time-update entries for the run.

    This is a Redis **string** key (not a hash) holding a JSON-encoded array — a
    materialized projection/cache written by the stop-times producer with a
    staleness TTL.  The GTFS-RT builder reads this key and treats a missing or
    empty value as "skip stop_time_update" (honest empty list in the feed).

    Each array entry has the shape::

        {
            "stop_sequence": int,
            "stop_id": str,
            "arrival_time": int,   # POSIX seconds
            "departure_time": int, # POSIX seconds (== arrival_time for now)
            "uncertainty": int,
        }

    Written with a staleness TTL so a stalled producer allows the projection to
    expire rather than serving stale arrivals.  Run lifecycle owns hard cleanup.
    """
    return f"run:{run_id}:stop_time_updates"
