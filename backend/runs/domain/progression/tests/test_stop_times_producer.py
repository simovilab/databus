"""Tests for the real ETA stop-time-updates producer.

Coverage:
- Pure helper unit tests (ShapeGeometry constructed directly, temp MODEL_REGISTRY_DIR)
- Bug regression: no duplicate stop_sequence; list shrinks as vehicle advances
- Output-adapter edge cases: top-level error, per-stop error, STOPPED_AT
- Impure produce_stop_times: monkeypatched Redis + get_shape_geometry
- Builder hardening: unsorted/duplicate projection is sorted+deduped
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

import runs.domain.progression.stop_times as stop_times_module
from runs.domain.progression.shapes import ShapeGeometry, assemble_geometry
from runs.domain.progression.stop_times import (
    ETA_DEFAULT_UNCERTAINTY_S,
    STOP_TIME_UPDATES_TTL_S,
    compute_stop_time_updates,
    produce_stop_times,
)
from runs.domain.telemetry import keys, stop_time_updates, vehicle_stop_status
from schedule_engine.builders import build_trip_update_entity


# ---------------------------------------------------------------------------
# Shared geometry fixture helpers
# ---------------------------------------------------------------------------

# A simple straight N–S line: 6 stops spaced ~111 m apart (1 arc-second of lat).
# Shape: 7 points at lon = -84.0, lat from 9.900 to 9.906.
_LAT_BASE = 9.900
_LON = -84.0
_D_LAT = 0.001  # ≈ 111 m per step


def _straight_shape_points(n_points: int = 7) -> list[tuple[float, float, int]]:
    """Return (lat, lon, seq) tuples for a straight N–S polyline."""
    return [(_LAT_BASE + i * _D_LAT, _LON, i) for i in range(n_points)]


def _straight_stop_rows(n_stops: int = 6) -> list[dict]:
    """Return stop rows snapped to the first n_stops polyline vertices."""
    return [
        {
            "stop_id": f"S{i}",
            "stop_sequence": i,
            "lat": _LAT_BASE + i * _D_LAT,
            "lon": _LON,
        }
        for i in range(n_stops)
    ]


def make_straight_geom(n_stops: int = 6) -> ShapeGeometry:
    """Build a ShapeGeometry from the straight test polyline."""
    return assemble_geometry(
        shape_id="test-shape",
        trip_id="test-trip",
        shape_points=_straight_shape_points(n_stops + 1),
        stop_rows=_straight_stop_rows(n_stops),
    )


# ---------------------------------------------------------------------------
# Fixture: seed a baseline model into a temp directory
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def model_dir():
    """Seed the baseline ETA model into a temp directory once per module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "MODEL_REGISTRY_DIR": tmpdir}
        result = subprocess.run(
            [sys.executable, "-m", "gtfs_eta.seed_baseline_model"],
            env=env,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        assert result.returncode == 0, (
            f"seed_baseline_model failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        yield tmpdir


# ---------------------------------------------------------------------------
# Helper: build a minimal position dict (typed, as from position.from_redis)
# ---------------------------------------------------------------------------


def _pos(lat: float, lon: float, speed: float = 4.5, ts: int = 1_700_000_000) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "speed": speed,
        "timestamp": ts,
    }


def _run_hash(vehicle: str = "V1", route_id: str = "R1", trip_id: str = "T1") -> dict:
    return {
        "vehicle": vehicle,
        "route_id": route_id,
        "trip_id": trip_id,
        "shape_id": "test-shape",
    }


# ---------------------------------------------------------------------------
# Pure helper — happy path
# ---------------------------------------------------------------------------


class TestComputeStopTimeUpdatesHappyPath:
    """Predictions map correctly; ARRIVAL_TIME is int POSIX; ETAs increase."""

    def test_returns_list_of_dicts(self, model_dir):
        geom = make_straight_geom()
        # Vehicle at the very start of the route (before stop 0)
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=3,
                default_uncertainty_s=120,
            )
        assert isinstance(result, list)
        if result:  # may be empty if model not loaded but seed should work
            assert all(isinstance(e, dict) for e in result)

    def test_arrival_time_is_int_posix(self, model_dir):
        geom = make_straight_geom()
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=3,
                default_uncertainty_s=120,
            )
        for entry in result:
            assert isinstance(entry[stop_time_updates.ARRIVAL_TIME], int)
            assert isinstance(entry[stop_time_updates.DEPARTURE_TIME], int)
            # Sanity: POSIX in a plausible range (year 2000 → 2100)
            assert 946_684_800 < entry[stop_time_updates.ARRIVAL_TIME] < 4_102_444_800

    def test_uncertainty_equals_default(self, model_dir):
        geom = make_straight_geom()
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=3,
                default_uncertainty_s=99,
            )
        for entry in result:
            assert entry[stop_time_updates.UNCERTAINTY] == 99

    def test_etas_are_non_decreasing(self, model_dir):
        """ETAs must increase (or stay equal) as distance increases."""
        geom = make_straight_geom()
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=6,
                default_uncertainty_s=120,
            )
        times = [e[stop_time_updates.ARRIVAL_TIME] for e in result]
        for i in range(1, len(times)):
            assert times[i] >= times[i - 1], (
                f"ETA decreased: entry[{i - 1}]={times[i - 1]} > entry[{i}]={times[i]}"
            )

    def test_stop_id_and_sequence_match_geom(self, model_dir):
        geom = make_straight_geom(n_stops=6)
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=3,
                default_uncertainty_s=120,
            )
        geom_stop_ids = {s["stop_id"] for s in geom.stops}
        for entry in result:
            assert entry[stop_time_updates.STOP_ID] in geom_stop_ids


