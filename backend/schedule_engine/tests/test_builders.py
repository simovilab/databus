"""Django-free unit tests for schedule_engine.builders.

These tests import ONLY ``schedule_engine.builders`` (never ``tasks``).
A small dict-backed FakeRedis supports the subset of the Redis API the
builders use: ``smembers(key) -> set`` and ``hgetall(key) -> dict``.
All values in hashes are strings, matching the ``decode_responses=True``
behaviour of the live client.

The key proto gate: every feed dict is passed through
``json_format.ParseDict(feed, gtfs_rt.FeedMessage())`` *and*
``.SerializeToString()`` to catch proto2 unknown-field / required-field
errors at test time.
"""

import json

import pytest
from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2 as gtfs_rt

from runs.domain.telemetry import keys, stop_time_updates
from schedule_engine.builders import (
    build_trip_updates_feed,
    build_vehicle_position_entity,
    build_vehicle_positions_feed,
    get_current_timestamp,
    get_entity_id,
)


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal dict-backed Redis stub.

    Supports:
    - ``hgetall(key) -> dict[str, str]``  (empty dict when absent)
    - ``smembers(key) -> set[str]``       (empty set when absent)
    - ``get(key) -> str | None``          (None when absent or value is not a str)
    """

    def __init__(self, data: dict | None = None):
        # data maps key -> value where value is either a dict (hash), set, or str
        self._data: dict = data or {}

    def hgetall(self, key: str) -> dict:
        val = self._data.get(key, {})
        return dict(val) if isinstance(val, dict) else {}

    def smembers(self, key: str) -> set:
        val = self._data.get(key, set())
        return set(val) if isinstance(val, set) else set()

    def get(self, key: str) -> str | None:
        val = self._data.get(key)
        return val if isinstance(val, str) else None


# ---------------------------------------------------------------------------
# Shared seed data helpers
# ---------------------------------------------------------------------------

RUN_ID = "run-001"
VEHICLE_ID = "vehicle-42"


_STOP_TIME_ENTRY_1 = {
    "stop_sequence": 3,
    "stop_id": "stop-99",
    "arrival_time": 1700001000,
    "departure_time": 1700001000,
    "uncertainty": 120,
}

_STOP_TIME_ENTRY_2 = {
    "stop_sequence": 4,
    "stop_id": "stop-100",
    "arrival_time": 1700001300,
    "departure_time": 1700001300,
    "uncertainty": 120,
}


def _full_redis_data() -> dict:
    """Return a FakeRedis data dict seeded with all hashes for one in-progress run."""
    return {
        # membership set
        "runs:in_progress": {RUN_ID},
        # flat run hash (lifecycle record + trip fields for fallback)
        f"run:{RUN_ID}": {
            "vehicle": VEHICLE_ID,
            "trip_id": "trip-abc",
            "route_id": "route-1",
            "direction_id": "0",
            "schedule_relationship": "SCHEDULED",
            "shape_id": "shape-X",
            "start_time": "08:00:00",
            "start_date": "20260608",
        },
        # GTFS-RT-shaped trip projection
        f"run:{RUN_ID}:trip": {
            "trip_id": "trip-abc",
            "route_id": "route-1",
            "direction_id": "0",
            "schedule_relationship": "SCHEDULED",
            "start_time": "08:00:00",
            "start_date": "20260608",
        },
        # edge position hash (vehicle-keyed)
        f"vehicle:{VEHICLE_ID}:position": {
            "latitude": "51.5074",
            "longitude": "-0.1278",
            "bearing": "90.0",
            "timestamp": "1700000000",
        },
        # edge occupancy hash — includes occupancy_count (edge-only field)
        f"vehicle:{VEHICLE_ID}:occupancy": {
            "occupancy_percentage": "35",
            "occupancy_count": "18",
            "occupancy_status": "FEW_SEATS_AVAILABLE",
        },
        # server stop-status hash (run-keyed)
        f"run:{RUN_ID}:vehicle_stop_status": {
            "current_stop_sequence": "3",
            "stop_id": "stop-99",
            "current_status": "IN_TRANSIT_TO",
        },
        # stop-time-updates projection (JSON string, written by stop_times producer)
        keys.stop_time_updates_key(RUN_ID): stop_time_updates.to_redis(
            [_STOP_TIME_ENTRY_1, _STOP_TIME_ENTRY_2]
        ),
        # vehicle metadata
        f"vehicle:{VEHICLE_ID}:metadata": {
            "id": VEHICLE_ID,
            "label": "Bus 42",
            "license_plate": "XYZ-1234",
        },
    }


def _parse_feed(feed_dict: dict) -> gtfs_rt.FeedMessage:
    """Round-trip a feed dict through ParseDict + SerializeToString (the proto gate)."""
    msg = json_format.ParseDict(feed_dict, gtfs_rt.FeedMessage())
    # SerializeToString catches proto2 required-field / unknown-field errors
    raw = msg.SerializeToString()
    # Deserialise back to verify the bytes are valid
    roundtripped = gtfs_rt.FeedMessage()
    roundtripped.ParseFromString(raw)
    return roundtripped


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


def test_get_current_timestamp_is_positive_int():
    ts = get_current_timestamp()
    assert isinstance(ts, int)
    assert ts > 0


def test_get_entity_id_returns_vehicle_id():
    assert get_entity_id("v-7") == "v-7"


# ---------------------------------------------------------------------------
# build_vehicle_positions_feed — full seed
# ---------------------------------------------------------------------------


class TestBuildVehiclePositionsFeedFullSeed:
    def setup_method(self):
        self.r = FakeRedis(_full_redis_data())
        self.feed = build_vehicle_positions_feed(self.r)
        self.proto_msg = _parse_feed(self.feed)

    def test_proto_gate_parse_and_serialize(self):
        """ParseDict + SerializeToString must not raise."""
        # Already executed in setup_method via _parse_feed; reaching here = pass.
        assert self.proto_msg is not None

    def test_exactly_one_entity(self):
        assert len(self.feed["entity"]) == 1

    def test_entity_id_is_vehicle_id(self):
        assert self.feed["entity"][0]["id"] == VEHICLE_ID

    def test_timestamp_lifted_to_vehicle_position_level(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["timestamp"] == 1700000000

    def test_position_sub_dict_has_no_timestamp(self):
        pos = self.feed["entity"][0]["vehicle"]["position"]
        assert "timestamp" not in pos

    def test_position_has_lat_lon(self):
        pos = self.feed["entity"][0]["vehicle"]["position"]
        assert pytest.approx(pos["latitude"]) == 51.5074
        assert pytest.approx(pos["longitude"]) == -0.1278

    def test_current_status_from_stop_status_hash(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["current_status"] == "IN_TRANSIT_TO"

    def test_current_stop_sequence_from_stop_status_hash(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["current_stop_sequence"] == 3

    def test_stop_id_from_stop_status_hash(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["stop_id"] == "stop-99"

    def test_occupancy_status_present(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["occupancy_status"] == "FEW_SEATS_AVAILABLE"

    def test_occupancy_percentage_present(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["occupancy_percentage"] == 35

    def test_trip_id_from_trip_hash(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["trip"]["trip_id"] == "trip-abc"

    def test_vehicle_descriptor_present(self):
        v = self.feed["entity"][0]["vehicle"]
        assert v["vehicle"]["id"] == VEHICLE_ID
        assert v["vehicle"]["label"] == "Bus 42"

    def test_proto_entity_timestamp_matches(self):
        entity = self.proto_msg.entity[0]
        assert entity.vehicle.timestamp == 1700000000

    def test_proto_position_has_lat_lon(self):
        entity = self.proto_msg.entity[0]
        assert pytest.approx(entity.vehicle.position.latitude) == 51.5074
        assert pytest.approx(entity.vehicle.position.longitude) == -0.1278


# ---------------------------------------------------------------------------
# Explicit occupancy_count exclusion
# ---------------------------------------------------------------------------


class TestOccupancyCountExclusion:
    """occupancy_count must NOT appear in the feed dict — it is not a GTFS-RT
    VehiclePosition field and would cause ParseDict to raise."""

    def setup_method(self):
        self.r = FakeRedis(_full_redis_data())
        self.feed = build_vehicle_positions_feed(self.r)

    def test_occupancy_count_absent_from_entity_vehicle_dict(self):
        v = self.feed["entity"][0]["vehicle"]
        assert "occupancy_count" not in v

    def test_occupancy_count_absent_from_serialised_json(self):
        # Belt-and-suspenders: check the JSON string too
        feed_json = json.dumps(self.feed)
        assert "occupancy_count" not in feed_json

    def test_proto_gate_still_succeeds_without_occupancy_count(self):
        """Confirm ParseDict succeeds on the dict that excludes occupancy_count."""
        _parse_feed(self.feed)  # would raise if occupancy_count leaked through


# ---------------------------------------------------------------------------
# Timestamp lift
# ---------------------------------------------------------------------------


class TestTimestampLift:
    """A position hash with ``timestamp`` must surface it at VehiclePosition
    level, not inside the position sub-dict."""

    def test_timestamp_in_position_hash_lifted_to_vp_level(self):
        data = _full_redis_data()
        data[f"vehicle:{VEHICLE_ID}:position"]["timestamp"] = "1700001234"
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        v = feed["entity"][0]["vehicle"]
        assert v["timestamp"] == 1700001234
        assert "timestamp" not in v["position"]

    def test_missing_timestamp_uses_current_time(self):
        data = _full_redis_data()
        del data[f"vehicle:{VEHICLE_ID}:position"]["timestamp"]
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        v = feed["entity"][0]["vehicle"]
        # Should be a recent unix timestamp (within the last minute)
        now = get_current_timestamp()
        assert 0 < v["timestamp"] <= now + 5  # small tolerance for clock skew

    def test_timestamp_absent_from_position_sub_dict_when_missing(self):
        data = _full_redis_data()
        del data[f"vehicle:{VEHICLE_ID}:position"]["timestamp"]
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        v = feed["entity"][0]["vehicle"]
        assert "timestamp" not in v.get("position", {})


# ---------------------------------------------------------------------------
# Skip semantics
# ---------------------------------------------------------------------------


class TestSkipSemantics:
    """A run whose vehicle has no position, occupancy, or stop-status data
    must produce zero entities in the feed."""

    def test_no_sensor_data_produces_zero_entities(self):
        data = {
            "runs:in_progress": {RUN_ID},
            f"run:{RUN_ID}": {
                "vehicle": VEHICLE_ID,
                "trip_id": "trip-abc",
                "route_id": "route-1",
            },
            # Deliberately omit position, occupancy, and stop_status hashes
        }
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        assert feed["entity"] == []

    def test_run_missing_from_redis_produces_zero_entities(self):
        data = {
            "runs:in_progress": {"nonexistent-run"},
        }
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        assert feed["entity"] == []

    def test_run_without_vehicle_field_produces_zero_entities(self):
        data = {
            "runs:in_progress": {RUN_ID},
            f"run:{RUN_ID}": {"trip_id": "trip-abc"},  # no vehicle field
        }
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        assert feed["entity"] == []

    def test_proto_gate_succeeds_on_empty_feed(self):
        data = {"runs:in_progress": set()}
        r = FakeRedis(data)
        feed = build_vehicle_positions_feed(r)
        assert feed["entity"] == []
        _parse_feed(feed)  # must not raise


# ---------------------------------------------------------------------------
# build_vehicle_position_entity — unit-level
# ---------------------------------------------------------------------------


class TestBuildVehiclePositionEntityUnit:
    def test_returns_none_when_run_missing(self):
        r = FakeRedis({"runs:in_progress": {RUN_ID}})
        assert build_vehicle_position_entity(r, RUN_ID) is None

    def test_returns_none_when_no_vehicle_field(self):
        data = {f"run:{RUN_ID}": {"trip_id": "t"}}
        r = FakeRedis(data)
        assert build_vehicle_position_entity(r, RUN_ID) is None

    def test_schedule_relationship_defaults_to_scheduled(self):
        data = _full_redis_data()
        # Remove schedule_relationship from the trip hash
        del data[f"run:{RUN_ID}:trip"]["schedule_relationship"]
        del data[f"run:{RUN_ID}"]["schedule_relationship"]
        r = FakeRedis(data)
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert entity["vehicle"]["trip"]["schedule_relationship"] == "SCHEDULED"

    def test_trip_fallback_from_flat_run_hash(self):
        """When run:<id>:trip is absent, trip fields come from the flat run hash."""
        data = _full_redis_data()
        del data[f"run:{RUN_ID}:trip"]
        r = FakeRedis(data)
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert entity["vehicle"]["trip"]["trip_id"] == "trip-abc"

    def test_congestion_level_emitted_when_present(self):
        data = _full_redis_data()
        data[f"run:{RUN_ID}:congestion_level"] = {"congestion_level": "STOP_AND_GO"}
        r = FakeRedis(data)
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert entity["vehicle"]["congestion_level"] == "STOP_AND_GO"

    def test_congestion_level_absent_when_hash_missing(self):
        r = FakeRedis(_full_redis_data())
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert "congestion_level" not in entity["vehicle"]

    def test_license_plate_included_when_present(self):
        r = FakeRedis(_full_redis_data())
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert entity["vehicle"]["vehicle"]["license_plate"] == "XYZ-1234"

    def test_wheelchair_accessible_included_when_present(self):
        data = _full_redis_data()
        data[f"vehicle:{VEHICLE_ID}:metadata"]["wheelchair_accessible"] = "1"
        r = FakeRedis(data)
        entity = build_vehicle_position_entity(r, RUN_ID)
        assert entity is not None
        assert entity["vehicle"]["vehicle"]["wheelchair_accessible"] == "1"


# ---------------------------------------------------------------------------
# build_trip_updates_feed
# ---------------------------------------------------------------------------


class TestBuildTripUpdatesFeed:
    def setup_method(self):
        self.r = FakeRedis(_full_redis_data())
        self.feed = build_trip_updates_feed(self.r)
        self.proto_msg = _parse_feed(self.feed)

    def test_proto_gate_parse_and_serialize(self):
        assert self.proto_msg is not None

    def test_exactly_one_entity(self):
        assert len(self.feed["entity"]) == 1

    def test_trip_id_from_trip_hash(self):
        tu = self.feed["entity"][0]["trip_update"]
        assert tu["trip"]["trip_id"] == "trip-abc"

    def test_vehicle_descriptor_present(self):
        tu = self.feed["entity"][0]["trip_update"]
        assert tu["vehicle"]["id"] == VEHICLE_ID
        assert tu["vehicle"]["label"] == "Bus 42"

    def test_vehicle_no_wheelchair_in_trip_update(self):
        """Trip updates do not include wheelchair_accessible (matches current code)."""
        data = _full_redis_data()
        data[f"vehicle:{VEHICLE_ID}:metadata"]["wheelchair_accessible"] = "1"
        r = FakeRedis(data)
        feed = build_trip_updates_feed(r)
        tu = feed["entity"][0]["trip_update"]
        assert "wheelchair_accessible" not in tu["vehicle"]

    def test_timestamp_lifted_from_position(self):
        tu = self.feed["entity"][0]["trip_update"]
        assert tu["timestamp"] == 1700000000

    def test_stop_time_update_key_present(self):
        tu = self.feed["entity"][0]["trip_update"]
        assert "stop_time_update" in tu
        assert isinstance(tu["stop_time_update"], list)

    def test_stop_time_update_entries_from_projection(self):
        """Entries must come from the seeded projection, reshaped to nested arrival/departure."""
        tu = self.feed["entity"][0]["trip_update"]
        updates = tu["stop_time_update"]
        assert len(updates) == 2
        # First entry
        assert updates[0]["stop_sequence"] == 3
        assert updates[0]["stop_id"] == "stop-99"
        assert updates[0]["arrival"]["time"] == 1700001000
        assert updates[0]["arrival"]["uncertainty"] == 120
        assert updates[0]["departure"]["time"] == 1700001000
        assert updates[0]["departure"]["uncertainty"] == 120
        # Second entry
        assert updates[1]["stop_sequence"] == 4
        assert updates[1]["stop_id"] == "stop-100"
        assert updates[1]["arrival"]["time"] == 1700001300

    def test_stop_time_update_proto_gate(self):
        """The full feed with stop_time_updates must round-trip through proto."""
        assert self.proto_msg is not None
        entity = self.proto_msg.entity[0]
        assert entity.trip_update.stop_time_update[0].stop_sequence == 3
        assert entity.trip_update.stop_time_update[0].stop_id == "stop-99"
        assert entity.trip_update.stop_time_update[0].arrival.time == 1700001000

    def test_skip_when_no_position_and_no_stop_status(self):
        data = {
            "runs:in_progress": {RUN_ID},
            f"run:{RUN_ID}": {"vehicle": VEHICLE_ID, "trip_id": "t", "route_id": "r"},
            f"vehicle:{VEHICLE_ID}:metadata": {"id": VEHICLE_ID, "label": "B"},
        }
        r = FakeRedis(data)
        feed = build_trip_updates_feed(r)
        assert feed["entity"] == []

    def test_proto_gate_trip_id_roundtrip(self):
        entity = self.proto_msg.entity[0]
        assert entity.trip_update.trip.trip_id == "trip-abc"

    def test_license_plate_in_trip_update_vehicle(self):
        tu = self.feed["entity"][0]["trip_update"]
        assert tu["vehicle"]["license_plate"] == "XYZ-1234"

    def test_trip_fallback_from_flat_run_hash(self):
        data = _full_redis_data()
        del data[f"run:{RUN_ID}:trip"]
        r = FakeRedis(data)
        feed = build_trip_updates_feed(r)
        assert len(feed["entity"]) == 1
        tu = feed["entity"][0]["trip_update"]
        assert tu["trip"]["trip_id"] == "trip-abc"

    def test_missing_projection_yields_no_stop_time_update_entries(self):
        """When the stop_time_updates projection key is absent, stop_time_update is []."""
        data = _full_redis_data()
        # Remove the projection key
        del data[keys.stop_time_updates_key(RUN_ID)]
        r = FakeRedis(data)
        feed = build_trip_updates_feed(r)
        assert len(feed["entity"]) == 1
        tu = feed["entity"][0]["trip_update"]
        assert tu["stop_time_update"] == []

    def test_empty_projection_yields_no_stop_time_update_entries(self):
        """When the projection is an empty JSON array, stop_time_update is []."""
        data = _full_redis_data()
        data[keys.stop_time_updates_key(RUN_ID)] = stop_time_updates.to_redis([])
        r = FakeRedis(data)
        feed = build_trip_updates_feed(r)
        tu = feed["entity"][0]["trip_update"]
        assert tu["stop_time_update"] == []


# ---------------------------------------------------------------------------
# Feed header
# ---------------------------------------------------------------------------


class TestFeedHeader:
    def test_vp_feed_header_fields(self):
        r = FakeRedis({"runs:in_progress": set()})
        feed = build_vehicle_positions_feed(r)
        assert feed["header"]["gtfs_realtime_version"] == "2.0"
        assert feed["header"]["incrementality"] == "FULL_DATASET"
        assert isinstance(feed["header"]["timestamp"], int)

    def test_tu_feed_header_fields(self):
        r = FakeRedis({"runs:in_progress": set()})
        feed = build_trip_updates_feed(r)
        assert feed["header"]["gtfs_realtime_version"] == "2.0"
        assert feed["header"]["incrementality"] == "FULL_DATASET"
        assert isinstance(feed["header"]["timestamp"], int)
