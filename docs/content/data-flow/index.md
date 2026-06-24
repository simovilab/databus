---
icon: lucide/activity
description: End-to-end data flow from vehicle MQTT telemetry through Redis state, Celery processing, and GTFS-RT file publishing to WebSocket clients.
---

# Data flow

Databús® moves data through five sequential stages, from raw vehicle telemetry to published GTFS Realtime feeds and live WebSocket updates. Each stage is handled by a specific service and the hand-off between stages is always explicit — either an MQTT message, a Celery task, or a Redis write.

```mermaid
sequenceDiagram
    autonumber
    participant V as Vehicle / Simulator
    participant B as NanoMQ (telemetry-broker)
    participant M as MQTTConsumerStep<br/>(realtime-engine worker)
    participant R as Redis (state)
    participant C as process_position_update<br/>(realtime-engine queue)
    participant P as progression/producer.py
    participant S as schedule_engine tasks<br/>(schedule-engine queue)
    participant F as feed/files/
    participant W as WebSocket clients

    Note over V,W: A day in the life of a run

    V->>B: MQTT publish<br/>transit/vehicle/42/position QoS 0
    B->>M: on_message callback
    M->>M: validate payload,<br/>look up vehicle:42:current_run
    M->>R: HSET vehicle:42:position
    M->>R: SET runs:last_seen:<run_id>
    M->>C: process_position_update.delay(run_id, vehicle_id)

    Note over C,P: Off network thread (Celery task)
    C->>R: re-read vehicle:42:position
    C->>P: produce_stop_status(run_id, vehicle_id)
    P->>R: HSET run:<id>:vehicle_stop_status
    C->>R: write run:<id>:stop_time_updates (JSON, TTL 60 s)
    C->>C: detect_from_telemetry (position leaf)

    Note over S,W: Celery Beat fires every 15 s
    S->>R: smembers("runs:in_progress")
    S->>R: read all entity hashes
    S->>F: write vehicle_positions.{pb,json}
    S->>F: write trip_updates.{pb,json}
    S->>W: channel_layer.group_send("status", …)
```

| Page | What it covers |
|---|---|
| [Telemetry ingestion](telemetry-ingestion.md) | MQTT consumer bootstep, topic subscriptions, per-leaf pipeline |
| [Server-side processing](server-processing.md) | `process_position_update` Celery task and its four steps |
| [Map-matching & progression](map-matching.md) | GPS→polyline projection, three-state radius rules, monotonic guard |
| [GTFS Realtime publishing](gtfs-rt-publishing.md) | Beat schedule, builders, output files |
| [Live updates (WebSocket)](live-updates.md) | Django Channels `status` group and frontend heartbeat |
