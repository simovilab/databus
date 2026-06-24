---
icon: lucide/radio
description: MQTT topic grammar, payload schemas, and QoS contracts for vehicle telemetry ingestion into the NanoMQ broker.
---

# MQTT Telemetry Contract

Vehicles (or simulators) publish telemetry to the NanoMQ broker. The
`realtime-engine` Celery worker subscribes to these topics via the
`MQTTConsumerStep` bootstep and ingests them into Redis.

Broker: **NanoMQ** at `telemetry-broker:1883` (internal) / `mqtt.<domain>:8883`
(TLS, production).

---

## Topic grammar

```text
transit/vehicle/<vehicle_id>/<leaf>
```

| Segment | Description |
| --- | --- |
| `transit` | Fixed namespace prefix |
| `vehicle` | Fixed entity type |
| `<vehicle_id>` | String identifier matching `operations.Vehicle.id` |
| `<leaf>` | One of the supported data leaves |

The MQTT consumer uses `+` wildcard subscriptions:

```text
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
5. `detect_from_telemetry(run_id, vehicle_id, "occupancy", data)` is called
   inline (not via the Celery queue) — occupancy detection is cheap and must
   fire lifecycle events immediately for tracking-start and restore detectors.
6. `r.set(runs:last_seen:<run_id>, now().isoformat())` is written synchronously.

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

```text
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

---

## Copy-paste examples

### Publish a position update

```bash
mosquitto_pub -h localhost -p 1883 \
  -t 'transit/vehicle/vehicle-001/position' \
  -m '{"latitude": 9.9341, "longitude": -84.0875, "bearing": 45.0, "speed": 8.3, "odometer": 12350.5, "timestamp": 1718800000}'
```

### Publish an occupancy update

```bash
mosquitto_pub -h localhost -p 1883 \
  -t 'transit/vehicle/vehicle-001/occupancy' \
  -m '{"occupancy_percentage": 65, "occupancy_count": 32}'
```

Replace `vehicle-001` with the actual `operations.Vehicle.id`. Both topics require QoS 0. The vehicle must be assigned to an active run (via `POST /api/create-run/` + `run_confirmed_by_operator`) or the messages will be silently dropped.
