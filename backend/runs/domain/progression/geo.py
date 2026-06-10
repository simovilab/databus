"""Pure geometry primitives for map-matching — no I/O, stdlib math only.

Public functions:
    haversine_m                — great-circle distance in metres (ported from sim)
    project_point_to_segment   — project a GPS point onto a single polyline segment
    project_point_to_polyline  — project a GPS point onto a cumulative polyline
                                 (global search; used by compute.py for live vehicles)
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
# Per-segment primitive
# ---------------------------------------------------------------------------


def project_point_to_segment(
    lat: float,
    lon: float,
    seg_start: tuple[float, float, float],
    seg_end: tuple[float, float, float],
) -> tuple[float, float]:
    """Project a GPS point onto a single polyline segment.

    Uses the same local-equirectangular math as ``project_point_to_polyline``
    (centred on *seg_start*; t clamped to [0, 1]).

    Parameters
    ----------
    lat, lon:
        Observed WGS-84 position.
    seg_start, seg_end:
        ``(lat, lon, cum_dist_m)`` tuples as produced by ``build_polyline``.

    Returns
    -------
    ``(progress_m, cross_track_m)`` where

    * ``progress_m``    – ``cum_dist_m`` of *seg_start* + along-track distance
                          from *seg_start* to the foot of perpendicular.
    * ``cross_track_m`` – perpendicular distance from the point to the segment
                          (always >= 0).

    Degenerate segment (length < 1e-9 m): the foot is *seg_start*;
    ``cross_track_m`` is the haversine distance from the point to *seg_start*.
    """
    lat0, lon0, cum0 = seg_start
    lat1, lon1, cum1 = seg_end

    seg_len_m = cum1 - cum0
    if seg_len_m < 1e-9:
        d = haversine_m(lat, lon, lat0, lon0)
        return (cum0, d)

    cos_lat0 = math.cos(math.radians(lat0))

    dx_seg = _R * cos_lat0 * math.radians(lon1 - lon0)
    dy_seg = _R * math.radians(lat1 - lat0)

    dx_pt = _R * cos_lat0 * math.radians(lon - lon0)
    dy_pt = _R * math.radians(lat - lat0)

    seg_len_sq = dx_seg ** 2 + dy_seg ** 2
    t = (dx_pt * dx_seg + dy_pt * dy_seg) / seg_len_sq
    t = max(0.0, min(1.0, t))

    fx = dx_seg * t
    fy = dy_seg * t

    cross_m = math.sqrt((dx_pt - fx) ** 2 + (dy_pt - fy) ** 2)
    along_m = t * math.sqrt(seg_len_sq)
    progress_m = cum0 + along_m

    return (progress_m, cross_m)


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
        progress_m, cross_m = project_point_to_segment(
            lat, lon, polyline[i], polyline[i + 1]
        )
        if cross_m < best_cross_m:
            best_cross_m = cross_m
            best_progress_m = progress_m
            best_seg = i

    return {
        "progress_m": best_progress_m,
        "cross_track_m": best_cross_m,
        "segment_idx": best_seg,
    }
