"""Pure unit tests for compute_stop_status — no Django/Redis required.

Two test groups:

1. **Fallback / contract group** (tests 1-9, original):
   These use a ``_RUN_HASH`` that references real shape/trip ids, but since no
   Django ORM is configured in plain-pytest the ``get_shape_geometry`` call
   raises, which triggers the broad ``except Exception`` fallback inside
   ``compute_stop_status``.  The fallback reproduces the old seam behaviour:
   ``IN_TRANSIT_TO`` + carry-forward of ``prev_state``.  All original
   contract assertions hold unchanged.

2. **Real map-matching group** (new tests at the bottom):
   ``shapes.get_shape_geometry`` is monkeypatched to return a known straight-line
   ``ShapeGeometry`` with a small set of colinear stops.  Canned positions are fed
   in to assert the status sequence ``IN_TRANSIT_TO → INCOMING_AT → STOPPED_AT``
   and that ``current_stop_sequence`` never regresses on jittered GPS.
"""

import pytest

from runs.domain.progression.compute import (
    INCOMING_AT_RADIUS_M,
    STATIONARY_SPEED_MPS,
    STOP_RADIUS_M,
    compute_stop_status,
)
from runs.domain.progression.shapes import (
    ShapeGeometry,
    assemble_geometry,
    invalidate_cache,
)
from runs.domain.telemetry import vehicle_stop_status


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_POSITION_HASH = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "bearing": 90.0,
    "speed": 8.5,
    "timestamp": 1700000000,
}

_RUN_HASH = {
    "trip_id": "trip-1",
    "route_id": "route-1",
    "shape_id": "shape-1",
}


# ---------------------------------------------------------------------------
# Test 1 — Default seam: IN_TRANSIT_TO with no seq/stop_id when prev is None
# ---------------------------------------------------------------------------


def test_default_returns_in_transit_to_with_no_prev():
    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=None)

    assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert vehicle_stop_status.CURRENT_STOP_SEQUENCE not in result
    assert vehicle_stop_status.STOP_ID not in result


# ---------------------------------------------------------------------------
# Test 2 — prev_state with sequence and stop_id: both carried forward
# ---------------------------------------------------------------------------


def test_carries_forward_sequence_and_stop_id_from_prev_state():
    prev = {
        vehicle_stop_status.CURRENT_STOP_SEQUENCE: 5,
        vehicle_stop_status.STOP_ID: "STOP-42",
        vehicle_stop_status.CURRENT_STATUS: "STOPPED_AT",
    }

    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=prev)

    assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert result[vehicle_stop_status.CURRENT_STOP_SEQUENCE] == 5
    assert result[vehicle_stop_status.STOP_ID] == "STOP-42"


# ---------------------------------------------------------------------------
# Test 3 — prev_state with only stop_id (no sequence): only stop_id carried
# ---------------------------------------------------------------------------


def test_carries_forward_only_stop_id_when_no_sequence_in_prev():
    prev = {
        vehicle_stop_status.STOP_ID: "STOP-7",
        vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
    }

    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=prev)

    assert result[vehicle_stop_status.STOP_ID] == "STOP-7"
    assert vehicle_stop_status.CURRENT_STOP_SEQUENCE not in result


# ---------------------------------------------------------------------------
# Test 4 — prev_state with only sequence (no stop_id): only sequence carried
# ---------------------------------------------------------------------------


def test_carries_forward_only_sequence_when_no_stop_id_in_prev():
    prev = {
        vehicle_stop_status.CURRENT_STOP_SEQUENCE: 3,
        vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
    }

    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=prev)

    assert result[vehicle_stop_status.CURRENT_STOP_SEQUENCE] == 3
    assert vehicle_stop_status.STOP_ID not in result


# ---------------------------------------------------------------------------
# Test 5 — Round-trip: seam output always passes validate_for_write (no prev)
# ---------------------------------------------------------------------------


