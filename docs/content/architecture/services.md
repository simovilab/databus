---
icon: lucide/server
---

# Services & mandates

Every Databús component has exactly one role and a hard "Does NOT" boundary. This page is the authoritative corrected service map — it supersedes the stale descriptions in `AGENTS.md` and `MODEL.md` wherever they disagree with the code.

!!! warning "Stale docs correction"
    `AGENTS.md` describes separate `realtime-engine/`, `publisher/`, and `scheduler/` Python projects. Those top-level directories do not exist. Everything runs as Django apps inside `backend/` and Celery workers launched from that same Django project. The sections below reflect the compose services as they actually run.

---

## orchestrator

**Role:** Control plane and domain authority.

**Process:** Django + Daphne ASGI server. Exposes HTTP and WebSocket.

**Django apps loaded:**

- `api` — DRF REST endpoints for run commands and telemetry reads.
- `runs` — Run domain models, lifecycle FSM service, detection domain.
- `schedule_engine` — GTFS Schedule query layer and GTFS-RT builder task definitions.
- `feed` — GTFS data models (Agency, Route, Trip, Stop, StopTime, Shape, Calendar).
- `operations` — Vehicle and operator models.
- `website` — UI-facing views.
- `messages` — AMQP event publisher (see caveat below).
- `gtfs` — GTFS submodule.

**Responsibilities:**

- Validates and records run lifecycle commands from the REST API.
- Drives the `RunLifecycleService` (which executes FSM transitions synchronously on the HTTP thread for commands).
- Persists domain data and lifecycle state in PostgreSQL via Django ORM.
- Exposes DRF token auth, admin, and OpenAPI docs at `/api/docs/`.
- Sends WebSocket heartbeats via Django Channels after each GTFS-RT rebuild.

**Does NOT:**

- Process raw MQTT telemetry.
- Perform map-matching or stop-status computation.
- Write vehicle telemetry to Redis.

**Emits:** Commands (REST → lifecycle service → FSM actions → Redis/DB).

**Consumes:** REST requests, WebSocket connections.

---

## realtime-engine

**Role:** Real-time reasoning, telemetry ingestion, and lifecycle event processing.

**Process:** Celery worker draining queue `realtime_engine`. Also hosts the MQTT consumer as an in-process Celery bootstep (`realtime_engine/mqtt.py`, class `MQTTConsumerStep`).

**Source:** `backend/realtime_engine/`

**Responsibilities:**

- Subscribes to `transit/vehicle/+/position` and `transit/vehicle/+/occupancy` on NanoMQ (QoS 0) via the bootstep. The `progression` leaf is **not** subscribed — progression is computed server-side.
- Validates each incoming MQTT message against the telemetry contract and writes it to Redis (`vehicle:<id>:position` or `:occupancy`).
- Updates `runs:last_seen:<run_id>` on every message.
- Enqueues `process_position_update(run_id, vehicle_id)` for heavy work off the paho network thread.
- `process_position_update` runs in four steps:
    1. Server-side stop-status production via `runs.domain.progression.producer.produce_stop_status` (real GPS→polyline map-matching in `compute.py`).
    2. Feeds the computed `vehicle_stop_status` into `detect_from_telemetry` with leaf `"progression"` for completion detection.
    3. Computes and caches the `stop_time_updates` projection.
    4. Re-reads the latest position from Redis and runs position-leaf detection (`RunStartedDetector`, etc.).
- Processes `run_lifecycle_event(event, payload)` tasks — these call `RunLifecycleService.process_event` which executes FSM guards and actions.
- Runs `scan_stale_runs` every 30 seconds (scheduled by the `scheduler`) to detect telemetry silence.

**Does NOT:**

- Serve HTTP.
- Build GTFS-RT feeds.
- Own domain schemas.

**Queue:** `realtime_engine`

**Key tasks** (`backend/realtime_engine/tasks.py`):
- `process_position_update(run_id, vehicle_id)`
- `run_lifecycle_event(event, payload)`
- `scan_stale_runs()`

---

## schedule-engine

**Role:** GTFS Realtime feed projection.

**Process:** Celery worker draining queue `schedule_engine`.

**Source:** `backend/schedule_engine/`

**Responsibilities:**

