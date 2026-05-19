# realtime_engine

Celery worker that processes lifecycle events and runs the MQTT telemetry consumer.

## MQTT consumer: management command approach

The MQTT consumer is implemented as a **Django management command** (`manage.py mqtt_consumer`)
started by a dedicated `realtime-consumer` compose service (see `compose.dev.yml`).

**Why not Celery bootsteps?**  
A Celery bootstep would start the MQTT loop inside the Celery worker process, mixing
telemetry I/O with task execution. Keeping them separate means the consumer can reconnect
cleanly without affecting the Celery worker pool, and scaling them independently is
straightforward (e.g. add more Celery workers without adding more MQTT connections).

## Topic subscriptions

```
transit/vehicle/+/position    QoS 0
transit/vehicle/+/progression QoS 0
transit/vehicle/+/occupancy   QoS 0
```

The `data` leaf (static metadata) is not subscribed here — vehicle metadata is written to
Redis by `RunLifecycleActions.update_system_state` when a run is initialized.

## Lifecycle events fired by the consumer

| Run state    | Trigger condition                          | Event fired             |
|--------------|--------------------------------------------|-------------------------|
| `Confirmed`  | Any valid ping received                    | `run_tracking_started`  |
| `Tracking`   | `position.speed > 0.5` m/s                | `run_started`           |
| `No Signal`  | Any valid ping received                    | `run_tracking_restored` |
| `In Progress`| `progression.current_status == STOPPED_AT` at terminal stop | `complete_run` |

## Stale run scanning

`scan_stale_runs` runs every 30 s via Celery Beat:

- `IN_PROGRESS` + staleness > 60 s → `run_tracking_lost`
- `NO_SIGNAL` + staleness > 300 s → `run_tracking_expired`
