"""Pure GTFS-RT feed assembly helpers — no Django, no Channels, no Celery.

This module is the Django-free half of the schedule_engine feed pipeline.
It reads per-entity Redis hashes (written by the MQTT consumer and lifecycle
actions) via the telemetry contract ``from_redis`` helpers and assembles
GTFS-RT FeedMessage dicts.

The Celery tasks in ``tasks.py`` call these helpers for the assembly step,
then handle the I/O (file writes, channel-layer broadcast).

Import graph (one-directional):
    tasks.py → builders.py → runs.domain.telemetry.* + keys
    builders.py must NOT import tasks.py, Django, Channels, or Celery.
"""

from datetime import datetime

from runs.domain.telemetry import (
    congestion_level,
    keys,
    occupancy,
    position,
    trip,
    vehicle_stop_status,
)

from .fake_stop_times import build_stop_time_updates


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def get_current_timestamp() -> int:
    """Return the current time as a Unix epoch integer."""
    return int(datetime.now().timestamp())


def get_entity_id(vehicle_id: str) -> str:
    """Return the GTFS-RT entity id for a given vehicle id."""
    return vehicle_id


# ---------------------------------------------------------------------------
# Single-entity assemblers
# ---------------------------------------------------------------------------


def build_vehicle_position_entity(r, run_id: str) -> dict | None:
    """Assemble one GTFS-RT VehiclePosition entity dict from Redis.

    Reads the per-entity hashes (written by the MQTT consumer and lifecycle
    actions) via the telemetry contract ``from_redis`` helpers. Returns ``None``
    when all of the sensor/status hashes are empty (preserves the existing skip
    semantics).

    Parameters
    ----------
    r:
        A Redis client (or any fake with ``hgetall(key) -> dict``).
    run_id:
        The run identifier; used to look up ``run:<id>`` and all
        ``run:<id>:*`` hashes.

    Returns
    -------
    dict | None
        A GTFS-RT entity dict ready for ``json_format.ParseDict`` into
        ``gtfs_realtime_pb2.FeedMessage``, or ``None`` to skip this run.
    """
    run = r.hgetall(keys.run_key(run_id))
    if not run:
        return None
    vehicle_id = run.get("vehicle", "")
    if not vehicle_id:
        return None

    # Read per-entity hashes
    position_raw = r.hgetall(keys.position_key(vehicle_id))
    occupancy_raw = r.hgetall(keys.occupancy_key(vehicle_id))
    stop_status_raw = r.hgetall(keys.stop_status_key(run_id))
    meta = r.hgetall(keys.metadata_key(vehicle_id))

    # Skip when no live sensor/status data is present at all
    if not position_raw and not occupancy_raw and not stop_status_raw:
        return None

    entity: dict = {"id": vehicle_id, "vehicle": {}}
    v = entity["vehicle"]

    # --- trip descriptor ------------------------------------------------
    trip_hash = trip.from_redis(r.hgetall(keys.trip_key(run_id)))
    if not trip_hash:
        # Fall back to the flat run hash (carries the same trip fields)
        trip_hash = trip.from_redis(run)
    # Default schedule_relationship to SCHEDULED when absent
    if "schedule_relationship" not in trip_hash:
        trip_hash["schedule_relationship"] = "SCHEDULED"
    v["trip"] = trip_hash

    # --- vehicle descriptor (from metadata raw hash) --------------------
    v["vehicle"] = {
        "id": meta.get("id", vehicle_id),
        "label": meta.get("label", vehicle_id),
    }
    if meta.get("license_plate"):
        v["vehicle"]["license_plate"] = meta["license_plate"]
    if meta.get("wheelchair_accessible"):
        v["vehicle"]["wheelchair_accessible"] = meta["wheelchair_accessible"]

    # --- position + timestamp lift (CRITICAL: timestamp at VP level) ----
    pos = position.from_redis(position_raw)
    ts = pos.pop("timestamp", None)
    if pos:  # has at minimum latitude + longitude
        v["position"] = pos
    v["timestamp"] = ts if ts is not None else get_current_timestamp()

    # --- stop status (current_stop_sequence / stop_id / current_status) -
    v.update(vehicle_stop_status.from_redis(stop_status_raw))

    # --- occupancy: emit ONLY occupancy_status + occupancy_percentage ---
    # occupancy_count is NOT a field on the GTFS-RT VehiclePosition message;
    # emitting it would make ParseDict raise an unknown-field error.
    occ = occupancy.from_redis(occupancy_raw)
    if "occupancy_status" in occ:
        v["occupancy_status"] = occ["occupancy_status"]
    if "occupancy_percentage" in occ:
        v["occupancy_percentage"] = occ["occupancy_percentage"]

    # --- congestion level (deferred; present only when hash is set) -----
    cong = congestion_level.from_redis(r.hgetall(keys.congestion_key(run_id)))
    if "congestion_level" in cong:
        v["congestion_level"] = cong["congestion_level"]

    return entity


