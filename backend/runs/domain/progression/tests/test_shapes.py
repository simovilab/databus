"""Pure unit tests for shapes.py — no Django/Redis required.

Tests cover:
- build_polyline: cumulative distances, empty input, single point.
- build_stops: progress_m assigned, monotonic on straight shapes.
- assemble_geometry: returns valid ShapeGeometry.
- get_shape_geometry caching: second call doesn't invoke the loader again.
- invalidate_cache: clears cached entry so next call reloads.
"""

import pytest

from runs.domain.progression.geo import haversine_m
from runs.domain.progression.shapes import (
    ShapeGeometry,
    assemble_geometry,
    build_polyline,
    build_stops,
    get_shape_geometry,
    invalidate_cache,
    _validate_dists_m,
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


# ---------------------------------------------------------------------------
# build_polyline — shape_dist_traveled (dists_m) parameter (Commit 1)
# ---------------------------------------------------------------------------


class TestBuildPolylineWithDists:
    """Tests for the optional dists_m parameter introduced in Commit 1."""

    def _raw(self, n: int = 4) -> list[tuple[float, float, int]]:
        """n points along the prime meridian, ~111 km apart."""
        return [(float(i), 0.0, i) for i in range(n)]

    def test_uses_provided_dists_when_usable(self):
        """When dists_m is valid, cum_dist_m must come from dists_m, not haversine."""
        raw = self._raw(4)
        # Provide distances in a different but valid scale (still within 0.5-2.0× haversine).
        haversine_poly = build_polyline(raw)
        haversine_total = haversine_poly[-1][2]
        # Scale to ~0.9× haversine to keep within [0.5, 2.0].
        scale = 0.9
        dists_m = [haversine_total * scale * i / 3 for i in range(4)]
        result = build_polyline(raw, dists_m=dists_m)
        assert result[0][2] == pytest.approx(0.0, abs=1e-9)
        assert result[-1][2] == pytest.approx(dists_m[-1] - dists_m[0], rel=1e-9)

    def test_falls_back_when_dists_m_is_none(self):
        """None dists_m → haversine cumulative (same as no-arg call)."""
        raw = self._raw(3)
        result_no_arg = build_polyline(raw)
        result_none = build_polyline(raw, dists_m=None)
        for a, b in zip(result_no_arg, result_none):
            assert a[2] == pytest.approx(b[2], rel=1e-12)

    def test_falls_back_when_wrong_length(self):
        """dists_m with wrong length → haversine fallback."""
        raw = self._raw(4)
        haversine_poly = build_polyline(raw)
        result = build_polyline(raw, dists_m=[0.0, 1000.0])  # length 2, need 4
        for a, b in zip(haversine_poly, result):
            assert a[2] == pytest.approx(b[2], rel=1e-12)

    def test_falls_back_when_has_none_entry(self):
        """dists_m with a None entry → haversine fallback."""
        raw = self._raw(3)
        haversine_poly = build_polyline(raw)
        result = build_polyline(raw, dists_m=[0.0, None, 200_000.0])
        for a, b in zip(haversine_poly, result):
            assert a[2] == pytest.approx(b[2], rel=1e-12)

    def test_falls_back_when_non_monotonic(self):
        """dists_m that decreases → haversine fallback."""
        raw = self._raw(3)
        haversine_poly = build_polyline(raw)
        # Total is within band but the middle entry goes DOWN.
        total = haversine_poly[-1][2]
        bad = [0.0, total * 0.8, total * 0.6]  # not non-decreasing
        result = build_polyline(raw, dists_m=bad)
        for a, b in zip(haversine_poly, result):
            assert a[2] == pytest.approx(b[2], rel=1e-12)

    def test_falls_back_when_outside_sanity_band(self):
        """dists_m total vastly larger than haversine → haversine fallback."""
        raw = self._raw(3)
        haversine_poly = build_polyline(raw)
        total = haversine_poly[-1][2]
        # 3× the haversine total — outside the [0.5, 2.0] band.
        bad = [0.0, total * 1.5, total * 3.0]
        result = build_polyline(raw, dists_m=bad)
        for a, b in zip(haversine_poly, result):
            assert a[2] == pytest.approx(b[2], rel=1e-12)

    def test_first_point_always_zero(self):
        """Even when dists_m does not start at 0, the result is normalised."""
        raw = self._raw(3)
        haversine_poly = build_polyline(raw)
        total = haversine_poly[-1][2]
        # Start at an arbitrary offset (still within band relative to total).
        offset = 500.0
        dists_m = [offset, offset + total * 0.5, offset + total * 0.9]
        result = build_polyline(raw, dists_m=dists_m)
        assert result[0][2] == pytest.approx(0.0, abs=1e-9)

    def test_validate_dists_m_too_short(self):
        assert _validate_dists_m([0.0, 100.0], 3, 200_000.0) is False

    def test_validate_dists_m_passes(self):
        assert _validate_dists_m([0.0, 100_000.0, 200_000.0], 3, 200_000.0) is True

    def test_validate_dists_m_ratio_below_band(self):
        # dists total = 50 000, haversine = 200 000 → ratio = 0.25 < 0.5
        assert _validate_dists_m([0.0, 25_000.0, 50_000.0], 3, 200_000.0) is False

    def test_validate_dists_m_ratio_above_band(self):
        # dists total = 600 000, haversine = 200 000 → ratio = 3.0 > 2.0
        assert _validate_dists_m([0.0, 300_000.0, 600_000.0], 3, 200_000.0) is False


# ---------------------------------------------------------------------------
# assign_stops_monotonic + loop-back test (Commit 2)
# ---------------------------------------------------------------------------


class TestAssignStopsMonotonic:
    """Tests for the DP-based monotonic stop assignment introduced in Commit 2."""

    def test_empty_stops_returns_empty(self):
        from runs.domain.progression.shapes import assign_stops_monotonic

        poly = build_polyline([(0.0, 0.0, 0), (1.0, 0.0, 1), (2.0, 0.0, 2)])
        assert assign_stops_monotonic([], poly) == []

    def test_single_stop(self):
        from runs.domain.progression.shapes import assign_stops_monotonic

        poly = build_polyline([(0.0, 0.0, 0), (1.0, 0.0, 1)])
        stops = [{"stop_id": "A", "stop_sequence": 1, "lat": 0.0, "lon": 0.0}]
        result = assign_stops_monotonic(stops, poly)
        assert len(result) == 1
        assert result[0] == pytest.approx(0.0, abs=10.0)

    def test_monotonic_straight_shape(self):
        """Stops on a straight shape must get monotonically non-decreasing progress_m."""
        from runs.domain.progression.shapes import assign_stops_monotonic

        raw = [(float(i), 0.0, i) for i in range(5)]
        poly = build_polyline(raw)
        stops = [
            {"stop_id": f"S{i}", "stop_sequence": i, "lat": float(i), "lon": 0.0}
            for i in range(5)
        ]
        result = assign_stops_monotonic(stops, poly)
        assert len(result) == 5
        for i in range(1, len(result)):
            assert result[i] >= result[i - 1], f"Not monotonic at index {i}: {result}"

    def test_no_segments_edge_case(self):
        """Single-point polyline (no segments) — all stops get the same progress."""
        from runs.domain.progression.shapes import assign_stops_monotonic

        poly = build_polyline([(5.0, 10.0, 0)])
        stops = [
            {"stop_id": "A", "stop_sequence": 1, "lat": 5.0, "lon": 10.0},
            {"stop_id": "B", "stop_sequence": 2, "lat": 5.001, "lon": 10.001},
        ]
        result = assign_stops_monotonic(stops, poly)
        assert len(result) == 2
        assert result[0] == pytest.approx(0.0, abs=1e-9)
        assert result[1] == pytest.approx(0.0, abs=1e-9)

    def test_loop_back_shape_dp_assigns_correct_pass(self):
        """The key regression test: a shape that doubles back.

        Shape geometry (all on the equator, east-west):

            A(0, 0) ---> B(0, 1) ---> C(0, 2) ---> D(0, 1.5) ---> E(0, 0.5)

        The route goes east to lon=2, then turns around and heads west,
        ending near lon=0.5.  Crucially, stop S3 is at (0, 0.6), which is
        physically close to the EARLY part of the route (near A, lon 0-1) but
        is actually on the RETURN leg (segment D→E covers lon 1.5 → 0.5).

        Naive global nearest-segment projection snaps S3 to the first segment
        A→B (small progress_m ≈ distance from A to lon=0.6, ~66 700 m).

        DP monotonic assignment must keep S3 on the return leg, yielding a
        progress_m larger than S2's progress_m — approximately
          A→B + B→C + C→D + along D→E to lon=0.6.
        """
        from runs.domain.progression.shapes import assign_stops_monotonic
        from runs.domain.progression.geo import project_point_to_polyline

        # Shape points: east then looping back west.
        raw = [
            (0.0, 0.0, 0),  # A — start
            (0.0, 1.0, 1),  # B — 1° east
            (0.0, 2.0, 2),  # C — 2° east (turn-around)
            (0.0, 1.5, 3),  # D — heading back west
            (0.0, 0.5, 4),  # E — end (close to start side)
        ]
        poly = build_polyline(raw)

        # Three stops:
        # S1 — at A (start), expected small progress_m.
        # S2 — at C (turn-around), expected large progress_m.
        # S3 — at (0, 0.6), physically near A→B but must be on return leg D→E.
        stops = [
            {"stop_id": "S1", "stop_sequence": 1, "lat": 0.0, "lon": 0.0},
            {"stop_id": "S2", "stop_sequence": 2, "lat": 0.0, "lon": 2.0},
            {"stop_id": "S3", "stop_sequence": 3, "lat": 0.0, "lon": 0.6},
        ]

        dp_result = assign_stops_monotonic(stops, poly)

        # 1. Three values returned.
        assert len(dp_result) == 3

        # 2. Monotonically non-decreasing.
        for i in range(1, len(dp_result)):
            assert dp_result[i] >= dp_result[i - 1], (
                f"DP result not monotonic: {dp_result}"
            )

        # 3. S1 is near the start — progress_m should be small (< 50 km).
        assert dp_result[0] < 50_000.0, f"S1 progress too large: {dp_result[0]}"

        # 4. S2 is at the turn-around — progress_m ≈ haversine A→B→C ≈ 222 km.
        assert dp_result[1] > 150_000.0, f"S2 progress too small: {dp_result[1]}"

        # 5. S3 must be assigned the RETURN leg, not the outbound.
        #    Total outbound A→B→C ≈ 222 km; return D→E partial ≈ 55 km past C.
        #    So S3's progress_m must be > S2's progress_m (it's after S2).
        assert dp_result[2] > dp_result[1], (
            f"S3 ({dp_result[2]:.1f} m) should be > S2 ({dp_result[1]:.1f} m)"
        )

        # 6. Contrast: naive global nearest-segment gives a WRONG small value.
        naive_proj = project_point_to_polyline(0.0, 0.6, poly)
        naive_s3_progress = naive_proj["progress_m"]
        # Naive snaps to the first pass (A→B segment), so progress is small.
        assert naive_s3_progress < dp_result[2], (
            f"Expected naive ({naive_s3_progress:.1f} m) < DP ({dp_result[2]:.1f} m) "
            f"for the loop-back stop"
        )
