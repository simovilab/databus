"""Per-shape geometry: build, cache, and load GTFS shape+stop geometry.

Public surface
--------------
ShapeGeometry            – frozen dataclass; one per (shape_id, trip_id) pair.
build_polyline(...)      – pure: raw GTFS rows → cumulative polyline tuples.
build_stops(...)         – pure: stop rows + polyline → stops with progress_m.
assemble_geometry(...)   – pure: combine the two into a ShapeGeometry.
load_shape_geometry(...) – ORM loader (Django imported inside the function).
get_shape_geometry(...)  – cached wrapper; returns None when data unavailable.
invalidate_cache()       – clear the module-level cache (call after GTFS import).

Cache notes
-----------
The cache is a plain module-level dict keyed by ``(feed_id, shape_id, trip_id)``.
``invalidate_cache()`` must be wired to the GTFS feed import hook externally
(the hook registration is out of scope for this module — see the import pipeline).

The ETA/look-ahead step can slice ``geometry.stops`` to only upcoming stops
(``stop_sequence >= current_stop_sequence``); the list is ordered by sequence.
"""

from __future__ import annotations

from dataclasses import dataclass

from runs.domain.progression.geo import haversine_m, project_point_to_polyline


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShapeGeometry:
    """Immutable, hashable geometry bundle for a (shape_id, trip_id) pair.

    Attributes
    ----------
    shape_id:
        GTFS shape_id string.
    trip_id:
        GTFS trip_id string (used to look up StopTimes).
    polyline:
        Ordered ``(lat, lon, cum_dist_m)`` tuples from shape start to end.
        First point always has ``cum_dist_m = 0.0``.
    stops:
        Ordered stop dicts, one per stop-time row, sorted by ``stop_sequence``.
        Each dict has keys:
            ``stop_id``       (str)
            ``stop_sequence`` (int)
            ``lat``           (float)
            ``lon``           (float)
            ``progress_m``    (float) — stop projected onto the polyline.
    """

    shape_id: str
    trip_id: str
    polyline: tuple[tuple[float, float, float], ...]
    stops: tuple[dict, ...]


# ---------------------------------------------------------------------------
# Pure builders
# ---------------------------------------------------------------------------


def build_polyline(
    points: list[tuple[float, float, int]],
) -> list[tuple[float, float, float]]:
    """Convert raw GTFS shape rows to a cumulative-distance polyline.

    Parameters
    ----------
    points:
        List of ``(lat, lon, shape_pt_sequence)`` tuples, pre-sorted by
        ``shape_pt_sequence`` ascending (the caller is responsible for ordering).

    Returns
    -------
    list of ``(lat, lon, cum_dist_m)`` tuples.  First point has
    ``cum_dist_m = 0.0``; subsequent points add the haversine distance from
    the previous point.
    """
    if not points:
        return []

    result: list[tuple[float, float, float]] = []
    cum = 0.0
    prev_lat: float | None = None
    prev_lon: float | None = None

    for lat, lon, _seq in points:
        if prev_lat is None:
            cum = 0.0
        else:
            cum += haversine_m(prev_lat, prev_lon, lat, lon)
        result.append((lat, lon, cum))
        prev_lat, prev_lon = lat, lon

    return result


def build_stops(
    stop_rows: list[dict],
    polyline: list[tuple[float, float, float]],
) -> list[dict]:
    """Project each stop onto the polyline and return enriched stop dicts.

    Parameters
    ----------
    stop_rows:
        List of dicts, each with keys ``stop_id`` (str), ``stop_sequence``
        (int), ``lat`` (float), ``lon`` (float).
    polyline:
        Cumulative polyline as returned by ``build_polyline``.

    Returns
    -------
    List of dicts (same order as input) with the additional key
    ``progress_m`` (float).
    """
    result = []
    for row in stop_rows:
        proj = project_point_to_polyline(row["lat"], row["lon"], polyline)
        result.append(
            {
                "stop_id": row["stop_id"],
                "stop_sequence": row["stop_sequence"],
                "lat": row["lat"],
                "lon": row["lon"],
                "progress_m": proj["progress_m"],
            }
        )
    return result


def assemble_geometry(
    shape_id: str,
    trip_id: str,
    shape_points: list[tuple[float, float, int]],
    stop_rows: list[dict],
) -> ShapeGeometry:
    """Assemble a ShapeGeometry from raw GTFS rows.

    Parameters
    ----------
    shape_id:
        GTFS shape_id.
    trip_id:
        GTFS trip_id.
    shape_points:
        ``(lat, lon, shape_pt_sequence)`` tuples ordered by sequence ascending.
    stop_rows:
        List of dicts ``{stop_id, stop_sequence, lat, lon}`` ordered by
        ``stop_sequence`` ascending.

    Returns
    -------
    ShapeGeometry (frozen, hashable).
    """
    polyline = build_polyline(shape_points)
    stops = build_stops(stop_rows, polyline)
    return ShapeGeometry(
        shape_id=shape_id,
        trip_id=trip_id,
        polyline=tuple(polyline),
        stops=tuple(stops),
    )