- Reads Redis snapshots of active runs and vehicles.
- Builds GTFS-RT protobuf and JSON outputs for VehiclePositions, TripUpdates, and Alerts.
- Writes output files to `backend/feed/files/` (`vehicle_positions.{pb,json}`, `trip_updates.{pb,json}`, `alerts.{pb,json}`).
- Pushes a WebSocket `"status"` group message via Django Channels after each `build_trip_updates` call.

**Does NOT:**

- Write to Redis.
- Modify lifecycle state.
- Process MQTT messages.

**Queue:** `schedule_engine`

**Key tasks** (`backend/schedule_engine/tasks.py`):
- `build_vehicle_positions()` — every 15 s
- `build_trip_updates()` — every 15 s
- `build_alerts()` — every 10 s (currently stub: returns `"Feed ServiceAlert built"`)

!!! note "AGENTS.md calls this the 'Publisher'"
    `ARCHITECTURE.md §5` and `AGENTS.md` describe a separate "Publisher" service. In the actual code the projection role is fulfilled by `schedule_engine` running inside the `schedule-engine` Celery worker. There is no standalone publisher process.

---

## scheduler

**Role:** Temporal orchestration (Celery Beat).

**Process:** `celery beat` launched from the `backend/databus/celery.py` app.

**Responsibilities:**

- Fires the four periodic tasks on the configured schedule.

**Beat schedule** (defined in `backend/databus/celery.py`):

| Task | Interval |
|---|---|
| `schedule_engine.tasks.build_vehicle_positions` | every 15 s |
| `schedule_engine.tasks.build_trip_updates` | every 15 s |
| `schedule_engine.tasks.build_alerts` | every 10 s |
| `realtime_engine.tasks.scan_stale_runs` | every 30 s |

!!! note "Beat schedule is in code, not admin"
    `AGENTS.md` states that the beat schedule is managed via `django_celery_beat` in the admin UI. This is incorrect. The schedule is hardcoded in `app.conf.beat_schedule` in `backend/databus/celery.py` and requires a code change to modify.

---

## state (Redis)

**Role:** Authoritative real-time operational state.

**Image:** `redis:7-alpine`

**Single writer rule:** `realtime-engine` is the sole writer. `schedule-engine` reads snapshots. `orchestrator` writes lifecycle state hash fields via FSM actions.

**Does NOT:**

- Persist historical data.
- Apply business logic.

See [state-and-persistence.md](state-and-persistence.md) and [../data-model/redis-keys.md](../data-model/redis-keys.md).

---

## database (PostgreSQL + PostGIS)

**Role:** Durable domain storage and operational history.

**Image:** Custom build on `postgis/postgis`.

**Contents:**

- Domain records: runs, vehicles, operators, GTFS schedule data.
- Run lifecycle events and state transitions.
- GTFS-RT blobs (retained ~1 year).

---

## telemetry-broker (NanoMQ)

**Role:** MQTT broker for vehicle telemetry.

**Image:** `emqx/nanomq:0.24.9-full`

**Topics served:** `transit/vehicle/+/{position,occupancy}` (QoS 0, no retained messages for telemetry).

In production, Traefik terminates TLS on port 8883 and forwards plain MQTT to NanoMQ on port 1883.

---

## message-broker (RabbitMQ)

**Role:** Celery task queue and AMQP event bus.

**Image:** `rabbitmq:4-management`

**Primary use:** Celery task routing between `scheduler`, `realtime-engine`, and `schedule-engine`.

**Designed use (not yet implemented):** AMQP domain events on exchange `databus.events`. See [messaging.md](messaging.md).

---

## analytics-engine (Prefect)

**Role:** Batch analytics and modeling.

**Image:** `prefecthq/prefect:3-latest`

Operationally independent of the real-time path. Consumes PostgreSQL batch data.

---

## task-monitoring (Flower)

**Role:** Celery task observability dashboard.

**Image:** `mher/flower:2.0`

Connects to RabbitMQ via AMQP. Exposed at `tasks.<domain>` in production.

---

## user-interface (Nuxt)

**Role:** Web frontend for dispatchers and operators.

**Image:** Built from `frontend/Dockerfile`.

Communicates with `orchestrator` via REST and WebSocket.

---

## docs (production only)

**Role:** Serve the built Zensical static site.

**Image:** `nginx:alpine`, serving `docs/site/`.

Only present in `compose.prod.yml`. Not included in the dev compose.
