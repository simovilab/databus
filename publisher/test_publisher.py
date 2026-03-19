"""
Unit tests for publisher.py — focused on build_stop_time_updates.
Run with: uv run pytest test_publisher.py -v
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from publisher import build_stop_time_updates


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RUN = {
    "route_id": "bUCR_L2",
    "trip_id": "trip_001",
    "direction_id": "0",
    "vehicle": "bus_01",
}

SAMPLE_POSITION = {
    "latitude": "9.9281",
    "longitude": "-84.0907",
    "bearing": "270.0",
    "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
}

SAMPLE_PROGRESSION = {
    "current_stop_sequence": "3",
    "stop_id": "UCR_0_03",
    "current_status": "IN_TRANSIT_TO",
}


# ---------------------------------------------------------------------------
# Known-route tests (existing MOCK_ROUTE_STOPS behaviour)
# ---------------------------------------------------------------------------

class TestKnownRoute:
    def test_known_route_returns_future_stops(self):
        updates = build_stop_time_updates(SAMPLE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION)
        assert len(updates) > 0

    def test_known_route_returns_stops_from_current_sequence_onwards(self):
        updates = build_stop_time_updates(SAMPLE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION)
        sequences = [u["stop_sequence"] for u in updates]
        # current_stop_sequence is 3 and status is IN_TRANSIT_TO → include seq 3+
        assert all(seq >= 3 for seq in sequences)

    def test_known_route_stopped_at_skips_current_stop(self):
        progression = {**SAMPLE_PROGRESSION, "current_status": "STOPPED_AT"}
        updates = build_stop_time_updates(SAMPLE_RUN, SAMPLE_POSITION, progression)
        sequences = [u["stop_sequence"] for u in updates]
        assert 3 not in sequences  # current stop skipped when already stopped

    def test_update_has_required_fields(self):
        updates = build_stop_time_updates(SAMPLE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION)
        for u in updates:
            assert "stop_sequence" in u
            assert "stop_id" in u
            assert "eta_posix" in u
            assert "uncertainty" in u

    def test_etas_are_monotonically_increasing(self):
        updates = build_stop_time_updates(SAMPLE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION)
        etas = [u["eta_posix"] for u in updates]
        assert etas == sorted(etas)


# ---------------------------------------------------------------------------
# Unknown-route fallback — THIS IS THE BUG BEING FIXED
# ---------------------------------------------------------------------------

class TestUnknownRouteFallback:
    UNKNOWN_ROUTE_RUN = {**SAMPLE_RUN, "route_id": "SOME_OTHER_ROUTE"}

    def test_unknown_route_returns_at_least_one_update(self):
        """
        Previously returned [] for any route not in MOCK_ROUTE_STOPS.
        Now should produce at least one stop time update from progression data.
        """
        updates = build_stop_time_updates(
            self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION
        )
        assert len(updates) >= 1

    def test_unknown_route_fallback_uses_progression_stop(self):
        updates = build_stop_time_updates(
            self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION
        )
        stop_ids = [u["stop_id"] for u in updates]
        assert "UCR_0_03" in stop_ids

    def test_unknown_route_fallback_has_required_fields(self):
        updates = build_stop_time_updates(
            self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION
        )
        for u in updates:
            assert "stop_sequence" in u
            assert "stop_id" in u
            assert "eta_posix" in u
            assert "uncertainty" in u

    def test_unknown_route_fallback_eta_in_the_future(self):
        updates = build_stop_time_updates(
            self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, SAMPLE_PROGRESSION
        )
        now = int(datetime.now(timezone.utc).timestamp())
        for u in updates:
            assert u["eta_posix"] >= now

    def test_empty_route_id_returns_empty(self):
        run = {**SAMPLE_RUN, "route_id": ""}
        updates = build_stop_time_updates(run, SAMPLE_POSITION, SAMPLE_PROGRESSION)
        assert updates == []

    def test_missing_progression_returns_empty(self):
        updates = build_stop_time_updates(self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, {})
        assert updates == []

    def test_missing_stop_id_in_progression_returns_empty(self):
        progression = {"current_stop_sequence": "3", "current_status": "IN_TRANSIT_TO"}
        updates = build_stop_time_updates(
            self.UNKNOWN_ROUTE_RUN, SAMPLE_POSITION, progression
        )
        assert updates == []