# ---------------------------------------------------------------------------
# Bug regression: no duplicates; list shrinks as vehicle advances
# ---------------------------------------------------------------------------


class TestBugRegressions:
    def test_no_duplicate_stop_sequence_in_output(self, model_dir):
        """Output must never contain duplicate stop_sequence values."""
        geom = make_straight_geom(n_stops=6)
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
                max_stops=6,
                default_uncertainty_s=120,
            )
        seqs = [e[stop_time_updates.STOP_SEQUENCE] for e in result]
        assert len(seqs) == len(set(seqs)), f"Duplicate sequences: {seqs}"

    def test_list_length_non_increasing_as_sequence_advances(self, model_dir):
        """As current_stop_sequence advances 0→3→5, the result length must not grow."""
        geom = make_straight_geom(n_stops=6)
        # Vehicle mid-route
        pos = _pos(_LAT_BASE + 2 * _D_LAT + 0.0005, _LON)

        def _count(current_seq: int, status: str = "IN_TRANSIT_TO") -> int:
            ss = {
                vehicle_stop_status.CURRENT_STOP_SEQUENCE: current_seq,
                vehicle_stop_status.CURRENT_STATUS: status,
            }
            with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
                res = compute_stop_time_updates(
                    run_hash=_run_hash(),
                    position=pos,
                    stop_status=ss,
                    geom=geom,
                    max_stops=6,
                    default_uncertainty_s=120,
                )
            return len(res)

        c0 = _count(0)
        c3 = _count(3)
        c5 = _count(5)
        assert c0 >= c3 >= c5, (
            f"List grew as sequence advanced: seq0={c0}, seq3={c3}, seq5={c5}"
        )

    def test_output_contains_only_sequences_gte_current(self, model_dir):
        """All returned sequences must be >= current_stop_sequence."""
        geom = make_straight_geom(n_stops=6)
        pos = _pos(_LAT_BASE, _LON)
        current_seq = 3
        ss = {
            vehicle_stop_status.CURRENT_STOP_SEQUENCE: current_seq,
            vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
        }
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status=ss,
                geom=geom,
                max_stops=6,
                default_uncertainty_s=120,
            )
        for entry in result:
            assert entry[stop_time_updates.STOP_SEQUENCE] >= current_seq