def build_trip_update_entity(r, run_id: str) -> dict | None:
    """Assemble one GTFS-RT TripUpdate entity dict from Redis.

    Returns ``None`` when neither position nor stop-status data are present
    (mirrors the current skip semantics that checked ``not position and not
    progression``).

    Parameters
    ----------
    r:
        A Redis client (or any fake with ``hgetall`` / ``smembers``).
    run_id:
        The run identifier.

    Returns
    -------
    dict | None
        A GTFS-RT entity dict, or ``None`` to skip this run.
    """
    run = r.hgetall(keys.run_key(run_id))
    if not run:
        return None
    vehicle_id = run.get("vehicle", "")
    if not vehicle_id:
        return None

    # Read per-entity hashes
    position_raw = r.hgetall(keys.position_key(vehicle_id))
    stop_status_raw = r.hgetall(keys.stop_status_key(run_id))
    meta = r.hgetall(keys.metadata_key(vehicle_id))

    # Mirror current skip semantics: skip when neither position nor stop status
    if not position_raw and not stop_status_raw:
        return None

    entity: dict = {"id": get_entity_id(vehicle_id), "trip_update": {}}
    tu = entity["trip_update"]

    # --- timestamp (lifted from position hash, same as VP) --------------
    pos = position.from_redis(position_raw)
    ts = pos.pop("timestamp", None)
    tu["timestamp"] = ts if ts is not None else get_current_timestamp()

    # --- trip descriptor ------------------------------------------------
    trip_hash = trip.from_redis(r.hgetall(keys.trip_key(run_id)))
    if not trip_hash:
        trip_hash = trip.from_redis(run)
    if "schedule_relationship" not in trip_hash:
        trip_hash["schedule_relationship"] = "SCHEDULED"
    tu["trip"] = trip_hash

    # --- vehicle descriptor (note: no wheelchair_accessible here — matches
    #     current build_trip_updates behaviour) ---------------------------
    tu["vehicle"] = {
        "id": meta.get("id", vehicle_id),
        "label": meta.get("label", vehicle_id),
    }
    if meta.get("license_plate"):
        tu["vehicle"]["license_plate"] = meta["license_plate"]

    # --- stop time updates ----------------------------------------------
    # Pass the raw stop_status hash as `progression=`; fake_stop_times reads
    # current_stop_sequence and current_status from it — which this hash provides.
    stop_time_updates = build_stop_time_updates(run=run, progression=stop_status_raw)
    tu["stop_time_update"] = []
    for update in stop_time_updates:
        tu["stop_time_update"].append(
            {
                "stop_sequence": update["stop_sequence"],
                "stop_id": update["stop_id"],
                "arrival": {
                    "time": update["eta_posix"],
                    "uncertainty": update["uncertainty"],
                },
                "departure": {
                    "time": update["eta_posix"],
                    "uncertainty": update["uncertainty"],
                },
            }
        )

    return entity


# ---------------------------------------------------------------------------
# Full FeedMessage assemblers
# ---------------------------------------------------------------------------


def build_vehicle_positions_feed(r) -> dict:
    """Build a complete GTFS-RT VehiclePositions FeedMessage dict.

    Iterates ``runs:in_progress``, assembles one entity per run via
    :func:`build_vehicle_position_entity`, and skips ``None`` results.

    Parameters
    ----------
    r:
        A Redis client (or fake) supporting ``smembers`` and ``hgetall``.

    Returns
    -------
    dict
        A FeedMessage dict with ``header`` and ``entity`` list, ready for
        ``json_format.ParseDict(feed_dict, gtfs_rt.FeedMessage())``.
    """
    feed: dict = {
        "header": {
            "gtfs_realtime_version": "2.0",
            "incrementality": "FULL_DATASET",
            "timestamp": get_current_timestamp(),
        },
        "entity": [],
    }

    for run_id in r.smembers("runs:in_progress"):
        entity = build_vehicle_position_entity(r, run_id)
        if entity is not None:
            feed["entity"].append(entity)

    return feed


def build_trip_updates_feed(r) -> dict:
    """Build a complete GTFS-RT TripUpdates FeedMessage dict.

    Iterates ``runs:in_progress``, assembles one entity per run via
    :func:`build_trip_update_entity`, and skips ``None`` results.

    Parameters
    ----------
    r:
        A Redis client (or fake) supporting ``smembers`` and ``hgetall``.

    Returns
    -------
    dict
        A FeedMessage dict with ``header`` and ``entity`` list.
    """
    feed: dict = {
        "header": {
            "gtfs_realtime_version": "2.0",
            "incrementality": "FULL_DATASET",
            "timestamp": get_current_timestamp(),
        },
        "entity": [],
    }

    for run_id in r.smembers("runs:in_progress"):
        entity = build_trip_update_entity(r, run_id)
        if entity is not None:
            feed["entity"].append(entity)

    return feed
