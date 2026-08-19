"""Real ETA stop-time-updates producer — impure/pure split.

Pure computation lives in :func:`compute_stop_time_updates`; all Redis I/O
lives in :func:`produce_stop_times`.  The split mirrors
``compute.py`` / ``producer.py`` in this package.

Called by ``realtime_engine/tasks.py`` after every successful position write
so that ``run:<run_id>:stop_time_updates`` is kept current for the GTFS-RT
builder.

Environment variables
---------------------
MODEL_REGISTRY_DIR
    Directory where the ETA model registry is stored.  Read by
    ``gtfs_eta`` itself from the environment — just set it before
    starting the worker.  Example: ``eta_models/``.
ETA_MAX_STOPS
    Maximum number of upcoming stops to predict.  Default: 3.
ETA_DEFAULT_UNCERTAINTY_S
    Uncertainty value (seconds) attached to every predicted arrival.
    Default: 120.
"""

import logging
import os
from datetime import datetime, timezone

import redis

from runs.domain.telemetry import keys, stop_time_updates, vehicle_stop_status
from runs.domain.progression.geo import project_point_to_polyline
from runs.domain.progression.shapes import ShapeGeometry, get_shape_geometry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level config
# ---------------------------------------------------------------------------

# Comfortably above the position-update interval (~1-5 s) so a stalled
# producer expires the projection instead of serving stale arrivals; run
# lifecycle still owns hard cleanup.
STOP_TIME_UPDATES_TTL_S = 60

# Maximum upcoming stops to pass to the estimator per position tick.
ETA_MAX_STOPS = int(os.getenv("ETA_MAX_STOPS", "3"))

# Uncertainty (seconds) attached to every prediction.  Passed through to the
# GTFS-RT feed; callers (e.g. apps) can use it for confidence UX.
ETA_DEFAULT_UNCERTAINTY_S = int(os.getenv("ETA_DEFAULT_UNCERTAINTY_S", "120"))

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


def compute_stop_time_updates(
    *,
    run_hash: dict,
    position: dict,
    stop_status: dict,
    geom: ShapeGeometry,
    max_stops: int = ETA_MAX_STOPS,
    default_uncertainty_s: int = ETA_DEFAULT_UNCERTAINTY_S,
) -> list[dict]:
    """Derive stop-time-update contract entries from run state and geometry.

    Pure: no Redis, no ORM, no side effects.  The ``geom`` is passed in so
    the caller can decide when to skip (and leave last-good in Redis to TTL).

    Parameters
    ----------
    run_hash:
        Raw Redis hash for ``run:<run_id>`` — all string values.
    position:
        Typed position dict as returned by ``position.from_redis``.
        Keys: ``latitude``, ``longitude``, optionally ``speed``, ``timestamp``.
    stop_status:
        Typed stop-status dict as returned by ``vehicle_stop_status.from_redis``.
    geom:
        Pre-loaded :class:`ShapeGeometry` for the trip's shape.
    max_stops:
        Maximum number of upcoming stops to predict.
    default_uncertainty_s:
        Uncertainty (seconds) attached to every predicted arrival.

    Returns
    -------
    list[dict]
        Zero or more contract dicts, each with exactly the five fields
        required by :func:`stop_time_updates.to_redis`:
        ``stop_sequence``, ``stop_id``, ``arrival_time``,
        ``departure_time``, ``uncertainty``.
        Empty list when no predictions are available or the estimator
        returns a top-level error.
    """
    # ------------------------------------------------------------------
    # 1. Determine current stop sequence and status
    # ------------------------------------------------------------------
    current_stop_sequence: int = stop_status.get(
        vehicle_stop_status.CURRENT_STOP_SEQUENCE, 0
    ) or 0
    status: str = stop_status.get(vehicle_stop_status.CURRENT_STATUS, "")

    # ------------------------------------------------------------------
    # 2. Project vehicle onto polyline → vehicle_progress_m
    # ------------------------------------------------------------------
    lat = position.get("latitude")
    lon = position.get("longitude")
    if lat is None or lon is None:
        return []

    proj = project_point_to_polyline(float(lat), float(lon), list(geom.polyline))
    vehicle_progress_m: float = proj["progress_m"]

    # ------------------------------------------------------------------
    # 3. Build upcoming_stops list (filter by sequence, compute distances)
    # ------------------------------------------------------------------
    upcoming_stops: list[dict] = []
    for stop in geom.stops:
        seq: int = stop["stop_sequence"]
        if status == "STOPPED_AT":
            if seq <= current_stop_sequence:
                continue
        else:
            if seq < current_stop_sequence:
                continue
        shape_dist = max(0.0, stop["progress_m"] - vehicle_progress_m)
        upcoming_stops.append(
            {
                "stop_id": stop["stop_id"],
                "stop_sequence": seq,
                "lat": stop["lat"],
                "lon": stop["lon"],
                "total_stop_sequence": len(geom.stops),
                "shape_distance_to_stop": shape_dist,
            }
        )

    if not upcoming_stops:
        return []

    # ------------------------------------------------------------------
    # 4. Build vehicle_position dict in estimator contract format
    # ------------------------------------------------------------------
    raw_ts = position.get("timestamp")
    if raw_ts is not None:
        ts_iso = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc).isoformat()
    else:
        ts_iso = datetime.now(tz=timezone.utc).isoformat()

    vehicle_position = {
        "vehicle_id": run_hash.get("vehicle", ""),
        "lat": float(lat),
        "lon": float(lon),
        "speed": float(position.get("speed", 0.0) or 0.0),
        "timestamp": ts_iso,
        "route": run_hash.get("route_id", ""),
    }

    # ------------------------------------------------------------------
    # 5. Build ShapePolyline for the estimator (lazy import → clean startup)
    # ------------------------------------------------------------------
    from gtfs_eta.feature_engineering.spatial import ShapePolyline  # noqa: PLC0415

    shape = ShapePolyline([(pt[0], pt[1]) for pt in geom.polyline])

    # ------------------------------------------------------------------
    # 6. Call estimator (lazy import keeps Django startup clean).
    # We import the *module* and call via attribute so tests can patch
    # ``gtfs_eta.eta_service.estimator.estimate_stop_times`` reliably.
    # ------------------------------------------------------------------
    import gtfs_eta.eta_service.estimator as _estimator_mod  # noqa: PLC0415

    result = _estimator_mod.estimate_stop_times(
        vehicle_position,
        upcoming_stops,
        route_id=run_hash.get("route_id"),
        trip_id=run_hash.get("trip_id"),
        prefer_route_model=True,
        max_stops=max_stops,
        shape=shape,
    )

    # Top-level error or empty predictions → safe to return []
    if result.get("error") or not result.get("predictions"):
        if result.get("error"):
            logger.debug(
                "compute_stop_time_updates: estimator error: %s", result["error"]
            )
        return []

    # ------------------------------------------------------------------
    # 7. Output adapter: predictions → contract dicts
    # ------------------------------------------------------------------
    entries: list[dict] = []
    for pred in result["predictions"]:
        # Skip per-stop failures
        if pred.get("error"):
            logger.debug(
                "compute_stop_time_updates: per-stop error for seq=%s: %s",
                pred.get("stop_sequence"),
                pred["error"],
            )
            continue
        eta_ts_str: str | None = pred.get("eta_timestamp")
        if not eta_ts_str:
            continue
        try:
            # Handle trailing Z (Python < 3.11 fromisoformat doesn't accept it)
            if eta_ts_str.endswith("Z"):
                eta_ts_str = eta_ts_str[:-1] + "+00:00"
            eta_posix = int(datetime.fromisoformat(eta_ts_str).timestamp())
        except (ValueError, TypeError) as exc:
            logger.debug(
                "compute_stop_time_updates: bad eta_timestamp %r: %s", eta_ts_str, exc
            )
            continue

        entries.append(
            {
                stop_time_updates.STOP_SEQUENCE: int(pred["stop_sequence"]),
                stop_time_updates.STOP_ID: str(pred["stop_id"]),
                stop_time_updates.ARRIVAL_TIME: eta_posix,
                stop_time_updates.DEPARTURE_TIME: eta_posix,
                stop_time_updates.UNCERTAINTY: default_uncertainty_s,
            }
        )

    # ------------------------------------------------------------------
    # 8. Dedup by stop_sequence (keep first) + sort ascending
    # ------------------------------------------------------------------
    seen: set[int] = set()
    deduped: list[dict] = []
    for entry in entries:
        seq = entry[stop_time_updates.STOP_SEQUENCE]
        if seq not in seen:
            seen.add(seq)
            deduped.append(entry)

    deduped.sort(key=lambda e: e[stop_time_updates.STOP_SEQUENCE])
    return deduped


