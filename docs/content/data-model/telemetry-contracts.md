---
icon: lucide/file-check
description: Typed telemetry contract modules for every Redis key — validate_for_write (strict ingestion) and from_redis (tolerant reads) for position, occupancy, trip, vehicle_stop_status, congestion_level, and stop_time_updates.
---

# Telemetry Contracts

Every Redis key that carries telemetry data has a **contract module** in
`backend/runs/domain/telemetry/`. A contract module defines:

- Field-name constants (no other module hardcodes field strings).
- `validate_for_write(payload: dict) -> dict[str, str]` — strict; raises
  `ValueError` on bad input; returns a Redis-ready `{field: str}` mapping.
- `from_redis(hash: dict) -> dict` — tolerant; absent keys are omitted; bad
  optional values are silently dropped; bad required values raise `ValueError`.

This two-sided contract enforces a clean boundary: the ingestion path is
strict (garbage in → rejection), and the read path is tolerant (partial data
in Redis → partial entity in the feed, not a crash).

No contract module imports Django or Redis — they are safe to import from any
layer.

---

## `position` — `vehicle:<id>:position`

Module: `backend/runs/domain/telemetry/position.py`

Redis type: **Hash**

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `latitude` | `float` | Yes | Raised from both required fields if non-coercible |
| `longitude` | `float` | Yes | |
| `bearing` | `float` | No | Optional; dropped if non-coercible on read |
| `speed` | `float` | No | |
| `odometer` | `float` | No | |
| `timestamp` | `int` | No | Unix epoch seconds; lifted to VP level by the feed builder |

`validate_for_write`: raises `ValueError` for missing or non-coercible required
fields; raises `ValueError` for present-but-non-coercible optional fields
(strict on write).

`from_redis`: tolerant — silently drops bad optional values; raises `ValueError`
only if a present required field cannot be coerced to float.

---

## `occupancy` — `vehicle:<id>:occupancy`

Module: `backend/runs/domain/telemetry/occupancy.py`

Redis type: **Hash**

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `occupancy_status` | `str` (enum) | Yes | Must be one of the 9 valid GTFS values |
| `occupancy_percentage` | `int` | No | |
| `occupancy_count` | `int` | No | Not emitted in GTFS-RT feed (no such field on VehiclePosition) |

**Valid `occupancy_status` values** (from `occupancy.VALID_STATUSES`):

```text
EMPTY, MANY_SEATS_AVAILABLE, FEW_SEATS_AVAILABLE, STANDING_ROOM_ONLY,
CRUSHED_STANDING_ROOM_ONLY, FULL, NOT_ACCEPTING_PASSENGERS,
NO_DATA_AVAILABLE, NOT_BOARDABLE
```

!!! warning "Edge value discarded"
    The MQTT consumer overwrites any edge-sent `occupancy_status` with the
    result of `classify_status(occupancy_percentage)` before calling
    `validate_for_write`. The edge cannot control this field; bucketing is
    a server policy.

`classify_status(percentage: int | None) -> str`:

| `percentage` | Result |
| --- | --- |
| `None` | `NO_DATA_AVAILABLE` |
| `< 20` | `MANY_SEATS_AVAILABLE` |
| `< 50` | `FEW_SEATS_AVAILABLE` |
| `< 80` | `STANDING_ROOM_ONLY` |
| `>= 80` | `FULL` |

`from_redis`: tolerant on read — passes through whatever `occupancy_status`
string is in Redis without re-validating the enum.

---

## `trip` — `run:<id>:trip`

Module: `backend/runs/domain/telemetry/trip.py`

Redis type: **Hash**

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `trip_id` | `str` | Yes | |
| `route_id` | `str` | Yes | |
| `direction_id` | `int` | No | |
| `schedule_relationship` | `str` | No | |
| `start_time` | `str` | No | HH:MM:SS |
| `start_date` | `str` | No | YYYYMMDD |

