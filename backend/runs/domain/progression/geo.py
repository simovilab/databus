"""Pure geometry primitives for map-matching — no I/O, stdlib math only.

Two public functions:
    haversine_m            — great-circle distance in metres (ported from sim)
    project_point_to_polyline — project a GPS point onto a cumulative polyline
"""

from __future__ import annotations

import math

# Earth radius used in the simulator (kinematics.py) — ported verbatim.
_R = 6_371_000.0


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points.

    Ported verbatim from simulator_app/domain/kinematics.py (R = 6_371_000 m).
    """
    r = _R
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Point-to-polyline projection
# ---------------------------------------------------------------------------


def project_point_to_polyline(
    lat: float,
    lon: float,
    polyline: list[tuple[float, float, float]],
) -> dict:
    """Project a GPS point onto a cumulative polyline.

    Parameters
    ----------
    lat, lon:
        Observed WGS-84 position.
    polyline:
        Ordered list of ``(lat, lon, cum_dist_m)`` tuples as produced by
        ``shapes.build_polyline``.  Must contain at least one point.

    Returns
    -------
    dict with keys:
        ``progress_m``    – distance along the polyline to the projected foot
                            (i.e. cum_dist_m of the segment start + along-track
                            distance to the foot).
        ``cross_track_m`` – perpendicular distance from the point to the nearest
                            segment (always >= 0).
        ``segment_idx``   – index of the segment (0 = first pair) whose foot is
                            nearest.  For a 1-point polyline, segment_idx = 0.

    Edge cases
    ----------
    * Empty polyline → returns ``{"progress_m": 0.0, "cross_track_m": 0.0,
      "segment_idx": 0}`` (defensive fallback).
    * 1-point polyline → the single point is the only candidate; cross_track is
      the haversine distance to that point; progress_m = cum_dist of that point
      (always 0.0 for the first point).
    * Parameter t outside [0, 1] is clamped → the foot is the nearer endpoint.
    """
    if not polyline:
        return {"progress_m": 0.0, "cross_track_m": 0.0, "segment_idx": 0}

    if len(polyline) == 1:
        only = polyline[0]
        d = haversine_m(lat, lon, only[0], only[1])
        return {"progress_m": only[2], "cross_track_m": d, "segment_idx": 0}

    best_cross_m = float("inf")
    best_progress_m = polyline[0][2]
    best_seg = 0

    for i in range(len(polyline) - 1):
        lat0, lon0, cum0 = polyline[i]
        lat1, lon1, cum1 = polyline[i + 1]

        seg_len_m = cum1 - cum0
        if seg_len_m < 1e-9:
            # Degenerate (duplicate) segment — treat as a single point.
            d = haversine_m(lat, lon, lat0, lon0)
            if d < best_cross_m:
                best_cross_m = d
                best_progress_m = cum0
                best_seg = i
            continue

        # Local equirectangular projection centred on segment start.
        # x = R * cos(lat0) * Δlon_rad  (easting, metres)
        # y = R * Δlat_rad              (northing, metres)
        cos_lat0 = math.cos(math.radians(lat0))

        # Segment vector in local metres.
        dx_seg = _R * cos_lat0 * math.radians(lon1 - lon0)
        dy_seg = _R * math.radians(lat1 - lat0)

        # Point vector relative to segment start, in local metres.
        dx_pt = _R * cos_lat0 * math.radians(lon - lon0)
        dy_pt = _R * math.radians(lat - lat0)

        # Scalar projection parameter t ∈ [0, 1].
        seg_len_sq = dx_seg ** 2 + dy_seg ** 2  # = seg_len_m² but more numerically clean
        t = (dx_pt * dx_seg + dy_pt * dy_seg) / seg_len_sq
        t = max(0.0, min(1.0, t))

        # Foot of perpendicular in local metres.
        fx = dx_seg * t
        fy = dy_seg * t

        # Perpendicular (cross-track) distance.
        cross_m = math.sqrt((dx_pt - fx) ** 2 + (dy_pt - fy) ** 2)

        # Along-track distance from segment start to foot.
        along_m = math.sqrt(fx ** 2 + fy ** 2)

        # Signed check: if t=0 the foot is at the start; dot product with the
        # point vector confirms along_m direction.  Since t is clamped we just
        # take along_m = t * seg_len_m to stay consistent with the parameter.
        along_m = t * math.sqrt(seg_len_sq)

        progress_m = cum0 + along_m

        if cross_m < best_cross_m:
            best_cross_m = cross_m
            best_progress_m = progress_m
            best_seg = i

    return {
        "progress_m": best_progress_m,
        "cross_track_m": best_cross_m,
        "segment_idx": best_seg,
    }
