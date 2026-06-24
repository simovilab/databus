---
icon: lucide/file-json
description: The two GTFS specifications Databús ingests (Schedule) and emits (Realtime), with field-level detail on VehiclePosition and TripUpdate feeds.
---

# GTFS Schedule & Realtime

GTFS (General Transit Feed Specification) is the open standard used by transit
agencies worldwide to describe their services. Databús® works with both flavors:
**GTFS Schedule** (the static timetable) and **GTFS Realtime** (the live
overlay).

## GTFS Schedule

GTFS Schedule describes what service an agency *plans* to run: routes, trips,
stops, stop times, calendars, shapes, fares. It is a ZIP archive of CSV files
distributed by the agency. Databús® imports it into PostgreSQL via the `feed`
Django app and uses it as the ground truth for:

- Validating that a new run references a real trip and route.
- Loading the shape geometry used for server-side map-matching.
- Projecting upcoming stop arrivals into `run:<id>:stop_time_updates`.

The Django models that mirror GTFS Schedule tables live in
`backend/feed/models.py` and extend abstract base classes from the `gtfs`
submodule (`Agency`, `Stop`, `Route`, `Trip`, `StopTime`, `Calendar`,
`Shape`). See [Data model › Django models](../data-model/django-models.md) for
the full list.

The `schedule_engine` app handles GTFS-Schedule-side tasks: building the run
UI, routing queries, and fake-stop-time generation for the simulator.
See [Data model › Schedule engine](../data-model/schedule-engine.md).

## GTFS Realtime

GTFS Realtime is a protobuf-encoded overlay that describes what service is
*happening right now*. A GTFS-RT feed is a `FeedMessage` containing a list of
`FeedEntity` records, each holding one of three entity types:

### VehiclePosition

Reports where a vehicle currently is and its relationship to stops.

Fields Databús® populates:

| Field | Source Redis key | Notes |
| --- | --- | --- |
| `trip` | `run:<id>:trip` | TripDescriptor projection |
| `vehicle` | `vehicle:<id>:metadata` | id, label, license_plate |
| `position` | `vehicle:<id>:position` | latitude, longitude, bearing, speed |
| `timestamp` | `vehicle:<id>:position.timestamp` | lifted to VP level |
| `current_stop_sequence` | `run:<id>:vehicle_stop_status` | server-computed |
| `stop_id` | `run:<id>:vehicle_stop_status` | server-computed |
| `current_status` | `run:<id>:vehicle_stop_status` | INCOMING_AT / STOPPED_AT / IN_TRANSIT_TO |
| `occupancy_status` | `vehicle:<id>:occupancy` | server-bucketed via `classify_status` |
| `occupancy_percentage` | `vehicle:<id>:occupancy` | raw percentage |
| `congestion_level` | `run:<id>:congestion_level` | omitted when hash is absent |

Output file: `backend/feed/files/vehicle_positions.{pb,json}` — refreshed every 15 s.

### TripUpdate

Reports predicted arrival and departure times at upcoming stops for a trip.

Fields Databús® populates:

| Field | Source |
| --- | --- |
| `trip` | `run:<id>:trip` |
| `vehicle` | `vehicle:<id>:metadata` |
| `timestamp` | `vehicle:<id>:position.timestamp` |
| `stop_time_update[]` | `run:<id>:stop_time_updates` (JSON string) |

Each `StopTimeUpdate` entry contains `stop_sequence`, `stop_id`,
`arrival.time`, `departure.time`, and `uncertainty`. The projection is
written by the stop-times producer and expires with a staleness TTL. An absent
or empty projection results in an honest empty `stop_time_update` list in the
feed.

Output file: `backend/feed/files/trip_updates.{pb,json}` — refreshed every 15 s.

### ServiceAlert

!!! warning "Stub"
    The `build_alerts` Celery task (`backend/schedule_engine/tasks.py`) is
    currently a stub. It returns the string `"Feed ServiceAlert built"` and
    does not produce a real feed file. ServiceAlert emission is planned for a
    future release.

## Feed assembly

Both feeds are assembled by the `schedule_engine` app. The beat fires
`build_vehicle_positions` and `build_trip_updates` every 15 seconds, and
`build_alerts` every 10 seconds. The builders read the Redis snapshot via
the telemetry contract `from_redis` helpers, assemble a Python dict in GTFS-RT
shape, convert it with `json_format.ParseDict`, and write both `.json` and
`.pb` variants to `backend/feed/files/`.

See [Data flow › GTFS Realtime publishing](../data-flow/gtfs-rt-publishing.md)
for the full pipeline and
[Interfaces › GTFS Realtime feeds](../interfaces/gtfs-rt-feeds.md) for
consumer-facing details.

## External references

- [GTFS Schedule reference](https://gtfs.org/schedule/reference/)
- [GTFS Realtime reference](https://gtfs.org/realtime/reference/)
- [GTFS Realtime proto definition](https://github.com/google/transit/blob/master/gtfs-realtime/proto/gtfs-realtime.proto)
