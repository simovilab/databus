---
icon: lucide/cpu
description: Celery worker topology, queue routing, beat schedule, and Flower monitoring for the realtime-engine and schedule-engine workers.
---

# Celery workers, queues & beat

Databús runs three Celery processes: two workers consuming different queues, and one beat scheduler. This page describes their roles, queue routing, and the beat schedule.

## Worker topology

```text
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│  realtime-engine (worker)           │  │  schedule-engine (worker)           │
│  queue: realtime_engine             │  │  queue: schedule_engine             │
│                                     │  │                                     │
│  Tasks:                             │  │  Tasks:                             │
│  • process_position_update          │  │  • build_vehicle_positions          │
│  • run_lifecycle_event              │  │  • build_trip_updates               │
│  • scan_stale_runs                  │  │  • build_alerts                     │
│                                     │  │                                     │
│  Bootstep: MQTTConsumerStep         │  │  No bootstep active                 │
│  (gated by MQTT_CONSUMER_ENABLED)   │  │                                     │
└─────────────────────────────────────┘  └─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  scheduler (Celery beat)            │
│  Fires periodic tasks on schedule   │
│  No task execution, no queues       │
└─────────────────────────────────────┘
```

All three processes load `backend/databus/celery.py` as the Celery app. The queue each task lands on is declared via the `queue=` argument to `@shared_task`.

## Queue routing

| Queue | Consumed by | Tasks |
|---|---|---|
| `realtime_engine` | `realtime-engine` worker | `process_position_update`, `run_lifecycle_event`, `scan_stale_runs` |
| `schedule_engine` | `schedule-engine` worker | `build_vehicle_positions`, `build_trip_updates`, `build_alerts` |

Queue separation ensures that a spike in MQTT telemetry (many `process_position_update` tasks) does not starve GTFS-RT building tasks, and vice versa.

## The MQTT consumer bootstep

The `MQTTConsumerStep` bootstep is registered globally in `databus/celery.py`:

```python
from realtime_engine.mqtt import MQTTConsumerStep
app.steps["worker"].add(MQTTConsumerStep)
```

This registers the step on **every** worker that loads the Celery app. The step checks `MQTT_CONSUMER_ENABLED` at startup and only activates on the `realtime-engine` worker. Other workers log a single `INFO` line and skip activation.

See [Telemetry ingestion](../data-flow/telemetry-ingestion.md) for the full bootstep description.

## Beat schedule

The beat schedule is defined **in code** in `backend/databus/celery.py`, not in the `django_celery_beat` database admin.

!!! warning "Beat schedule is not in the Django admin"
    `AGENTS.md` suggests that schedules are managed through `django_celery_beat` and the Django admin. This is incorrect. The schedule is static, defined in `app.conf.beat_schedule` in `databus/celery.py`. To change a cadence, edit that file and redeploy the `scheduler` service.

```python
app.conf.beat_schedule = {
    "build-vehicle-positions-every-15s": {
        "task": "schedule_engine.tasks.build_vehicle_positions",
        "schedule": timedelta(seconds=15),
    },
    "build-trip-updates-every-15s": {
        "task": "schedule_engine.tasks.build_trip_updates",
        "schedule": timedelta(seconds=15),
    },
    "build-alerts-every-10s": {
        "task": "schedule_engine.tasks.build_alerts",
        "schedule": timedelta(seconds=10),
    },
    "scan-stale-runs-every-30s": {
        "task": "realtime_engine.tasks.scan_stale_runs",
        "schedule": timedelta(seconds=30),
    },
}
```

| Entry | Task | Queue | Cadence | Purpose |
|---|---|---|---|---|
| `build-vehicle-positions-every-15s` | `build_vehicle_positions` | `schedule_engine` | 15 s | Rebuild `vehicle_positions.{pb,json}` |
| `build-trip-updates-every-15s` | `build_trip_updates` | `schedule_engine` | 15 s | Rebuild `trip_updates.{pb,json}`, push WebSocket heartbeat |
| `build-alerts-every-10s` | `build_alerts` | `schedule_engine` | 10 s | Stub — returns a string, writes no file |
| `scan-stale-runs-every-30s` | `scan_stale_runs` | `realtime_engine` | 30 s | Detect `run_tracking_lost` / `run_tracking_expired` |

## Celery task monitoring: Flower

The `task-monitoring` compose service runs [Flower](https://flower.readthedocs.io/), a real-time Celery dashboard.

| Environment | URL |
|---|---|
| Development | http://localhost:5555 |
| Production | `https://${FLOWER_DOMAIN}` (e.g. `https://tasks.databus.simovilab.com`) |

Flower connects to RabbitMQ and shows:

- Active, scheduled, and reserved tasks per worker.
- Task history with arguments, result, and execution time.
- Worker status and queue depths.

## Compose service → Celery process mapping

| Compose service | Celery command | Build target |
|---|---|---|
| `realtime-engine` | `celery -A databus worker -Q realtime_engine -l info` | `realtime-engine` |
| `schedule-engine` | `celery -A databus worker -Q schedule_engine -l info` | `schedule-engine` |
| `scheduler` | `celery -A databus beat -l info` | `scheduler` |

Build targets are defined in `backend/Dockerfile`. Each target installs the same Python environment but sets a different `CMD`.

## Related pages

- [Telemetry ingestion](../data-flow/telemetry-ingestion.md) — the `MQTTConsumerStep` bootstep.
- [Server-side processing](../data-flow/server-processing.md) — `process_position_update` in detail.
- [GTFS Realtime publishing](../data-flow/gtfs-rt-publishing.md) — the `schedule_engine` tasks.
- [Stale-run scanning](../runs/stale-runs.md) — `scan_stale_runs` logic.
- [Configuration & env vars](configuration.md) — `MQTT_CONSUMER_ENABLED` and related settings.