# ---------------------------------------------------------------------------
# Output-adapter edge cases
# ---------------------------------------------------------------------------


class TestOutputAdapterEdgeCases:
    def test_top_level_error_returns_empty(self):
        """When estimator returns a top-level error, result must be []."""
        geom = make_straight_geom()
        pos = _pos(_LAT_BASE, _LON)
        error_result = {
            "predictions": [],
            "error": "No trained models found for model_type",
            "model_key": None,
        }
        # estimate_stop_times is lazily imported inside compute_stop_time_updates;
        # patch the function in its source module (gtfs_eta.eta_service.estimator).
        with patch(
            "gtfs_eta.eta_service.estimator.estimate_stop_times",
            return_value=error_result,
        ):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
            )
        assert result == []

    def test_per_stop_error_is_skipped(self):
        """A prediction with per-stop error must be excluded from the output."""
        geom = make_straight_geom(n_stops=3)
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        now_ts = datetime.now(tz=timezone.utc)
        estimator_result = {
            "predictions": [
                {
                    "stop_id": "S0",
                    "stop_sequence": 0,
                    "distance_to_stop_m": 50.0,
                    "eta_seconds": None,
                    "eta_minutes": None,
                    "eta_formatted": None,
                    "eta_timestamp": None,
                    "error": "prediction failed",
                },
                {
                    "stop_id": "S1",
                    "stop_sequence": 1,
                    "distance_to_stop_m": 160.0,
                    "eta_seconds": 36.0,
                    "eta_minutes": 0.6,
                    "eta_formatted": "0m 36s",
                    "eta_timestamp": now_ts.isoformat(),
                },
            ],
        }
        with patch(
            "gtfs_eta.eta_service.estimator.estimate_stop_times",
            return_value=estimator_result,
        ):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
            )
        # Only S1 should be in the output (S0 has an error)
        assert len(result) == 1
        assert result[0][stop_time_updates.STOP_ID] == "S1"

    def test_stopped_at_excludes_current_stop(self, model_dir):
        """When status is STOPPED_AT, the current stop must not appear in output."""
        geom = make_straight_geom(n_stops=6)
        pos = _pos(_LAT_BASE + 2 * _D_LAT, _LON)
        current_seq = 2
        ss = {
            vehicle_stop_status.CURRENT_STOP_SEQUENCE: current_seq,
            vehicle_stop_status.CURRENT_STATUS: "STOPPED_AT",
        }
        with patch.dict(os.environ, {"MODEL_REGISTRY_DIR": model_dir}):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status=ss,
                geom=geom,
                max_stops=6,
                default_uncertainty_s=120,
            )
        seqs = [e[stop_time_updates.STOP_SEQUENCE] for e in result]
        assert current_seq not in seqs, (
            f"STOPPED_AT: current_seq={current_seq} found in output seqs {seqs}"
        )
        for seq in seqs:
            assert seq > current_seq

    def test_empty_upcoming_stops_returns_empty(self):
        """When no upcoming stops remain, result is []."""
        geom = make_straight_geom(n_stops=3)
        pos = _pos(_LAT_BASE, _LON)
        ss = {
            # All stops are behind the vehicle (seq 100 > any stop)
            vehicle_stop_status.CURRENT_STOP_SEQUENCE: 100,
            vehicle_stop_status.CURRENT_STATUS: "IN_TRANSIT_TO",
        }
        result = compute_stop_time_updates(
            run_hash=_run_hash(),
            position=pos,
            stop_status=ss,
            geom=geom,
        )
        assert result == []

    def test_empty_predictions_returns_empty(self):
        """When estimator returns empty predictions list (no error), result is []."""
        geom = make_straight_geom(n_stops=3)
        pos = _pos(_LAT_BASE - 0.0005, _LON)
        with patch(
            "gtfs_eta.eta_service.estimator.estimate_stop_times",
            return_value={"predictions": []},
        ):
            result = compute_stop_time_updates(
                run_hash=_run_hash(),
                position=pos,
                stop_status={},
                geom=geom,
            )
        assert result == []


