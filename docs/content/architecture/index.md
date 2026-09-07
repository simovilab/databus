---
icon: lucide/network
---

# Architecture

Databús is a distributed transit data platform composed of Django apps and Celery workers, all deployed as Docker Compose services. The sections below unpack the system from every angle.

```mermaid
flowchart TD
    subgraph Ingestion
        api([REST API])
        mqtt_in([MQTT])
    end

    subgraph Brokers
        telemetry_broker(("telemetry-broker\n(NanoMQ)"))
        message_broker(("message-broker\n(RabbitMQ)"))
    end

    subgraph Django["orchestrator (Django)"]
        direction TB
        api_app[api]
        runs_app[runs]
        schedule_engine_app[schedule_engine]
        feed_app[feed]
        ops_app[operations]
        website_app[website]
        messages_app[messages]
    end

    subgraph realtime_worker["realtime-engine (Celery worker)"]
        mqtt_bootstep[MQTT bootstep]
        re_tasks[process_position_update\nrun_lifecycle_event\nscan_stale_runs\nfetch_positions]
    end

    subgraph schedule_worker["schedule-engine (Celery worker)"]
        se_tasks[build_vehicle_positions\nbuild_trip_updates\nbuild_schedule]
    end

    scheduler_node(("scheduler\n(Celery Beat)"))

    subgraph State
        redis_node(("state\n(Redis)"))
    end

    subgraph Persistence
        pg_node(("database\n(PostgreSQL/PostGIS)"))
    end

    subgraph Outputs
        gtfs_rt[/GTFS-RT files/]
        ws[/WebSocket/]
    end

    analytics_engine(("analytics-engine\n(Prefect)"))
    flower(("task-monitoring\n(Flower)"))

    api --> Django
    mqtt_in --> telemetry_broker
    telemetry_broker -- MQTT --> mqtt_bootstep
    mqtt_bootstep --> re_tasks
    re_tasks -- "HSET" --> redis_node
    re_tasks -- "lifecycle events" --> message_broker
    Django -- "ORM" --> pg_node
    Django -- "commands" --> message_broker
    message_broker -- "tasks" --> realtime_worker
    message_broker -- "tasks" --> schedule_worker
    scheduler_node --> message_broker
    redis_node -- "snapshots" --> se_tasks
    se_tasks --> gtfs_rt
    se_tasks --> ws
    pg_node --> analytics_engine
    message_broker --> flower
```

| Page | What it covers |
|---|---|
| [System overview](overview.md) | Six-layer model: Ingestion → Projection |
| [Services & mandates](services.md) | Per-service role, responsibilities, and boundaries |
| [Messaging model](messaging.md) | Commands, observations, assertions; AMQP exchange layout |
| [State & persistence](state-and-persistence.md) | Redis (authoritative) vs PostgreSQL (durable) |
| [Deployment topology](deployment-topology.md) | Compose services, queue routing, dev vs prod |
