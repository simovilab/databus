"""Pure unit tests for shapes.py — no Django/Redis required.

Tests cover:
- build_polyline: cumulative distances, empty input, single point.
- build_stops: progress_m assigned, monotonic on straight shapes.
- assemble_geometry: returns valid ShapeGeometry.
- get_shape_geometry caching: second call doesn't invoke the loader again.
- invalidate_cache: clears cached entry so next call reloads.
"""

from __future__ import annotations

import pytest

from runs.domain.progression.geo import haversine_m
from runs.domain.progression.shapes import (
    ShapeGeometry,
    assemble_geometry,
    build_polyline,
    build_stops,
    get_shape_geometry,
    invalidate_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _straight_shape_points(n: int = 5) -> list[tuple[float, float, int]]:
    """n points along the prime meridian from (0,0) to (n-1 deg, 0)."""
    return [(float(i), 0.0, i) for i in range(n)]


def _straight_stops(n: int = 3) -> list[dict]:
    """n stops distributed along the prime meridian."""
    return [
        {"stop_id": f"S{i}", "stop_sequence": i + 1, "lat": float(i), "lon": 0.0}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# build_polyline
# ---------------------------------------------------------------------------


class TestBuildPolyline:
    def test_empty_input(self):
        assert build_polyline([]) == []

    def test_single_point_cum_zero(self):
        result = build_polyline([(10.0, 20.0, 1)])
        assert len(result) == 1
        lat, lon, cum = result[0]
        assert lat == pytest.approx(10.0)
        assert lon == pytest.approx(20.0)
        assert cum == pytest.approx(0.0)

    def test_two_points_cumulative(self):
        raw = [(0.0, 0.0, 0), (1.0, 0.0, 1)]
        result = build_polyline(raw)
        assert result[0][2] == pytest.approx(0.0)
        expected_d = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert result[1][2] == pytest.approx(expected_d, rel=1e-9)

    def test_three_points_matches_manual_haversine(self):
        raw = [(0.0, 0.0, 0), (1.0, 0.0, 1), (2.0, 0.0, 2)]
        result = build_polyline(raw)
        d01 = haversine_m(0.0, 0.0, 1.0, 0.0)
        d12 = haversine_m(1.0, 0.0, 2.0, 0.0)
        assert result[0][2] == pytest.approx(0.0)
        assert result[1][2] == pytest.approx(d01, rel=1e-9)
        assert result[2][2] == pytest.approx(d01 + d12, rel=1e-9)

    def test_cumulative_is_monotonically_increasing(self):
        raw = _straight_shape_points(5)
        result = build_polyline(raw)
        cums = [r[2] for r in result]
        for i in range(1, len(cums)):
            assert cums[i] > cums[i - 1]

    def test_preserves_lat_lon(self):
        raw = [(51.5, -0.1, 0), (51.6, -0.1, 1)]
        result = build_polyline(raw)
        assert result[0][0] == pytest.approx(51.5)
        assert result[0][1] == pytest.approx(-0.1)
        assert result[1][0] == pytest.approx(51.6)


# ---------------------------------------------------------------------------
# build_stops
# ---------------------------------------------------------------------------


class TestBuildStops:
    def test_empty_input(self):
        poly = build_polyline(_straight_shape_points(3))
        assert build_stops([], poly) == []

    def test_single_stop_on_first_vertex(self):
        poly = build_polyline(_straight_shape_points(3))
        stops = [{"stop_id": "X", "stop_sequence": 1, "lat": 0.0, "lon": 0.0}]
        result = build_stops(stops, poly)
        assert len(result) == 1
        assert result[0]["progress_m"] == pytest.approx(0.0, abs=1.0)
        assert result[0]["stop_id"] == "X"
        assert result[0]["stop_sequence"] == 1

    def test_progress_m_present_for_all_stops(self):
        poly = build_polyline(_straight_shape_points(5))
        stops = _straight_stops(3)
        result = build_stops(stops, poly)
        assert all("progress_m" in s for s in result)

    def test_progress_m_monotonic_along_straight_shape(self):
        """Stops at equally-spaced latitudes along the prime meridian must
        have strictly increasing progress_m."""
        raw_pts = [(float(i), 0.0, i) for i in range(5)]
        poly = build_polyline(raw_pts)
        stop_rows = [
            {"stop_id": f"S{i}", "stop_sequence": i, "lat": float(i), "lon": 0.0}
            for i in range(5)
        ]
        result = build_stops(stop_rows, poly)
        progs = [r["progress_m"] for r in result]
        for i in range(1, len(progs)):
            assert progs[i] > progs[i - 1], (
                f"progress not monotonic at index {i}: {progs}"
            )

    def test_stop_matches_manual_projection(self):
        """A stop at the exact first vertex should project to progress ≈ 0."""
        poly = build_polyline([(0.0, 0.0, 0), (1.0, 0.0, 1)])
        stops = [{"stop_id": "A", "stop_sequence": 1, "lat": 0.0, "lon": 0.0}]
        result = build_stops(stops, poly)
        assert result[0]["progress_m"] == pytest.approx(0.0, abs=1.0)


# ---------------------------------------------------------------------------
# assemble_geometry
# ---------------------------------------------------------------------------


class TestAssembleGeometry:
    def test_returns_shape_geometry_instance(self):
        pts = _straight_shape_points(3)
        stops = _straight_stops(2)
        geom = assemble_geometry("shp-1", "trip-1", pts, stops)
        assert isinstance(geom, ShapeGeometry)

    def test_fields_populated(self):
        pts = _straight_shape_points(4)
        stops = _straight_stops(3)
        geom = assemble_geometry("shp-A", "trip-B", pts, stops)
        assert geom.shape_id == "shp-A"
        assert geom.trip_id == "trip-B"
        assert len(geom.polyline) == 4
        assert len(geom.stops) == 3

    def test_polyline_is_tuple_of_tuples(self):
        pts = _straight_shape_points(3)
        geom = assemble_geometry("s", "t", pts, [])
        assert isinstance(geom.polyline, tuple)
        for item in geom.polyline:
            assert isinstance(item, tuple)

    def test_stops_is_tuple_of_dicts(self):
        pts = _straight_shape_points(3)
        stops = _straight_stops(2)
        geom = assemble_geometry("s", "t", pts, stops)
        assert isinstance(geom.stops, tuple)
        for s in geom.stops:
            assert isinstance(s, dict)
            assert "progress_m" in s

    def test_hashable(self):
        pts = _straight_shape_points(2)
        geom = assemble_geometry("s", "t", pts, [])
        # Should not raise — frozen dataclass with tuples.
        h = hash(geom)
        assert isinstance(h, int)


# ---------------------------------------------------------------------------
# Caching behaviour (monkeypatched loader)
# ---------------------------------------------------------------------------


def _make_test_geom(shape_id: str = "shp", trip_id: str = "trp") -> ShapeGeometry:
    pts = _straight_shape_points(3)
    stops = _straight_stops(2)
    return assemble_geometry(shape_id, trip_id, pts, stops)


class TestCache:
    def setup_method(self):
        invalidate_cache()

    def test_get_shape_geometry_returns_none_when_loader_returns_none(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "runs.domain.progression.shapes.load_shape_geometry",
            lambda *a, **kw: None,
        )
        # Also patch the feed lookup inside get_shape_geometry so no ORM is hit.
        monkeypatch.setattr(
            "runs.domain.progression.shapes.Feed",
            None,
            raising=False,
        )
        result = get_shape_geometry("no-shape", "no-trip")
        assert result is None

    def test_get_shape_geometry_caches_on_second_call(self, monkeypatch):
        """Second call must NOT invoke load_shape_geometry again."""
        geom = _make_test_geom()
        call_count = {"n": 0}

        def fake_load(shape_id, trip_id, *, feed=None):
            call_count["n"] += 1
            return geom

        monkeypatch.setattr(
            "runs.domain.progression.shapes.load_shape_geometry", fake_load
        )
        # Prevent the ORM Feed lookup inside get_shape_geometry from running.
        import runs.domain.progression.shapes as _shapes_mod

        monkeypatch.setattr(_shapes_mod, "_CACHE", {})

        # Patch the internal Feed import to avoid Django hitting ORM.
        # We rely on the try/except in get_shape_geometry — when Feed cannot be
        # imported (no Django), feed_id=None is used as the cache key.
        r1 = get_shape_geometry("shp", "trp")
        r2 = get_shape_geometry("shp", "trp")

        assert r1 is geom
        assert r2 is geom
        # load_shape_geometry should only have been called once.
        assert call_count["n"] == 1

    def test_invalidate_cache_forces_reload(self, monkeypatch):
        geom1 = _make_test_geom("s1", "t1")
        geom2 = _make_test_geom("s2", "t2")
        calls = {"geoms": [geom1, geom2]}

        def fake_load(shape_id, trip_id, *, feed=None):
            return calls["geoms"].pop(0)

        monkeypatch.setattr(
            "runs.domain.progression.shapes.load_shape_geometry", fake_load
        )
        import runs.domain.progression.shapes as _shapes_mod

        monkeypatch.setattr(_shapes_mod, "_CACHE", {})

        r1 = get_shape_geometry("shp", "trp")
        invalidate_cache()
        r2 = get_shape_geometry("shp", "trp")

        # After invalidation, the loader was called a second time → different geom.
        assert r1 is geom1
        assert r2 is geom2

    def test_invalidate_cache_clears_all_entries(self, monkeypatch):
        import runs.domain.progression.shapes as _shapes_mod

        g = _make_test_geom()
        _shapes_mod._CACHE[(None, "shp", "trp")] = g
        assert len(_shapes_mod._CACHE) == 1
        invalidate_cache()
        assert len(_shapes_mod._CACHE) == 0
