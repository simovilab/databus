"""Server-side stop-status computation (seam / placeholder implementation).

This module provides a single pure function :func:`compute_stop_status` that
derives a ``vehicle_stop_status`` contract dict from the current run hash and
the vehicle's latest position hash.

**Current implementation: seam / placeholder body**

The body is intentionally minimal — it defaults ``current_status`` to
``IN_TRANSIT_TO`` and carries forward ``current_stop_sequence`` / ``stop_id``
from ``prev_state`` as a monotonic floor so values do not regress once a real
producer has set them.  No map-matching is performed here.

The function signature is **stable** — the future map-matching implementation
swaps only the body.
``run_hash`` is accepted now (currently unused) because the real implementation
needs ``shape_id`` / ``trip_id`` to look up the run's GTFS shape polyline.

# TODO(map-matching port):
#   Real algorithm:
#   1. Project the observed GPS point (position_hash latitude/longitude) onto
#      the run's shape polyline (identified via run_hash["shape_id"]).
#   2. Find the nearest stop along the polyline within STOP_RADIUS_M.
#   3. Apply radius rules:
#      - distance <= STOP_RADIUS_M and vehicle is stationary → STOPPED_AT
#      - distance <= INCOMING_AT_RADIUS_M and approaching    → INCOMING_AT
#      - otherwise                                            → IN_TRANSIT_TO
#   4. Enforce monotonic sequence: current_stop_sequence must never decrease
#      from prev_state["current_stop_sequence"] (unless the run restarts).
#   5. Resolve stop_id from the GTFS stops table for the selected sequence.
#   The port swaps only this body; callers and tests of the contract dict shape
#   are unaffected because the signature and return type are already locked.
"""

from __future__ import annotations

from runs.domain.telemetry import vehicle_stop_status


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
        ``r.hgetall``).  In the seam this is unused; the future map-matching
        implementation uses ``run_hash["shape_id"]`` / ``run_hash["trip_id"]``.
    position_hash:
        The typed position dict (as returned by ``position.from_redis``),
        containing at minimum ``latitude`` and ``longitude`` as floats.
    prev_state:
        Optional previous vehicle_stop_status dict (as returned by
        ``vehicle_stop_status.from_redis``).  When present, ``current_stop_sequence``
        and ``stop_id`` are carried forward as a monotonic floor so values do
        not regress between position updates.

    Returns
    -------
    dict
        A vehicle_stop_status contract dict with:
        - ``current_status`` (str, always present — required by the contract)
        - ``current_stop_sequence`` (int, optional — carried from prev_state)
        - ``stop_id`` (str, optional — carried from prev_state)

        The returned dict always passes ``vehicle_stop_status.validate_for_write``.

    # TODO(map-matching port): Replace this seam body with real
    # map-matching logic as described in the module docstring above.
    """
    result: dict = {
        vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
    }

    # Carry forward optional fields from prev_state as a monotonic floor.
    # Once a real producer has set sequence/stop_id, they should not vanish
    # between position updates (they will only change when the real algorithm
    # detects a stop transition).
    if prev_state is not None:
        seq = prev_state.get(vehicle_stop_status.CURRENT_STOP_SEQUENCE)
        if seq is not None:
            result[vehicle_stop_status.CURRENT_STOP_SEQUENCE] = seq

        stop_id = prev_state.get(vehicle_stop_status.STOP_ID)
        if stop_id is not None:
            result[vehicle_stop_status.STOP_ID] = stop_id

    return result
