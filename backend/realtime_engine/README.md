# realtime_engine

Celery worker that processes lifecycle events and hosts the MQTT telemetry
consumer as an in-process bootstep.

## MQTT consumer: Celery bootstep approach

The MQTT consumer (`mqtt.py`) runs inside the realtime-engine worker as a
Celery `bootsteps.StartStopStep`. It starts when the worker boots and shuts
down when the worker shuts down. paho's `loop_start()` runs the network loop
in its own background thread, so it does not block Celery task execution.

The bootstep is registered globally in `databus/celery.py` but gated by the
`MQTT_CONSUMER_ENABLED` env var. Only the `realtime-engine` compose service
sets it to `true`; other workers (schedule-engine, beat) skip the bootstep so
the broker doesn't see duplicate subscribers.

**Why a bootstep instead of a separate service?**
The dedicated `realtime-consumer` service was an early choice that traded
operational simplicity for separation-of-concerns at a scale the demo doesn't
need. paho's network loop already runs in its own thread, so colocating it
with the Celery worker doesn't starve task execution. The bootstep avoids an
extra container, Dockerfile target, and bind-mount on the backend tree.

## Topic subscriptions

```
transit/vehicle/+/position    QoS 0
transit/vehicle/+/progression QoS 0
transit/vehicle/+/occupancy   QoS 0
```

The `data` leaf (static metadata) is not subscribed here — vehicle metadata is
written to Redis by `RunLifecycleActions.update_system_state` when a run is
initialized.

## Lifecycle events fired by the consumer

| Run state    | Trigger condition                                         | Event fired             |
|--------------|-----------------------------------------------------------|-------------------------|
| `Confirmed`  | Any valid ping received                                   | `run_tracking_started`  |
| `Tracking`   | `position.speed > 0.5` m/s                                | `run_started`           |
| `No Signal`  | Any valid ping received                                   | `run_tracking_restored` |
| `In Progress`| `progression.current_status == STOPPED_AT` with `stop_id` | `complete_run`          |

## Stale run scanning

`scan_stale_runs` runs every 30 s via Celery Beat:

- `IN_PROGRESS` + staleness > 60 s → `run_tracking_lost`
- `NO_SIGNAL` + staleness > 300 s → `run_tracking_expired`

## Environment variables

| Var                     | Default            | Purpose                                                       |
|-------------------------|--------------------|---------------------------------------------------------------|
| `MQTT_CONSUMER_ENABLED` | `false`            | Master switch; set `true` only on the realtime-engine worker. |
| `MQTT_HOST`             | `telemetry-broker` | Broker hostname (resolved inside compose).                    |
| `MQTT_PORT`             | `1883`             | Broker port.                                                  |
| `REDIS_HOST`            | `state`            | Redis hostname.                                               |
| `REDIS_PORT`            | `6379`             | Redis port.                                                   |
