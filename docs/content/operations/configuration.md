---
icon: lucide/settings
description: Complete environment variable reference for Databús — Django core, database, Redis, RabbitMQ, MQTT, Traefik domain routing, and development port bindings.
---

# Configuration & environment variables

Databús is configured entirely through environment variables loaded from `.env` (development) or `.env` + `.env.prod` (production). The `.env.example` file at the repository root is the canonical reference — copy it to `.env` and fill in values before starting the stack.

## `.env` file roles

| File | Purpose |
|---|---|
| `.env.example` | Template committed to the repository. Contains safe defaults and empty slots for secrets. |
| `.env` | Your local configuration. **Never commit this file.** |
| `.env.prod` | Production overrides (domains, TLS, credentials). Loaded alongside `.env` by `compose.prod.yml`. |

## Variable reference

### Django core

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `SECRET_KEY` | *(empty)* | Yes | Django secret key. Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. |
| `ALLOWED_HOSTS` | *(empty)* | Yes | Comma-separated list of allowed hostnames. In development: `localhost,127.0.0.1`. |
| `DEBUG` | *(not set)* | No | Set to `True` for development. Never set in production. |
| `STATIC_URL` | `/static/` | No | URL prefix for static files. |
| `MEDIA_URL` | `/media/` | No | URL prefix for media files. |

!!! danger "Never in production"
    Never set `DEBUG=True` in production — it exposes stack traces, settings, and internal URLs to anyone who triggers an error. Always generate a strong unique `SECRET_KEY` (never use the example value or leave it empty). Rotate default database, Redis, and RabbitMQ credentials (`DB_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_PASS`) before first deployment — the defaults (`postgres`, `redispassword`, `guest`) are publicly known.

### Database (PostgreSQL / PostGIS)

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `DB_NAME` | `databus` | No | PostgreSQL database name. |
| `DB_USER` | `postgres` | No | PostgreSQL user. |
| `DB_PASSWORD` | `postgres` | Yes (prod) | PostgreSQL password. Change in production. |
| `DB_HOST` | `database` | No | Database hostname. Docker resolves `database` inside the compose network; use `localhost` for bare-metal. |
| `DB_PORT` | `5432` | No | PostgreSQL port. |

### Redis (authoritative real-time state)

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `REDIS_HOST` | `state` | No | Redis hostname. Docker resolves `state` inside the compose network. |
| `REDIS_PORT` | `6379` | No | Redis port. |
| `REDIS_PASSWORD` | `redispassword` | Yes (prod) | Redis AUTH password. Required in `compose.prod.yml` (the `state` service starts with `--requirepass`). Leave empty for bare-metal dev without auth. |
| `REDIS_DB` | `0` | No | Redis database index. |

### RabbitMQ (AMQP message broker)

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `RABBITMQ_USER` | `guest` | No | RabbitMQ user. |
| `RABBITMQ_PASS` | `guest` | Yes (prod) | RabbitMQ password. |
| `RABBITMQ_HOST` | `message-broker` | No | RabbitMQ hostname. |
| `RABBITMQ_PORT` | `5672` | No | RabbitMQ AMQP port. |

### MQTT (telemetry broker)

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `MQTT_HOST` | `telemetry-broker` | No | NanoMQ broker hostname. Resolved inside the compose network. |
| `MQTT_PORT` | `1883` | No | Plain MQTT port. Traefik terminates TLS on 8883 in production and forwards plain MQTT to NanoMQ on 1883. |
| `MQTT_CONSUMER_ENABLED` | `false` | **Critical** | Master switch for the MQTT consumer bootstep. Set `true` **only** on the `realtime-engine` worker. See [Telemetry ingestion](../data-flow/telemetry-ingestion.md). |

!!! warning "Do not set MQTT_CONSUMER_ENABLED=true on multiple workers"
    Each worker that has this variable enabled will subscribe to the broker and process every MQTT message. That means double-processing all telemetry. The compose files are pre-configured correctly; only change this if you know what you are doing.

### Production domain routing (Traefik)

These variables are only meaningful when running `compose.prod.yml`. They configure Traefik router rules.

| Variable | Example value | Purpose |
|---|---|---|
| `ORCHESTRATOR_DOMAIN` | `api.databus.simovilab.com` | Django API and admin |
| `UI_DOMAIN` | `databus.simovilab.com` | Nuxt frontend |
| `MQTT_DOMAIN` | `mqtt.databus.simovilab.com` | MQTT over TLS (port 8883) |
| `RABBITMQ_DOMAIN` | `rabbitmq.databus.simovilab.com` | RabbitMQ management UI |
| `ANALYTICS_DOMAIN` | `flows.databus.simovilab.com` | Prefect dashboard |
| `FLOWER_DOMAIN` | `tasks.databus.simovilab.com` | Celery Flower |
| `DOCS_DOMAIN` | `docs.databus.simovilab.com` | Documentation site |
| `CERT_RESOLVER` | `letsencrypt` | Traefik certificate resolver name |

### Host-port mapping (development only)

These variables control which host ports the compose services bind to in development. They have no effect in production (no ports are exposed to the host in `compose.prod.yml`).

| Variable | Default | Mapped service |
|---|---|---|
| `BACKEND_PORT` | `8000` | Django (orchestrator) |
| `DATABASE_PORT` | `5432` | PostgreSQL |
| `STATE_PORT` | `6379` | Redis |
| `MQTT_BROKER_PORT` | `1883` | NanoMQ |
| `MESSAGE_BROKER_AMQP_PORT` | `5672` | RabbitMQ AMQP |
| `MESSAGE_BROKER_MANAGEMENT_PORT` | `15672` | RabbitMQ management UI |
| `ANALYTICS_PORT` | `4200` | Prefect |
| `TASK_MONITORING_PORT` | `5555` | Flower |
| `USER_INTERFACE_PORT` | `13000` | Nuxt frontend |

### Other

| Variable | Default | Purpose |
|---|---|---|
| `API_TOKEN` | *(empty)* | Google Maps API key (used by the frontend map). |
| `PREFECT_SERVER_API_HOST` | `0.0.0.0` | Prefect server bind address. |
| `PREFECT_API_URL` | `http://localhost:4200/api` | Prefect API URL for workers. |

## macOS bare-metal: GDAL / GEOS paths

GeoDjango requires native GDAL and GEOS libraries. On macOS with Homebrew:

```bash
brew install gdal geos

# Add to .env or shell profile:
GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
```

On Apple Silicon, the Homebrew prefix is `/opt/homebrew`; on Intel it is `/usr/local`.

## Related pages

- [Local development](development.md) — using these variables in a development setup.
- [Deployment (production)](deployment.md) — production-specific configuration.
- [Telemetry ingestion](../data-flow/telemetry-ingestion.md) — `MQTT_CONSUMER_ENABLED` in detail.