def test_seam_output_passes_validate_for_write_no_prev():
    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=None)

    # Must not raise — this is the key contract guarantee
    mapping = vehicle_stop_status.validate_for_write(result)

    assert isinstance(mapping, dict)
    assert mapping[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"


# ---------------------------------------------------------------------------
# Test 6 — Round-trip: seam output with prev_state also passes validate_for_write
# ---------------------------------------------------------------------------


def test_seam_output_passes_validate_for_write_with_prev():
    prev = {
        vehicle_stop_status.CURRENT_STOP_SEQUENCE: 10,
        vehicle_stop_status.STOP_ID: "TERM-1",
        vehicle_stop_status.CURRENT_STATUS: "STOPPED_AT",
    }

    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state=prev)

    # Must not raise
    mapping = vehicle_stop_status.validate_for_write(result)

    assert mapping[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert mapping[vehicle_stop_status.CURRENT_STOP_SEQUENCE] == "10"
    assert mapping[vehicle_stop_status.STOP_ID] == "TERM-1"


# ---------------------------------------------------------------------------
# Test 7 — run_hash is accepted even when empty (seam ignores it)
# ---------------------------------------------------------------------------


def test_accepts_empty_run_hash():
    result = compute_stop_status({}, _POSITION_HASH, prev_state=None)

    assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"


# ---------------------------------------------------------------------------
# Test 8 — position_hash is accepted even when empty (seam ignores it)
# ---------------------------------------------------------------------------


def test_accepts_empty_position_hash():
    result = compute_stop_status(_RUN_HASH, {}, prev_state=None)

    assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    # Must still pass validate_for_write
    vehicle_stop_status.validate_for_write(result)


# ---------------------------------------------------------------------------
# Test 9 — prev_state empty dict: behaves same as None (no carry-forward)
# ---------------------------------------------------------------------------


def test_empty_prev_state_dict_carries_nothing():
    result = compute_stop_status(_RUN_HASH, _POSITION_HASH, prev_state={})

    assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
    assert vehicle_stop_status.CURRENT_STOP_SEQUENCE not in result
    assert vehicle_stop_status.STOP_ID not in result


# ===========================================================================
# Real map-matching tests (monkeypatched geometry)
# ===========================================================================
#
# Geometry: straight north-south line along the prime meridian.
#   Shape: 5 points from 0° to 4° latitude (≈ 444 km total).
#   Stops: 3 stops at 0°, 2°, 4° latitude.
#
#   The helper ``_make_geom`` assembles this without any ORM calls.
#   ``shapes.get_shape_geometry`` is patched to return it directly.
# ---------------------------------------------------------------------------


def _make_straight_geom() -> ShapeGeometry:
    """Build a canned north-pointing straight-line ShapeGeometry."""
    shape_points = [(float(i), 0.0, i) for i in range(5)]  # (lat, lon, seq)
    stop_rows = [
        {"stop_id": "S0", "stop_sequence": 1, "lat": 0.0, "lon": 0.0},
        {"stop_id": "S1", "stop_sequence": 2, "lat": 2.0, "lon": 0.0},
        {"stop_id": "S2", "stop_sequence": 3, "lat": 4.0, "lon": 0.0},
    ]
    return assemble_geometry("shp-straight", "trip-straight", shape_points, stop_rows)


def _pos(lat: float, lon: float = 0.0, speed: float | None = 8.0) -> dict:
    """Build a minimal position_hash dict."""
    p = {"latitude": lat, "longitude": lon, "bearing": 0.0, "timestamp": 1700000000}
    if speed is not None:
        p["speed"] = speed
    return p


def _run_hash() -> dict:
    return {"trip_id": "trip-straight", "shape_id": "shp-straight"}


class TestMapMatchingStatuses:
    """Status progression on a canned straight-line shape."""

    @pytest.fixture(autouse=True)
    def patch_geometry(self, monkeypatch):
        geom = _make_straight_geom()
        monkeypatch.setattr(
            "runs.domain.progression.shapes.get_shape_geometry",
            lambda *a, **kw: geom,
        )
        invalidate_cache()

    def test_far_from_stop_is_in_transit_to(self):
        """Position at lat=0.5° with speed 8 m/s — far from S1 (2°)."""
        result = compute_stop_status(_run_hash(), _pos(0.5), prev_state=None)
        assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"

    def test_incoming_at_when_within_incoming_radius(self):
        """Place vehicle just under INCOMING_AT_RADIUS_M before S1."""
        # Find lat just inside INCOMING_AT_RADIUS_M of S1 (2.0, 0.0).
        # 1° ≈ 111 195 m.  INCOMING_AT_RADIUS_M = 50 m → Δlat ≈ 50/111195.
        delta_lat = (INCOMING_AT_RADIUS_M - 5) / 111_195.0  # a little inside
        incoming_lat = 2.0 - delta_lat
        result = compute_stop_status(
            _run_hash(), _pos(incoming_lat, speed=8.0), prev_state=None
        )
        assert result[vehicle_stop_status.CURRENT_STATUS] == "INCOMING_AT"
        assert result[vehicle_stop_status.STOP_ID] == "S1"

    def test_stopped_at_when_within_stop_radius_and_slow(self):
        """Place vehicle inside STOP_RADIUS_M of S1 at near-zero speed."""
        delta_lat = (STOP_RADIUS_M - 2) / 111_195.0
        at_lat = 2.0 - delta_lat
        result = compute_stop_status(
            _run_hash(), _pos(at_lat, speed=STATIONARY_SPEED_MPS - 0.1), prev_state=None
        )
        assert result[vehicle_stop_status.CURRENT_STATUS] == "STOPPED_AT"
        assert result[vehicle_stop_status.STOP_ID] == "S1"

    def test_stopped_at_when_speed_absent(self):
        """No speed field → treated as stationary, so STOPPED_AT inside radius."""
        delta_lat = (STOP_RADIUS_M - 2) / 111_195.0
        at_lat = 2.0 - delta_lat
        result = compute_stop_status(
            _run_hash(), _pos(at_lat, speed=None), prev_state=None
        )
        assert result[vehicle_stop_status.CURRENT_STATUS] == "STOPPED_AT"

    def test_fast_inside_stop_radius_is_incoming_at(self):
        """Vehicle inside STOP_RADIUS_M but moving fast → INCOMING_AT.

        When a vehicle is within STOP_RADIUS_M but speed exceeds the stationary
        threshold the STOPPED_AT condition is not met.  The vehicle is still
        within INCOMING_AT_RADIUS_M (which is the outer radius) and still
        approaching, so INCOMING_AT is the correct status.
        """
        delta_lat = (STOP_RADIUS_M - 2) / 111_195.0
        at_lat = 2.0 - delta_lat
        result = compute_stop_status(
            _run_hash(), _pos(at_lat, speed=5.0), prev_state=None
        )
        # INCOMING_AT: within INCOMING_AT_RADIUS_M and still approaching.
        assert result[vehicle_stop_status.CURRENT_STATUS] == "INCOMING_AT"

    def test_status_sequence_in_transit_incoming_stopped(self):
        """Full sequence: far → near → at-stop."""
        rh = _run_hash()
        far = compute_stop_status(rh, _pos(0.5), prev_state=None)
        assert far[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"

        delta_lat = (INCOMING_AT_RADIUS_M - 5) / 111_195.0
        incoming = compute_stop_status(
            rh, _pos(2.0 - delta_lat, speed=8.0), prev_state=far
        )
        assert incoming[vehicle_stop_status.CURRENT_STATUS] == "INCOMING_AT"

        at_lat = 2.0 - (STOP_RADIUS_M - 2) / 111_195.0
        stopped = compute_stop_status(rh, _pos(at_lat, speed=0.1), prev_state=incoming)
        assert stopped[vehicle_stop_status.CURRENT_STATUS] == "STOPPED_AT"

    def test_stop_id_present_in_result(self):
        result = compute_stop_status(_run_hash(), _pos(0.5), prev_state=None)
        assert vehicle_stop_status.STOP_ID in result

    def test_stop_sequence_present_in_result(self):
        result = compute_stop_status(_run_hash(), _pos(0.5), prev_state=None)
        assert vehicle_stop_status.CURRENT_STOP_SEQUENCE in result

    def test_result_always_passes_validate_for_write(self):
        positions = [_pos(lat) for lat in [0.1, 0.5, 1.0, 1.9, 2.0, 2.5, 3.5, 4.0]]
        rh = _run_hash()
        prev = None
        for pos in positions:
            result = compute_stop_status(rh, pos, prev_state=prev)
            vehicle_stop_status.validate_for_write(result)
            prev = result


class TestMonotonicGuard:
    """current_stop_sequence must never decrease between position ticks."""

    @pytest.fixture(autouse=True)
    def patch_geometry(self, monkeypatch):
        geom = _make_straight_geom()
        monkeypatch.setattr(
            "runs.domain.progression.shapes.get_shape_geometry",
            lambda *a, **kw: geom,
        )
        invalidate_cache()

    def test_sequence_never_regresses_on_jittered_gps(self):
        """Feed a sequence of positions that sometimes step backward;
        current_stop_sequence must be non-decreasing."""
        rh = _run_hash()
        # Approach S1 (lat 2.0), cross it, then jitter backward.
        lats = [0.5, 1.0, 1.5, 1.9, 2.0, 1.95, 1.5, 1.0, 2.5, 3.0]
        prev = None
        prev_seq = 0
        for lat in lats:
            result = compute_stop_status(rh, _pos(lat, speed=2.0), prev_state=prev)
            seq = result.get(vehicle_stop_status.CURRENT_STOP_SEQUENCE, prev_seq)
            assert seq >= prev_seq, (
                f"Sequence regressed from {prev_seq} to {seq} at lat={lat}"
            )
            prev_seq = seq
            prev = result

    def test_sequence_holds_when_new_candidate_behind_prev(self):
        """If the map-matcher picks a stop behind the prev sequence, the prev
        sequence and stop_id are kept."""
        rh = _run_hash()
        # Give a prev_state that's already at stop 2 (S1, sequence=2).
        prev = {
            vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
            vehicle_stop_status.CURRENT_STOP_SEQUENCE: 2,
            vehicle_stop_status.STOP_ID: "S1",
        }
        # Position at lat=0.5 would normally pick S0 (sequence=1) — behind prev.
        result = compute_stop_status(rh, _pos(0.5), prev_state=prev)
        # The guard must clamp to sequence 2.
        assert result[vehicle_stop_status.CURRENT_STOP_SEQUENCE] == 2
        assert result[vehicle_stop_status.STOP_ID] == "S1"


class TestFallbackEdgeCases:
    """Extra fallback-path coverage (no monkeypatch needed — no geometry loaded)."""

    def test_missing_shape_id_fallback(self):
        rh = {"trip_id": "trip-1"}  # no shape_id
        result = compute_stop_status(rh, _pos(0.0), prev_state=None)
        assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"

    def test_missing_trip_id_fallback(self):
        rh = {"shape_id": "shp-1"}  # no trip_id
        result = compute_stop_status(rh, _pos(0.0), prev_state=None)
        assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"

    def test_missing_lat_lon_fallback(self):
        rh = (
            _run_hash()
        )  # valid, but get_shape_geometry will ORM-fail → fallback anyway
        result = compute_stop_status(rh, {}, prev_state=None)
        assert result[vehicle_stop_status.CURRENT_STATUS] == "IN_TRANSIT_TO"
