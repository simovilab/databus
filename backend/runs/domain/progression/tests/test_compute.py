"""Pure unit tests for compute_stop_status — no Django/Redis required.

The key guarantee tested here:
- The seam always returns a dict that passes vehicle_stop_status.validate_for_write
  (round-trip through the contract).  This pins the output shape so that
  the future map-matching port cannot accidentally break the contract.
"""

from __future__ import annotations

import pytest

from runs.domain.progression.compute import compute_stop_status
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
