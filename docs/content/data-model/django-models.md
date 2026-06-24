---
icon: lucide/box
description: Django ORM models for Databús — the Run entity, RunLifecycleTransition audit log, RunProgressEvent, and all operations, feed, and GTFS Realtime persistence models.
---

# Django Models

Databús persists durable domain data in PostgreSQL via Django ORM. The
following apps each own their model layer. All apps live under `backend/`.

---

## `runs` app — `backend/runs/models.py`

### `Run`

The central domain entity. One row per real-world trip execution.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `UUIDField` (primary key) | Auto-generated with `uuid.uuid7` |
| `vehicle` | `ManyToManyField(Vehicle)` | Typically one vehicle per run |
| `operator` | `ManyToManyField(Operator)` | Typically one operator per run |
| `route_id` | `CharField` | GTFS route_id |
| `trip_id` | `CharField` | GTFS trip_id |
| `direction_id` | `PositiveSmallIntegerField` | GTFS direction_id |
| `shape_id` | `CharField` | GTFS shape_id |
| `request_timestamp` | `DateTimeField` | Auto-set at creation |
| `start_date` | `DateField` | Service date |
| `start_time` | `DurationField` | Scheduled start time |
| `schedule_relationship` | `CharField` | SCHEDULED / ADDED / UNSCHEDULED / CANCELED / DUPLICATED / DELETED |
| `run_lifecycle_state` | `CharField` | Current FSM state; choices from `RunLifecycleStates` |
| `last_event_at` | `DateTimeField` | Timestamp of last lifecycle transition |

The `run_lifecycle_state` field mirrors the in-memory state. On run creation
it defaults to `RunLifecycleStates.REQUESTED`. The lifecycle service updates
it on every FSM transition.

### `RunLifecycleTransition`

Immutable audit record written by the lifecycle service before any external
side-effect. Because it is written before actions run, the log is authoritative
even if a downstream action later fails. For the full state and event set, see [run lifecycle states](../runs/lifecycle-states.md).

| Field | Notes |
| --- | --- |
| `id` | UUID7 primary key |
| `run` | ForeignKey to `Run` (CASCADE) |
| `event_name` | Event string (e.g., `run_confirmed_by_operator`) |
| `from_state` | State before transition |
| `to_state` | State after transition |
| `guards` | JSONField — results of guard checks |
| `actions` | JSONField — results of actions executed |
| `timestamp` | Logical event time |
| `created_at` | Row insertion time |

Indexed on `(run, timestamp)` and `event_name`.

The `GET /api/runs/<id>/history/` endpoint returns this log ordered by
`(timestamp, created_at)`.

### `RunProgressEvent`

Records stop-level progress events (vehicle arrived at stop, departed, etc.)
for analytics. See the [Progress FSM](../runs/progress-fsm.md) for the motion-state design intent.

| Field | Notes |
| --- | --- |
| `run` | ForeignKey to `Run` |
| `event_type` | String event type |
| `stop_id` | GTFS stop_id (nullable) |
| `payload` | JSONField |
| `timestamp` | Event time |

### `Position`, `VehicleStopStatus`, `CongestionLevel`, `OccupancyStatus`

Normalized GTFS-RT entity records for durable persistence and analytics.
Written by the realtime-engine after processing. These are separate from the
Redis keys — Redis holds the *live* snapshot; these models hold the
*historical trace*.

---

## `operations` app — `backend/operations/models.py`

Operational domain: companies, operators, vehicles, equipment.

### `Company`

Wrapper for a transit agency. Linked one-to-one to a `feed.Agency`.

| Field | Notes |
| --- | --- |
| `id` | CharField primary key |
| `linked_agency` | OneToOneField to `feed.Agency` |
| `name`, `description`, `phone`, `email`, `website` | Contact info |
| `location` | PointField |

### `Operator`

A person who drives or dispatches runs. Linked one-to-one to a Django `User`.

| Field | Notes |
| --- | --- |
| `id` | CharField primary key |
| `user` | OneToOneField to `auth.User` |
| `company` | ManyToManyField to `Company` |
| `phone`, `photo` | Contact info |

### `Vehicle`

A physical vehicle that can be assigned to a run.

| Field | Notes |
| --- | --- |
| `id` | CharField primary key |
| `company` | ForeignKey to `Company` |
| `label` | Human-readable identifier |
| `license_plate` | Plate number |
| `wheelchair_accessible` | Enum (NO_VALUE / UNKNOWN / WHEELCHAIR_ACCESIBLE / WHEELCHAIR_INACCESIBLE) |

### `DataProvider`, `Equipment`, `EquipmentLog`

Support models for on-board equipment registration and telemetry source
tracking.

---

## `feed` app — `backend/feed/models.py`

GTFS Schedule data imported from agency feeds, plus GTFS-RT persistence
models.

### GTFS Schedule models

All extend abstract base classes from the `gtfs` submodule:

| Model | Extends | GTFS file |
| --- | --- | --- |
| `Agency` | `BaseAgency` | `agency.txt` |
| `Stop` | `BaseStop` | `stops.txt` |
| `Route` | `BaseRoute` | `routes.txt` |
| `Calendar` | `BaseCalendar` | `calendar.txt` |
| `CalendarDate` | `BaseCalendarDate` | `calendar_dates.txt` |
| `Shape` | `BaseShape` | `shapes.txt` |
| `Trip` | `BaseTrip` | `trips.txt` |
| `StopTime` | `BaseStopTime` | `stop_times.txt` |
| `FareAttribute` | `BaseFareAttribute` | `fare_attributes.txt` |
| `FareRule` | `BaseFareRule` | `fare_rules.txt` |
| `FeedInfo` | `BaseFeedInfo` | `feed_info.txt` |

All are scoped to a `Feed` (identified by `feed_id`) via a ForeignKey. The
`is_current` flag on `Feed` identifies the active dataset.

Additional Databús-specific models:

| Model | Purpose |
| --- | --- |
| `GeoShape` | PostGIS `LineStringField` geometry for route shapes — used by map-matching |
| `RouteStop` | Stop sequence per route + shape + direction |
| `TripDuration` | Trip duration metadata for scheduling |
| `TripTime` | Departure times at timepoints (for the run-scheduling UI) |
| `GTFSProvider` | Registry of GTFS data providers and feed URLs |

### GTFS Realtime persistence models

| Model | Maps to |
| --- | --- |
| `FeedMessage` | GTFS-RT FeedMessage header |
| `VehiclePosition` | Normalized VehiclePosition entity |
| `TripUpdate` | Normalized TripUpdate entity |
| `StopTimeUpdate` | Normalized StopTimeUpdate per TripUpdate |
| `Alert` | Draft Alert model (TODO: align with GTFS-RT Alert schema) |

---

## Management commands

`update_foreign_keys` — repairs FK links in `feed` models after a bulk import
(e.g., after `loaddata gtfs.json`). Run it if FK integrity errors appear after
a feed import.
