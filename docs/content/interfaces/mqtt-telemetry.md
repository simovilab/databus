---
icon: lucide/radio
---

# MQTT Telemetry Contract

Vehicles (or simulators) publish telemetry to the NanoMQ broker. The
`realtime-engine` Celery worker subscribes to these topics via the
`MQTTConsumerStep` bootstep and ingests them into Redis.

Broker: **NanoMQ** at `telemetry-broker:1883` (internal) / `mqtt.<domain>:8883`
(TLS, production).

!!! note "Two producers, one topic contract"
    Position data reaches the `transit/vehicle/<id>/position` topic through
    two paths: devices/simulators that speak MQTT publish there directly, and
    devices that only expose an HTTP+JSON endpoint are polled every 10 s by
    the `fetch_positions` Celery task, which republishes what it fetches onto
    the same topic. Both paths converge on the single MQTT contract described
    below — see [HTTP polling ingestion path](#http-polling-ingestion-path)
    for how the second path works.

---

## Topic grammar

```
transit/vehicle/<vehicle_id>/<leaf>
```

| Segment | Description |
| --- | --- |
| `transit` | Fixed namespace prefix |
| `vehicle` | Fixed entity type |
| `<vehicle_id>` | String identifier matching `operations.Vehicle.id` |
| `<leaf>` | One of the supported data leaves |

The MQTT consumer uses `+` wildcard subscriptions:

```
transit/vehicle/+/position    QoS 0
transit/vehicle/+/occupancy   QoS 0
```

---

## Supported leaves

Only two leaves are actively subscribed. Any other leaf is silently dropped.

### `position`

Reports the vehicle's current GPS fix and motion data.

**Topic:** `transit/vehicle/<vehicle_id>/position`

**QoS:** 0 (at most once)

**Payload (JSON):**

```json
{
    "latitude": 9.9341,
    "longitude": -84.0875,
    "bearing": 45.0,
    "speed": 8.3,
    "odometer": 12350.5,
    "timestamp": 1718800000
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `latitude` | float | **Yes** | WGS-84 decimal degrees |
| `longitude` | float | **Yes** | WGS-84 decimal degrees |
| `bearing` | float | No | Degrees clockwise from true north |
| `speed` | float | No | Metres per second |
| `odometer` | float | No | Metres |
| `timestamp` | int | No | Unix epoch seconds of the GPS fix |

A message missing `latitude` or `longitude` is rejected and dropped. A message
with a valid position but an invalid optional field (e.g., non-numeric
`bearing`) is also rejected and dropped.

**Effect of a valid position message:**

1. `validate_for_write(data)` validates the payload.
2. `r.hset(vehicle:<id>:position, mapping=...)` writes the hash.
3. `process_position_update.delay(run_id, vehicle_id)` is enqueued for
   server-side processing (map-matching, detection, projections).
4. `r.set(runs:last_seen:<run_id>, now().isoformat())` is written synchronously.

---

### `occupancy`

Reports passenger load.

**Topic:** `transit/vehicle/<vehicle_id>/occupancy`

**QoS:** 0 (at most once)

**Payload (JSON):**

```json
{
    "occupancy_percentage": 65,
    "occupancy_count": 32
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `occupancy_percentage` | int | No | 0–100 |
| `occupancy_count` | int | No | Number of passengers |

!!! warning "Do not send `occupancy_status`"
    Any `occupancy_status` field in the payload is **discarded**. The server
    computes it from `occupancy_percentage` via `classify_status`. Sending a
    specific status value has no effect.

**Effect of a valid occupancy message:**

1. `occupancy_status` in the payload is stripped.
2. `classify_status(occupancy_percentage)` computes the server-policy enum value.
3. `validate_for_write(occ_payload)` validates the combined payload.
4. `r.hset(vehicle:<id>:occupancy, mapping=...)` writes the hash.
5. `r.set(runs:last_seen:<run_id>, now().isoformat())` is written synchronously.
6. `detect_from_telemetry(run_id, vehicle_id, "occupancy", data)` is called
   inline (not via the Celery queue) — occupancy detection is cheap and must
   fire lifecycle events immediately for tracking-start and restore detectors.

---

## HTTP polling ingestion path

Not every telemetry device exposes an MQTT publisher — some fleet-tracking
providers (e.g. NavSat-style endpoints) only expose an HTTP+JSON polling
endpoint. For those, `realtime_engine.tasks.fetch_positions`
(`backend/realtime_engine/tasks.py`) is a Celery Beat task, scheduled every
**10 seconds** (`fetch-positions` in `backend/databus/celery.py`, with
`expires=10` so a poll that couldn't even start within its own cycle is
revoked rather than queuing up behind a slow source), that:

1. Builds the in-service vehicle-id set from every `vehicle:<id>:current_run`
   key present in Redis — the same gate the MQTT consumer itself uses.
2. Queries `operations.Sensor` rows that are `status="ACTIVE"`,
   `provides_position=True`, and `source_type` in `["http", "both"]`.
3. Skips any sensor whose own `equipment.vehicle` is not in the in-service
   set (avoids paying the HTTP cost for out-of-service vehicles), then
   fetches the remaining sensors via the registered `"http"` adapter
   (`backend/realtime_engine/sources/http_json.py`), each call independently
   try/excepted so one failing source can't sink the poll.
4. Filters the fetched readings down to in-service vehicles again (a fleet
   endpoint can return many vehicles from a single sensor's URL, not just the
   one tied to that sensor's own equipment).
5. Publishes the survivors via `MqttPublisher.publish_batch`
   (`backend/realtime_engine/sources/publisher.py`) onto
   `transit/vehicle/<vehicle_id>/position`, QoS 0, not retained — **the exact
   same topic and payload shape** the MQTT consumer already subscribes to.

The task carries a `soft_time_limit=25` so one pathological source (a host
that hangs on every request) can't hold a worker slot indefinitely; on
`SoftTimeLimitExceeded` it logs the in-flight sensor and returns early
without publishing.

**HTTP+JSON adapter mapping:** a `Sensor` with `source_type="http"` (or
`"both"`) configures `source_http_url` and `source_json_mapping` — a small
schema of JSON-path mappings (`paths.lat`, `paths.lon`, optionally
`paths.speed`, `paths.odometer`, `paths.bearing`, `paths.timestamp`,
`paths.vehicle_id`) plus unit hints (`units.speed: "kmh"`,
`units.odometer: "km"`, converted to SI) and a timestamp format/timezone.
Only `lat`/`lon` are effectively required — a record that can't yield both is
skipped. If the mapping doesn't resolve a `vehicle_id`, the adapter falls
back to the sensor's own `equipment.vehicle`.

This path only ever produces `position` leaf messages — there is no HTTP
polling equivalent for `occupancy`.

Source: `backend/realtime_engine/tasks.py::fetch_positions`,
`backend/realtime_engine/sources/http_json.py`,
`backend/realtime_engine/sources/publisher.py`, `backend/databus/celery.py`.

---

## Routing: message dropped if no active run

Before processing any leaf, the consumer reads
`vehicle:<id>:current_run` from Redis. If that key is absent or empty, the
message is dropped with a `DEBUG` log. No telemetry is processed for vehicles
not currently assigned to an active run.

This prevents processing noise from vehicles that are off-duty, parked, or
whose run has already ended.

---

## Decommissioned leaf: `progression`

!!! warning "Not subscribed"
    `transit/vehicle/<vehicle_id>/progression` is **not** subscribed.
    The consumer does not subscribe to it. If a simulator or device publishes
    this topic, the NanoMQ broker may accept it, but the consumer will never
    receive it. Any such messages are effectively no-ops from Databús's
    perspective.

    Stop status is computed server-side via real GPS→polyline map-matching in
    `runs/domain/progression/compute.py`. The edge device does not need to — and
    must not — send progression data.

---

## Duplicate-consumer protection

Each consumer instance generates a unique MQTT `client_id`:

```
databus-mqtt-consumer-<hostname>-<pid>
```

A fixed `client_id` causes a second consumer process (e.g., a worker that
accidentally has `MQTT_CONSUMER_ENABLED=true`) to collide with the first on
the broker, triggering an endless reconnect war. The per-process client_id
makes such accidental duplicates non-catastrophic, though the single-consumer
gate (`MQTT_CONSUMER_ENABLED`) is the real guarantee.

Source: `backend/realtime_engine/mqtt.py::build_client`, commit `452d4f4`.

---

## Untrusted edge signal stance

All incoming MQTT data is treated as an untrusted signal. The server:

- Validates every payload before writing to Redis.
- Recomputes `occupancy_status` regardless of what the edge sends.
- Never trusts progression data from the edge (decommissioned).
- Drops messages for vehicles without an active run.

This prevents malformed or malicious telemetry from corrupting the operational
state or causing incorrect lifecycle events.

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `MQTT_CONSUMER_ENABLED` | `false` | Set `true` on the `realtime-engine` service only |
| `MQTT_HOST` | `telemetry-broker` | Broker hostname |
| `MQTT_PORT` | `1883` | Broker port |

See [Operations › Configuration](../operations/configuration.md) for the full
environment variable reference.