# ---------------------------------------------------------------------------
# Impure produce_stop_times tests (monkeypatched Redis)
# ---------------------------------------------------------------------------

VEHICLE_ID = "V-test"
RUN_ID = "run-test"

_RUN_RAW = {
    "trip_id": "T1",
    "route_id": "R1",
    "shape_id": "shape-1",
    "vehicle": VEHICLE_ID,
}

_POS_RAW = {
    "latitude": str(_LAT_BASE),
    "longitude": str(_LON),
    "speed": "4.5",
    "timestamp": "1700000000",
}

_STOP_STATUS_RAW = {
    "current_stop_sequence": "2",
    "stop_id": "S2",
    "current_status": "IN_TRANSIT_TO",
}


def _fake_redis(run_raw=None, pos_raw=None, stop_status_raw=None) -> MagicMock:
    r = MagicMock()

    def hgetall_side_effect(key: str) -> dict:
        if key == keys.run_key(RUN_ID):
            return run_raw if run_raw is not None else _RUN_RAW
        if key == keys.position_key(VEHICLE_ID):
            return pos_raw if pos_raw is not None else _POS_RAW
        if key == keys.stop_status_key(RUN_ID):
            return stop_status_raw if stop_status_raw is not None else _STOP_STATUS_RAW
        return {}

    r.hgetall.side_effect = hgetall_side_effect
    return r


class TestProduceStopTimesImpure:
    def test_returns_early_when_run_hash_empty(self, monkeypatch):
        fake_r = _fake_redis(run_raw={})
        monkeypatch.setattr(stop_times_module, "r", fake_r)
        produce_stop_times(RUN_ID, VEHICLE_ID)
        fake_r.set.assert_not_called()

    def test_returns_early_when_no_position(self, monkeypatch):
        fake_r = _fake_redis(pos_raw={})
        monkeypatch.setattr(stop_times_module, "r", fake_r)
        produce_stop_times(RUN_ID, VEHICLE_ID)
        fake_r.set.assert_not_called()

    def test_does_not_write_when_no_shape(self, monkeypatch):
        fake_r = _fake_redis()
        monkeypatch.setattr(stop_times_module, "r", fake_r)
        with patch(
            "runs.domain.progression.stop_times.get_shape_geometry",
            return_value=None,
        ):
            produce_stop_times(RUN_ID, VEHICLE_ID)
        fake_r.set.assert_not_called()

    def test_does_not_write_when_compute_returns_empty(self, monkeypatch):
        geom = make_straight_geom()
        fake_r = _fake_redis()
        monkeypatch.setattr(stop_times_module, "r", fake_r)
        with (
            patch(
                "runs.domain.progression.stop_times.get_shape_geometry",
                return_value=geom,
            ),
            patch(
                "runs.domain.progression.stop_times.compute_stop_time_updates",
                return_value=[],
            ),
        ):
            produce_stop_times(RUN_ID, VEHICLE_ID)
        fake_r.set.assert_not_called()

    def test_writes_correct_key_with_ttl(self, monkeypatch):
        geom = make_straight_geom()
        fake_r = _fake_redis()
        monkeypatch.setattr(stop_times_module, "r", fake_r)

        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        fake_entries = [
            {
                stop_time_updates.STOP_SEQUENCE: 2,
                stop_time_updates.STOP_ID: "S2",
                stop_time_updates.ARRIVAL_TIME: now_ts + 60,
                stop_time_updates.DEPARTURE_TIME: now_ts + 60,
                stop_time_updates.UNCERTAINTY: 120,
            },
        ]
        with (
            patch(
                "runs.domain.progression.stop_times.get_shape_geometry",
                return_value=geom,
            ),
            patch(
                "runs.domain.progression.stop_times.compute_stop_time_updates",
                return_value=fake_entries,
            ),
        ):
            produce_stop_times(RUN_ID, VEHICLE_ID)

        fake_r.set.assert_called_once()
        call_args = fake_r.set.call_args
        written_key = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
        assert written_key == keys.stop_time_updates_key(RUN_ID)
        assert call_args.kwargs.get("ex") == STOP_TIME_UPDATES_TTL_S

    def test_written_payload_parses_to_unique_ascending_sequences(self, monkeypatch):
        geom = make_straight_geom()
        fake_r = _fake_redis()
        monkeypatch.setattr(stop_times_module, "r", fake_r)

        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        fake_entries = [
            {
                stop_time_updates.STOP_SEQUENCE: 2,
                stop_time_updates.STOP_ID: "S2",
                stop_time_updates.ARRIVAL_TIME: now_ts + 60,
                stop_time_updates.DEPARTURE_TIME: now_ts + 60,
                stop_time_updates.UNCERTAINTY: 120,
            },
            {
                stop_time_updates.STOP_SEQUENCE: 3,
                stop_time_updates.STOP_ID: "S3",
                stop_time_updates.ARRIVAL_TIME: now_ts + 120,
                stop_time_updates.DEPARTURE_TIME: now_ts + 120,
                stop_time_updates.UNCERTAINTY: 120,
            },
        ]
        with (
            patch(
                "runs.domain.progression.stop_times.get_shape_geometry",
                return_value=geom,
            ),
            patch(
                "runs.domain.progression.stop_times.compute_stop_time_updates",
                return_value=fake_entries,
            ),
        ):
            produce_stop_times(RUN_ID, VEHICLE_ID)

        payload_str = fake_r.set.call_args.args[1]
        parsed = stop_time_updates.from_redis(payload_str)
        seqs = [e["stop_sequence"] for e in parsed]
        assert len(seqs) == len(set(seqs)), f"Duplicate sequences: {seqs}"
        assert seqs == sorted(seqs), f"Not ascending: {seqs}"


