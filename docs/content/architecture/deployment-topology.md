---
icon: lucide/layers-3
---

# Deployment topology

Databús runs entirely in Docker Compose. Two compose files share the same service names and images but differ in process targets, networking, and TLS.

## Compose services summary

| Service | Process | Queue / port | Notes |
|---|---|---|---|
| `orchestrator` | Django + Daphne ASGI | :8000 | HTTP + WebSocket |
| `realtime-engine` | `celery worker -Q realtime_engine` | `realtime_engine` | Hosts MQTT bootstep |
| `schedule-engine` | `celery worker -Q schedule_engine` | `schedule_engine` | GTFS-RT projection |
| `scheduler` | `celery beat` | — | Fires periodic tasks |
| `state` | Redis 7 | :6379 | Authoritative state |
| `database` | PostgreSQL + PostGIS | :5432 | Domain storage |
| `telemetry-broker` | NanoMQ 0.24.9 | :1883 | MQTT broker |
| `message-broker` | RabbitMQ 4 | :5672 / :15672 | Task queues + AMQP |
| `analytics-engine` | Prefect 3 | :4200 | Batch analytics |
| `task-monitoring` | Flower 2 | :5555 | Celery dashboard |
| `user-interface` | Nuxt | :3000 | Web frontend |
| `docs` | nginx | :80 | **Prod only** |

## The MQTT single-consumer gate

Only one service should subscribe to the NanoMQ broker. The gate is controlled by the `MQTT_CONSUMER_ENABLED` environment variable:

```yaml
# compose.dev.yml — realtime-engine only
realtime-engine:
  environment:
    - MQTT_CONSUMER_ENABLED=true
    - MQTT_HOST=telemetry-broker
    - MQTT_PORT=1883
```

Every Celery worker process imports `MQTTConsumerStep` from `backend/databus/celery.py`, but the step checks `MQTT_CONSUMER_ENABLED` at boot and silently skips if it is not `"true"`. This means `schedule-engine` and `scheduler` workers never open an MQTT connection, even though the step is registered globally.

Failing to set this var to exactly one worker causes either no subscription (if unset everywhere) or duplicate subscriptions that trigger MQTT session conflict and reconnect storms. See [../operations/troubleshooting.md](../operations/troubleshooting.md) for the symptom and the client_id fix (commit `452d4f4`).

## Queue routing

The two Celery workers drain separate named queues, keeping concerns isolated:

```
realtime_engine queue  →  realtime-engine worker
  - process_position_update
  - run_lifecycle_event
  - scan_stale_runs
  - fetch_positions

schedule_engine queue  →  schedule-engine worker
  - build_vehicle_positions
  - build_trip_updates
  - build_schedule
  - build_alerts   (routed here if ever called, but not in the beat schedule — see services.md)
```

Tasks are routed by the `queue=` argument on the `@shared_task` decorator in the respective `tasks.py` modules.

## Development compose

`compose.dev.yml` (`name: databus-dev`) runs everything with:

- Bind-mounted source code (`./backend:/app`) so changes are reflected without rebuilds.
- Host-exposed ports for direct access (Redis on `:6379`, RabbitMQ management on `:15672`, etc.).
- No Traefik — services are reached on `localhost:<port>`.
- A shared `backend_venv` named volume so the uv virtualenv is built once.

## Production compose

`compose.prod.yml` (`name: databus-prod`) changes:

- All services join the `internal` Docker network; only services that need external access additionally join `traefik_proxy`.
- Traefik handles TLS termination and subdomain routing:
    - `$ORCHESTRATOR_DOMAIN` → `orchestrator:8000`
    - `$UI_DOMAIN` → `user-interface:3000`
    - `$MQTT_DOMAIN` (TCP, port 8883) → TLS-terminated, forwarded to `telemetry-broker:1883`
    - `$RABBITMQ_DOMAIN` → RabbitMQ management UI (port 15672)
    - `$ANALYTICS_DOMAIN` → Prefect (port 4200)
    - `$FLOWER_DOMAIN` → Flower (port 5555)
    - `$DOCS_DOMAIN` → nginx serving `docs/site/`
- `restart: unless-stopped` on all services.
- `security_opt: no-new-privileges:true` on all services.
- Redis requires a password (`REDIS_PASSWORD`).
- The `docs` service is only present in prod (nginx + `docs/site/` volume mount).
- No bind-mounted source code — images are built from the Dockerfile `prod` target.

## Health checks

| Service | Health check |
|---|---|
| `database` | `pg_isready -U $DB_USER -d $DB_NAME` |
| `state` | `redis-cli ping` (prod: `-a $REDIS_PASSWORD`) |
| `message-broker` | `rabbitmq-diagnostics status` |

The `realtime-engine` and `schedule-engine` workers wait for `database`, `state`, and `message-broker` to be healthy before starting. The `orchestrator` waits for `database` and `state`.

## Environment variables

Core variables (full reference: [../operations/configuration.md](../operations/configuration.md)):

| Variable | Default | Used by |
|---|---|---|
| `MQTT_CONSUMER_ENABLED` | `false` | `realtime-engine` only (set to `true`) |
| `MQTT_HOST` | `telemetry-broker` | `realtime-engine` bootstep |
| `MQTT_PORT` | `1883` | `realtime-engine` bootstep |
| `REDIS_HOST` | `state` | All workers |
| `REDIS_PORT` | `6379` | All workers |
| `SECRET_KEY` | — | `orchestrator` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | — | All (ORM) |
| `RABBITMQ_USER` / `RABBITMQ_PASS` | `guest`/`guest` | Celery broker URL |
