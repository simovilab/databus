"""Pure unit tests for geo.py — no Django/Redis required.

Tests cover:
- haversine_m: known distances (latitude degree ≈ 111 km, equator longitude,
  identical points, cardinal moves).
- project_point_to_polyline: on-vertex, perpendicular offset, before-start
  clamp, after-end clamp, degenerate polylines (empty, single point).
"""

from __future__ import annotations

import math

import pytest

from runs.domain.progression.geo import (
    haversine_m,
    project_point_to_polyline,
    project_point_to_segment,
)


# ---------------------------------------------------------------------------
# haversine_m
# ---------------------------------------------------------------------------


class TestHaversineM:
    def test_identical_points_zero(self):
        assert haversine_m(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_latitude_near_equator(self):
        # 1° of latitude ≈ 111 195 m (varies slightly; allow 0.5% tolerance).
        d = haversine_m(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111_195.0, rel=0.005)

    def test_one_degree_longitude_at_equator(self):
        # At equator, 1° lon ≈ same as 1° lat.
        d = haversine_m(0.0, 0.0, 0.0, 1.0)
        assert d == pytest.approx(111_195.0, rel=0.005)

    def test_one_degree_longitude_at_45_lat(self):
        # At 45° N, 1° lon ≈ 111 195 * cos(45°) ≈ 78 626 m.
        d = haversine_m(45.0, 0.0, 45.0, 1.0)
        expected = 111_195.0 * math.cos(math.radians(45.0))
        assert d == pytest.approx(expected, rel=0.01)

    def test_symmetric(self):
        assert haversine_m(51.5, -0.1, 48.8, 2.3) == pytest.approx(
            haversine_m(48.8, 2.3, 51.5, -0.1), rel=1e-10
        )

    def test_known_paris_london(self):
        # Paris (48.8566, 2.3522) to London (51.5074, -0.1278) ≈ 340 km.
        d = haversine_m(48.8566, 2.3522, 51.5074, -0.1278)
        assert 330_000 < d < 350_000

    def test_non_negative(self):
        assert haversine_m(10.0, 10.0, -10.0, -10.0) > 0


# ---------------------------------------------------------------------------
# project_point_to_polyline
# ---------------------------------------------------------------------------


def _make_straight_polyline(
    lat0: float, lon0: float, lat1: float, lon1: float, n: int = 5
) -> list[tuple[float, float, float]]:
    """Build a uniform n-point polyline between two WGS-84 coords."""
    from runs.domain.progression.shapes import build_polyline

    raw = [
        (lat0 + (lat1 - lat0) * i / (n - 1), lon0 + (lon1 - lon0) * i / (n - 1), i)
        for i in range(n)
    ]
    return build_polyline(raw)


class TestProjectPointToPolyline:
    def test_empty_polyline_returns_zeros(self):
        result = project_point_to_polyline(0.0, 0.0, [])
        assert result == {"progress_m": 0.0, "cross_track_m": 0.0, "segment_idx": 0}

    def test_single_point_polyline(self):
        poly = [(10.0, 20.0, 0.0)]
        result = project_point_to_polyline(10.0, 20.0, poly)
        assert result["cross_track_m"] == pytest.approx(0.0, abs=1e-3)
        assert result["progress_m"] == pytest.approx(0.0, abs=1e-3)
        assert result["segment_idx"] == 0

    def test_point_exactly_on_first_vertex(self):
        poly = _make_straight_polyline(0.0, 0.0, 1.0, 0.0, n=5)
        result = project_point_to_polyline(0.0, 0.0, poly)
        assert result["cross_track_m"] == pytest.approx(0.0, abs=1.0)  # ≤1 m
        assert result["progress_m"] == pytest.approx(0.0, abs=1.0)
        assert result["segment_idx"] == 0

    def test_point_exactly_on_last_vertex(self):
        poly = _make_straight_polyline(0.0, 0.0, 1.0, 0.0, n=5)
        total_m = poly[-1][2]
        result = project_point_to_polyline(1.0, 0.0, poly)
        assert result["cross_track_m"] == pytest.approx(0.0, abs=1.0)
        assert result["progress_m"] == pytest.approx(total_m, rel=0.005)
        assert result["segment_idx"] == len(poly) - 2

    def test_midpoint_on_segment(self):
        """A point at the geographic midpoint of the polyline should have
        cross_track ≈ 0 and progress ≈ total_m / 2."""
        poly = _make_straight_polyline(0.0, 0.0, 0.0, 1.0, n=5)  # east-west
        total_m = poly[-1][2]
        mid_lat, mid_lon = 0.0, 0.5
        result = project_point_to_polyline(mid_lat, mid_lon, poly)
        assert result["cross_track_m"] == pytest.approx(0.0, abs=5.0)  # ≤5 m
        assert result["progress_m"] == pytest.approx(total_m / 2.0, rel=0.01)

    def test_perpendicular_offset_gives_correct_cross_track(self):
        """A point 0.01° north of the midpoint of an east-west line should
        have cross_track ≈ haversine_m(0, 0, 0.01, 0) and progress ≈ mid."""
        poly = _make_straight_polyline(0.0, 0.0, 0.0, 1.0, n=5)
        total_m = poly[-1][2]
        offset_deg = 0.01
        expected_cross_m = haversine_m(0.0, 0.0, offset_deg, 0.0)
        result = project_point_to_polyline(offset_deg, 0.5, poly)
        assert result["cross_track_m"] == pytest.approx(expected_cross_m, rel=0.05)
        assert result["progress_m"] == pytest.approx(total_m / 2.0, rel=0.05)

    def test_point_before_start_clamps_to_zero(self):
        """A point 'behind' the polyline should project to the start (t=0 clamp)."""
        poly = _make_straight_polyline(0.0, 0.0, 0.0, 1.0, n=3)
        # Place point due west of the start — behind the east-pointing line.
        result = project_point_to_polyline(0.0, -0.5, poly)
        assert result["progress_m"] == pytest.approx(0.0, abs=10.0)
        assert result["segment_idx"] == 0

    def test_point_after_end_clamps_to_total(self):
        """A point 'beyond' the end should project to the last vertex."""
        poly = _make_straight_polyline(0.0, 0.0, 0.0, 1.0, n=3)
        total_m = poly[-1][2]
        result = project_point_to_polyline(0.0, 1.5, poly)
        assert result["progress_m"] == pytest.approx(total_m, rel=0.01)
        assert result["segment_idx"] == len(poly) - 2

    def test_segment_idx_matches_nearest_segment(self):
        """For a two-segment polyline with a right-angle bend, the nearest
        segment should be reported correctly."""
        # Two segments: (0,0)→(0,1) then (0,1)→(1,1).
        from runs.domain.progression.shapes import build_polyline

        raw = [(0.0, 0.0, 0), (0.0, 1.0, 1), (1.0, 1.0, 2)]
        poly = build_polyline(raw)
        # A point north of the midpoint of the second segment.
        result = project_point_to_polyline(0.5, 1.001, poly)
        assert result["segment_idx"] == 1

    def test_returns_dict_with_required_keys(self):
        poly = _make_straight_polyline(10.0, 10.0, 11.0, 11.0, n=3)
        result = project_point_to_polyline(10.5, 10.5, poly)
        assert set(result.keys()) == {"progress_m", "cross_track_m", "segment_idx"}
        assert isinstance(result["progress_m"], float)
        assert isinstance(result["cross_track_m"], float)
        assert isinstance(result["segment_idx"], int)

    def test_progress_non_negative(self):
        poly = _make_straight_polyline(0.0, 0.0, 1.0, 1.0, n=4)
        result = project_point_to_polyline(0.5, 0.5, poly)
        assert result["progress_m"] >= 0.0
        assert result["cross_track_m"] >= 0.0


# ---------------------------------------------------------------------------
# project_point_to_segment (Commit 2)
# ---------------------------------------------------------------------------


class TestProjectPointToSegment:
    """Correctness tests for the per-segment projection primitive."""

    def _seg(self) -> tuple[tuple, tuple]:
        """A 1° E-W segment at the equator: (0,0) → (0,1)."""
        from runs.domain.progression.shapes import build_polyline

        poly = build_polyline([(0.0, 0.0, 0), (0.0, 1.0, 1)])
        return poly[0], poly[1]

    def test_point_on_line_gives_zero_cross_track(self):
        """A point exactly on the segment midpoint: cross_track ≈ 0."""
        seg_start, seg_end = self._seg()
        pm, ct = project_point_to_segment(0.0, 0.5, seg_start, seg_end)
        assert ct == pytest.approx(0.0, abs=2.0)

    def test_point_on_line_gives_correct_progress(self):
        """Midpoint on a 1° E-W segment: progress_m ≈ half the total length."""
        seg_start, seg_end = self._seg()
        total = seg_end[2]
        pm, ct = project_point_to_segment(0.0, 0.5, seg_start, seg_end)
        assert pm == pytest.approx(total / 2.0, rel=0.01)

    def test_perpendicular_offset_cross_track(self):
        """Point 0.01° north of midpoint: cross_track ≈ haversine of 0.01°."""
        seg_start, seg_end = self._seg()
        offset_deg = 0.01
        expected_ct = haversine_m(0.0, 0.0, offset_deg, 0.0)
        pm, ct = project_point_to_segment(offset_deg, 0.5, seg_start, seg_end)
        assert ct == pytest.approx(expected_ct, rel=0.05)

    def test_t_clamp_before_start(self):
        """Point 'behind' segment start: foot = seg_start, progress = cum0."""
        seg_start, seg_end = self._seg()
        pm, ct = project_point_to_segment(0.0, -0.5, seg_start, seg_end)
        assert pm == pytest.approx(seg_start[2], abs=1.0)

    def test_t_clamp_after_end(self):
        """Point 'beyond' segment end: foot = seg_end, progress ≈ cum_end."""
        seg_start, seg_end = self._seg()
        pm, ct = project_point_to_segment(0.0, 1.5, seg_start, seg_end)
        assert pm == pytest.approx(seg_end[2], rel=0.01)

    def test_returns_two_floats(self):
        seg_start, seg_end = self._seg()
        result = project_point_to_segment(0.0, 0.5, seg_start, seg_end)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_cross_track_non_negative(self):
        seg_start, seg_end = self._seg()
        _, ct = project_point_to_segment(0.001, 0.3, seg_start, seg_end)
        assert ct >= 0.0

    def test_degenerate_segment_uses_haversine(self):
        """Zero-length segment: cross_track = haversine distance to the point."""
        # Both endpoints at the same location.
        seg_start = (0.0, 0.0, 0.0)
        seg_end = (0.0, 0.0, 0.0)  # same → seg_len < 1e-9
        pm, ct = project_point_to_segment(0.0, 0.01, seg_start, seg_end)
        expected_ct = haversine_m(0.0, 0.0, 0.0, 0.01)
        assert ct == pytest.approx(expected_ct, rel=0.01)
        assert pm == pytest.approx(0.0, abs=1e-9)