Producer: lifecycle action (`runs/domain/lifecycle/actions.py`). The action
calls `project_from_run_hash(run_hash)` to extract the TripDescriptor subset
from the flat `run:<id>` hash and writes it with one `HSET` call.

The feed builder defaults `schedule_relationship` to `SCHEDULED` when the
field is absent.

---

## `vehicle_stop_status` — `run:<id>:vehicle_stop_status`

Module: `backend/runs/domain/telemetry/vehicle_stop_status.py`

Redis type: **Hash**

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `current_status` | `str` (enum) | Yes | `INCOMING_AT`, `STOPPED_AT`, `IN_TRANSIT_TO` |
| `current_stop_sequence` | `int` | No | |
| `stop_id` | `str` | No | |

Producer: server progression step (`runs/domain/progression/compute.py`) — the
result of projecting GPS onto the trip's polyline and applying haversine
distance rules against stop coordinates. This key is never written by the
edge.

The `RunCompletedDetector` reads `current_status` from this hash to trigger
the `run_completed` event when `STOPPED_AT` is detected at a terminal stop.

---

## `congestion_level` — `run:<id>:congestion_level`

Module: `backend/runs/domain/telemetry/congestion_level.py`

Redis type: **Hash**

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `congestion_level` | `str` (enum) | Yes (for write) | |

**Valid values**: `UNKNOWN_CONGESTION_LEVEL`, `RUNNING_SMOOTHLY`, `STOP_AND_GO`,
`CONGESTION`, `SEVERE_CONGESTION`.

!!! note "Deferred — no active producer"
    The module is defined for consistency and so feed builders can safely
    attempt `r.hgetall(keys.congestion_key(run_id))` without knowing whether
    the hash exists. The `from_redis` implementation returns `{}` when the
    hash is absent. No producer writes this key yet.

---

## `stop_time_updates` — `run:<id>:stop_time_updates`

Module: `backend/runs/domain/telemetry/stop_time_updates.py`

Redis type: **String** (JSON-encoded array)

!!! warning "String, not hash"
    Unlike all other telemetry keys, this is a Redis **string** key. Use
    `r.get(key)` to read it, not `r.hgetall(key)`.

**Per-entry schema** (each element of the JSON array):

| Field | Python type | Required | Notes |
| --- | --- | --- | --- |
| `stop_sequence` | `int` | Yes | |
| `stop_id` | `str` | Yes | Must be non-empty |
| `arrival_time` | `int` | Yes | POSIX seconds |
| `departure_time` | `int` | Yes | POSIX seconds (equals `arrival_time` currently) |
| `uncertainty` | `int` | Yes | Seconds |

`from_redis(raw_json: str | None) -> list[dict]`: tolerant — returns `[]` on
`None`, empty string, malformed JSON, or non-list JSON values. Entries missing
any required field are silently dropped.

`to_redis(entries: list[dict]) -> str`: strict — raises `ValueError` on the
first bad entry. Returns a JSON string ready for `r.set(key, ...)`.

Producer: `runs/domain/progression/stop_times.py`. Written with a staleness
TTL; an expired key causes the feed builder to emit an empty
`stop_time_update` list (honest rather than stale).

---

## Contract usage pattern

```python
# Write path (strict)
from runs.domain.telemetry import position, keys

mapping = position.validate_for_write(payload)   # raises ValueError on bad input
r.hset(keys.position_key(vehicle_id), mapping=mapping)

# Read path (tolerant)
raw = r.hgetall(keys.position_key(vehicle_id))
pos = position.from_redis(raw)                   # silently drops bad optionals
lat = pos.get("latitude")                        # None if absent
```

See [Data flow › Telemetry ingestion](../data-flow/telemetry-ingestion.md) for
the full write-path pipeline, and [GTFS Realtime feeds](../interfaces/gtfs-rt-feeds.md)
for the read-path feed assembly.
