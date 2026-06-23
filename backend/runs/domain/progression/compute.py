"""Server-side stop-status computation via real GPS→polyline map-matching.

Algorithm
---------
Given the current ``run_hash`` (which carries ``shape_id`` and ``trip_id``) and
the latest ``position_hash`` (typed GPS fix), the function:

1. Loads the cached GTFS shape geometry for the (shape_id, trip_id) pair via
   ``shapes.get_shape_geometry``.
2. Projects the observed GPS point onto the shape polyline to obtain
   ``point_progress_m`` — the along-track distance from the shape start.
3. Selects the *upcoming* stop: the stop whose ``progress_m`` is the smallest
   value >= ``point_progress_m`` (i.e. the next stop ahead).  If no stop is
   ahead of the vehicle the last stop is chosen.
4. Computes the great-circle distance from the observed point to the candidate
   stop and applies three-state radius rules:

   * ``distance <= STOP_RADIUS_M`` AND (speed unknown OR speed <=
     STATIONARY_SPEED_MPS) → ``STOPPED_AT``
   * ``distance <= INCOMING_AT_RADIUS_M`` AND vehicle is still approaching
     (``point_progress_m < stop.progress_m``) → ``INCOMING_AT``
   * otherwise → ``IN_TRANSIT_TO``

5. Enforces a monotonic sequence floor using ``prev_state``: if the new
   candidate's stop_sequence < prev sequence, the previous sequence/stop_id are
   kept (mirrors the sim debounce: only advance when stop_id changes).

The entire algorithm is wrapped in ``try/except Exception`` and falls back to
the original seam behaviour (``IN_TRANSIT_TO`` + carry-forward of prev_state)
on any exception, including ORM connection errors, missing GTFS data, or
unexpected position payloads.  The producer calls this on every position tick
and must never raise.

Signature and return contract are FROZEN — callers (``producer.py``), the
contract dict shape, and ``vehicle_stop_status.validate_for_write`` are unaffected.
"""

from runs.domain.telemetry import vehicle_stop_status
from runs.domain.progression import shapes
from runs.domain.progression.geo import haversine_m


# ---------------------------------------------------------------------------
# Tunable constants (comment explains intent for each)
# ---------------------------------------------------------------------------

# Vehicle is considered *at* a stop when within this radius.
STOP_RADIUS_M = 20.0

# Vehicle is *incoming* when within this radius and still approaching.
INCOMING_AT_RADIUS_M = 50.0

# Speed at or below this threshold (m/s) qualifies as stationary.
# 0.5 m/s ≈ 1.8 km/h — slow enough to be considered dwell.
STATIONARY_SPEED_MPS = 0.5


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def compute_stop_status(
    run_hash: dict,
    position_hash: dict,
    *,
    prev_state: dict | None = None,
) -> dict:
    """Derive a vehicle_stop_status contract dict from current run and position.

    Parameters
    ----------
    run_hash:
        The full ``run:<run_id>`` Redis hash (all strings, as returned by
        ``r.hgetall``).  Must contain ``shape_id`` and ``trip_id`` for real
        map-matching; falls back to seam behaviour otherwise.
    position_hash:
        The typed position dict (as returned by ``position.from_redis``),
        containing at minimum ``latitude`` and ``longitude`` as floats.
    prev_state:
        Optional previous vehicle_stop_status dict (as returned by
        ``vehicle_stop_status.from_redis``).  ``current_stop_sequence`` and
        ``stop_id`` are carried forward as a monotonic floor so values do not
        regress between position updates.

    Returns
    -------
    dict
        A vehicle_stop_status contract dict with:
        - ``current_status`` (str, always present — required by the contract)
        - ``current_stop_sequence`` (int, optional)
        - ``stop_id`` (str, optional)

        Always passes ``vehicle_stop_status.validate_for_write``.
        Never raises.
    """
    try:
        return _compute_with_map_matching(run_hash, position_hash, prev_state)
    except Exception:
        return _fallback(prev_state)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fallback(prev_state: dict | None) -> dict:
    """Seam / fallback: IN_TRANSIT_TO + carry-forward of prev_state fields."""
    result: dict = {
        vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
    }
    if prev_state is not None:
        seq = prev_state.get(vehicle_stop_status.CURRENT_STOP_SEQUENCE)
        if seq is not None:
            result[vehicle_stop_status.CURRENT_STOP_SEQUENCE] = seq
        stop_id = prev_state.get(vehicle_stop_status.STOP_ID)
        if stop_id is not None:
            result[vehicle_stop_status.STOP_ID] = stop_id
    return result