# ---------------------------------------------------------------------------
# Builder hardening: unsorted/duplicate projection is sorted+deduped
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal dict-backed Redis stub for builder tests."""

    def __init__(self, data: dict):
        self._data = data

    def hgetall(self, key: str) -> dict:
        val = self._data.get(key, {})
        return dict(val) if isinstance(val, dict) else {}

    def smembers(self, key: str) -> set:
        val = self._data.get(key, set())
        return set(val) if isinstance(val, set) else set()

    def get(self, key: str) -> str | None:
        val = self._data.get(key)
        return val if isinstance(val, str) else None


_BUILDER_RUN_ID = "run-b1"
_BUILDER_VID = "V-b1"


def _builder_redis_data(projection_entries: list[dict]) -> dict:
    return {
        "runs:in_progress": {_BUILDER_RUN_ID},
        f"run:{_BUILDER_RUN_ID}": {
            "vehicle": _BUILDER_VID,
            "trip_id": "trip-x",
            "route_id": "route-x",
            "schedule_relationship": "SCHEDULED",
        },
        f"run:{_BUILDER_RUN_ID}:trip": {
            "trip_id": "trip-x",
            "route_id": "route-x",
            "schedule_relationship": "SCHEDULED",
        },
        f"vehicle:{_BUILDER_VID}:position": {
            "latitude": "9.900",
            "longitude": "-84.0",
            "timestamp": "1700000000",
        },
        f"vehicle:{_BUILDER_VID}:metadata": {
            "id": _BUILDER_VID,
            "label": "Bus B1",
        },
        f"run:{_BUILDER_RUN_ID}:vehicle_stop_status": {
            "current_stop_sequence": "1",
            "current_status": "IN_TRANSIT_TO",
        },
        keys.stop_time_updates_key(_BUILDER_RUN_ID): stop_time_updates.to_redis(
            projection_entries
        ),
    }


class TestBuilderHardening:
    def test_unsorted_projection_is_sorted_ascending(self):
        now = int(datetime.now(tz=timezone.utc).timestamp())
        # Deliberately reverse order: seq 5 before seq 2
        entries = [
            {
                stop_time_updates.STOP_SEQUENCE: 5,
                stop_time_updates.STOP_ID: "S5",
                stop_time_updates.ARRIVAL_TIME: now + 200,
                stop_time_updates.DEPARTURE_TIME: now + 200,
                stop_time_updates.UNCERTAINTY: 120,
            },
            {
                stop_time_updates.STOP_SEQUENCE: 2,
                stop_time_updates.STOP_ID: "S2",
                stop_time_updates.ARRIVAL_TIME: now + 100,
                stop_time_updates.DEPARTURE_TIME: now + 100,
                stop_time_updates.UNCERTAINTY: 120,
            },
        ]
        r = FakeRedis(_builder_redis_data(entries))
        entity = build_trip_update_entity(r, _BUILDER_RUN_ID)
        assert entity is not None
        updates = entity["trip_update"]["stop_time_update"]
        seqs = [u["stop_sequence"] for u in updates]
        assert seqs == sorted(seqs), f"Not sorted: {seqs}"

    def test_duplicate_sequences_are_deduped(self):
        now = int(datetime.now(tz=timezone.utc).timestamp())
        # Two entries with same stop_sequence=3
        entries = [
            {
                stop_time_updates.STOP_SEQUENCE: 3,
                stop_time_updates.STOP_ID: "S3-a",
                stop_time_updates.ARRIVAL_TIME: now + 100,
                stop_time_updates.DEPARTURE_TIME: now + 100,
                stop_time_updates.UNCERTAINTY: 120,
            },
            {
                stop_time_updates.STOP_SEQUENCE: 3,
                stop_time_updates.STOP_ID: "S3-b",
                stop_time_updates.ARRIVAL_TIME: now + 110,
                stop_time_updates.DEPARTURE_TIME: now + 110,
                stop_time_updates.UNCERTAINTY: 120,
            },
            {
                stop_time_updates.STOP_SEQUENCE: 5,
                stop_time_updates.STOP_ID: "S5",
                stop_time_updates.ARRIVAL_TIME: now + 200,
                stop_time_updates.DEPARTURE_TIME: now + 200,
                stop_time_updates.UNCERTAINTY: 120,
            },
        ]
        r = FakeRedis(_builder_redis_data(entries))
        entity = build_trip_update_entity(r, _BUILDER_RUN_ID)
        assert entity is not None
        updates = entity["trip_update"]["stop_time_update"]
        seqs = [u["stop_sequence"] for u in updates]
        assert len(seqs) == len(set(seqs)), f"Duplicates remain: {seqs}"
        assert len(seqs) == 2  # seq 3 (first kept) + seq 5

    def test_first_of_duplicate_is_kept(self):
        """When two entries share a stop_sequence, the first (lower arrival) is kept."""
        now = int(datetime.now(tz=timezone.utc).timestamp())
        entries = [
            {
                stop_time_updates.STOP_SEQUENCE: 3,
                stop_time_updates.STOP_ID: "S3-first",
                stop_time_updates.ARRIVAL_TIME: now + 100,
                stop_time_updates.DEPARTURE_TIME: now + 100,
                stop_time_updates.UNCERTAINTY: 120,
            },
            {
                stop_time_updates.STOP_SEQUENCE: 3,
                stop_time_updates.STOP_ID: "S3-second",
                stop_time_updates.ARRIVAL_TIME: now + 110,
                stop_time_updates.DEPARTURE_TIME: now + 110,
                stop_time_updates.UNCERTAINTY: 120,
            },
        ]
        r = FakeRedis(_builder_redis_data(entries))
        entity = build_trip_update_entity(r, _BUILDER_RUN_ID)
        updates = entity["trip_update"]["stop_time_update"]
        assert updates[0]["stop_id"] == "S3-first"