# ---------------------------------------------------------------------------
# ORM loader (Django imported inside function)
# ---------------------------------------------------------------------------


def load_shape_geometry(
    shape_id: str,
    trip_id: str,
    *,
    feed=None,
) -> ShapeGeometry | None:
    """Load shape + stop geometry from the database and assemble it.

    Django models are imported inside this function so that the module is
    safe to import in plain-pytest without a configured Django app (mirrors
    the pattern used in ``runs/domain/lifecycle/guards.py``).

    Parameters
    ----------
    shape_id:
        GTFS shape_id to look up in the Shape table.
    trip_id:
        GTFS trip_id to look up stop times.
    feed:
        Optional Feed ORM instance.  When ``None``, the current feed is
        resolved via ``Feed.objects.filter(is_current=True).first()``.

    Returns
    -------
    ``ShapeGeometry`` on success, ``None`` if:
      - no current GTFS feed exists, or
      - the shape_id has no points in the Shape table, or
      - the trip_id has no stop-time rows.
    """
    from feed.models import Feed, Shape, StopTime, Stop  # noqa: PLC0415

    if feed is None:
        feed = Feed.objects.filter(is_current=True).first()
        if feed is None:
            return None

    # ---- Shape points -------------------------------------------------------
    shape_qs = (
        Shape.objects.filter(feed=feed, shape_id=shape_id)
        .order_by("shape_pt_sequence")
        .values_list("shape_pt_lat", "shape_pt_lon", "shape_pt_sequence")
    )
    shape_points = [
        (float(lat), float(lon), int(seq))
        for lat, lon, seq in shape_qs
    ]
    if not shape_points:
        return None

    # ---- Stop-time rows for the trip ----------------------------------------
    stop_time_qs = (
        StopTime.objects.filter(feed=feed, trip_id=trip_id)
        .order_by("stop_sequence")
        .values_list("stop_id", "stop_sequence")
    )
    st_rows = list(stop_time_qs)
    if not st_rows:
        return None

    stop_ids = [sid for sid, _seq in st_rows]
    stop_coord_map = {
        row["stop_id"]: (float(row["stop_lat"]), float(row["stop_lon"]))
        for row in Stop.objects.filter(feed=feed, stop_id__in=stop_ids).values(
            "stop_id", "stop_lat", "stop_lon"
        )
    }

    stop_rows = []
    for sid, seq in st_rows:
        coords = stop_coord_map.get(sid)
        if coords is None:
            # Skip stops whose coordinates are not in the feed.
            continue
        stop_rows.append(
            {
                "stop_id": sid,
                "stop_sequence": int(seq),
                "lat": coords[0],
                "lon": coords[1],
            }
        )

    if not stop_rows:
        return None

    return assemble_geometry(shape_id, trip_id, shape_points, stop_rows)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_CACHE: dict[tuple, ShapeGeometry] = {}


def get_shape_geometry(
    shape_id: str,
    trip_id: str,
    *,
    feed=None,
) -> ShapeGeometry | None:
    """Return a cached ShapeGeometry, loading from the ORM on first access.

    The cache key is ``(feed_id, shape_id, trip_id)`` so that different feeds
    do not collide.  When ``feed`` is ``None`` the current feed is resolved
    inside ``load_shape_geometry`` and the resulting feed id is used as the
    key.

    Returns ``None`` when the shape or trip cannot be found (propagated from
    ``load_shape_geometry``).
    """
    # We need the feed_id to form the cache key.  Resolve lazily.
    resolved_feed = feed
    if resolved_feed is None:
        try:
            from feed.models import Feed  # noqa: PLC0415

            resolved_feed = Feed.objects.filter(is_current=True).first()
        except Exception:
            # No Django configured (e.g. plain-pytest).  Use a sentinel key.
            resolved_feed = None

    feed_id = getattr(resolved_feed, "pk", None)
    cache_key = (feed_id, shape_id, trip_id)

    if cache_key in _CACHE:
        return _CACHE[cache_key]

    geom = load_shape_geometry(shape_id, trip_id, feed=resolved_feed)
    if geom is not None:
        _CACHE[cache_key] = geom
    return geom


def invalidate_cache() -> None:
    """Clear the in-process ShapeGeometry cache.

    Call this after a GTFS feed import completes so that stale geometry is
    not served to in-flight requests.  The import pipeline hook that triggers
    this call is wired separately (outside this module).
    """
    _CACHE.clear()