# ---------------------------------------------------------------------------
# Impure producer (Redis glue)
# ---------------------------------------------------------------------------


def produce_stop_times(run_id: str, vehicle_id: str) -> None:
    """Derive and write ``run:<run_id>:stop_time_updates`` from current run state.

    1. Reads the run hash; returns immediately if absent.
    2. Reads the position hash; returns without overwriting if no position.
    3. Reads the stop-status hash.
    4. Resolves shape geometry; returns without overwriting if unavailable
       (leaves last-good projection to TTL-expire naturally).
    5. Calls :func:`compute_stop_time_updates`; writes to Redis only when a
       non-empty list is returned (no-models case leaves last-good intact).

    Parameters
    ----------
    run_id:
        The active run id (string, as stored in ``vehicle:<id>:current_run``).
    vehicle_id:
        The vehicle id whose position was just updated.
    """
    # Step 1 — run hash
    run_hash = r.hgetall(keys.run_key(run_id))
    if not run_hash:
        return

    # Step 2 — position hash (required; exit without overwriting if absent)
    from runs.domain.telemetry import position as position_module  # noqa: PLC0415

    pos_raw = r.hgetall(keys.position_key(vehicle_id))
    if not pos_raw:
        return
    pos = position_module.from_redis(pos_raw)
    if pos.get("latitude") is None or pos.get("longitude") is None:
        return

    # Step 3 — stop-status hash (tolerate absence)
    stop_status_raw = r.hgetall(keys.stop_status_key(run_id))
    stop_status = vehicle_stop_status.from_redis(stop_status_raw) if stop_status_raw else {}

    # Step 4 — shape geometry (exit without overwriting if unavailable)
    shape_id = run_hash.get("shape_id", "")
    trip_id = run_hash.get("trip_id", "")
    if not shape_id or not trip_id:
        return
    geom = get_shape_geometry(shape_id, trip_id)
    if geom is None:
        return

    # Step 5 — compute and conditionally write
    entries = compute_stop_time_updates(
        run_hash=run_hash,
        position=pos,
        stop_status=stop_status,
        geom=geom,
        max_stops=ETA_MAX_STOPS,
        default_uncertainty_s=ETA_DEFAULT_UNCERTAINTY_S,
    )
    if not entries:
        # No predictions (no models trained, etc.) — leave last-good intact.
        return

    payload = stop_time_updates.to_redis(entries)
    r.set(keys.stop_time_updates_key(run_id), payload, ex=STOP_TIME_UPDATES_TTL_S)