def _compute_with_map_matching(
    run_hash: dict,
    position_hash: dict,
    prev_state: dict | None,
) -> dict:
    """Core map-matching logic — may raise; callers wrap in try/except."""
    # Step 1: resolve shape / trip ids.
    shape_id = run_hash.get("shape_id")
    trip_id = run_hash.get("trip_id")
    if not shape_id or not trip_id:
        return _fallback(prev_state)

    # Step 2: load geometry (may be None if feed / shape not found).
    geom = shapes.get_shape_geometry(shape_id, trip_id)
    if geom is None:
        return _fallback(prev_state)

    # Step 3: observed coordinates.
    observed_lat = position_hash.get("latitude")
    observed_lon = position_hash.get("longitude")
    if observed_lat is None or observed_lon is None:
        return _fallback(prev_state)
    observed_lat = float(observed_lat)
    observed_lon = float(observed_lon)

    # Step 4: project observed point onto polyline.
    proj = shapes.project_point_to_polyline(
        observed_lat, observed_lon, list(geom.polyline)
    )
    point_progress_m: float = proj["progress_m"]

    # Step 5: choose the candidate (upcoming) stop.
    candidate = _pick_upcoming_stop(geom.stops, point_progress_m)
    if candidate is None:
        return _fallback(prev_state)

    # Step 6: distance + radius rules.
    dist_m = haversine_m(observed_lat, observed_lon, candidate["lat"], candidate["lon"])
    speed = position_hash.get("speed")
    if speed is not None:
        speed = float(speed)

    if dist_m <= STOP_RADIUS_M and (speed is None or speed <= STATIONARY_SPEED_MPS):
        status = "STOPPED_AT"
    elif dist_m <= INCOMING_AT_RADIUS_M and point_progress_m < candidate["progress_m"]:
        status = "INCOMING_AT"
    else:
        status = "IN_TRANSIT_TO"

    chosen_seq: int = candidate["stop_sequence"]
    chosen_stop_id: str = candidate["stop_id"]

    # Step 7: monotonic guard — never regress sequence.
    if prev_state is not None:
        prev_seq = prev_state.get(vehicle_stop_status.CURRENT_STOP_SEQUENCE)
        if prev_seq is not None:
            prev_seq = int(prev_seq)
            if chosen_seq < prev_seq:
                # New candidate is behind prev — hold position.
                chosen_seq = prev_seq
                chosen_stop_id = prev_state.get(
                    vehicle_stop_status.STOP_ID, chosen_stop_id
                )

    result: dict = {
        vehicle_stop_status.CURRENT_STATUS: status,
        vehicle_stop_status.CURRENT_STOP_SEQUENCE: chosen_seq,
        vehicle_stop_status.STOP_ID: chosen_stop_id,
    }
    return result


def _pick_upcoming_stop(
    stops: tuple[dict, ...],
    point_progress_m: float,
) -> dict | None:
    """Return the next stop ahead of ``point_progress_m``, or the last stop.

    Stops are expected to be ordered by stop_sequence (ascending).  The
    upcoming stop is the one with the smallest ``progress_m`` that is >=
    ``point_progress_m``.  If the vehicle has passed all stops, the last stop
    is returned.
    """
    if not stops:
        return None

    for stop in stops:
        if stop["progress_m"] >= point_progress_m:
            return stop

    # Vehicle has passed all stops — return the terminal stop.
    return stops[-1]
