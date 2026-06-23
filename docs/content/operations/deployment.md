---
icon: lucide/rocket
---

# Deployment (production)

Production runs on Docker Compose behind a Traefik reverse proxy. TLS is terminated by Traefik using Let's Encrypt. No service exposes ports directly to the host.

!!! note "This page supersedes `docs/deployment.md`"
    The legacy `docs/deployment.md` describes a systemd-based deployment. That approach is retired. The compose/Traefik setup documented here is the current production target.

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- A server with ports 80, 443, and 8883 accessible from the internet
- DNS records pointing the domain variables to your server
- A `.env` file with production credentials (never commit this file)
- A `.env.prod` file with domain overrides (see below)

## Quick start

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD, RABBITMQ_PASS,
#             and all *_DOMAIN variables

./scripts/prod.sh
```

`prod.sh` initialises submodules, builds images, and starts `compose.prod.yml`.

## Environment variables

Production requires two env files:

- `.env` — base configuration (DB credentials, Redis password, RabbitMQ, MQTT).
- `.env.prod` — production overrides (`DEBUG=False`, production hostnames if different from `.env`).

The minimum set of required variables:

```bash
# Django
SECRET_KEY=<generate with django>

# Database
DB_PASSWORD=<strong-password>

# Redis
REDIS_PASSWORD=<strong-password>

# RabbitMQ
RABBITMQ_USER=databus
RABBITMQ_PASS=<strong-password>

# Domain routing
ORCHESTRATOR_DOMAIN=api.databus.simovilab.com
UI_DOMAIN=databus.simovilab.com
MQTT_DOMAIN=mqtt.databus.simovilab.com
RABBITMQ_DOMAIN=rabbitmq.databus.simovilab.com
ANALYTICS_DOMAIN=flows.databus.simovilab.com
FLOWER_DOMAIN=tasks.databus.simovilab.com
DOCS_DOMAIN=docs.databus.simovilab.com

# TLS
CERT_RESOLVER=letsencrypt
```

## Traefik overview

Traefik runs as an external container on the `traefik_proxy` Docker network. Services opt into Traefik routing via labels:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.orchestrator.rule=Host(`${ORCHESTRATOR_DOMAIN}`)"
  - "traefik.http.routers.orchestrator.entrypoints=websecure"
  - "traefik.http.routers.orchestrator.tls.certresolver=${CERT_RESOLVER:-letsencrypt}"
```

MQTT uses a TCP router (not HTTP) because TLS passthrough for MQTT requires TCP-level routing:

```yaml
labels:
  - "traefik.tcp.routers.mqtt.rule=HostSNI(`${MQTT_DOMAIN}`)"
  - "traefik.tcp.routers.mqtt.entrypoints=mqtt"
  - "traefik.tcp.routers.mqtt.tls.certresolver=${CERT_RESOLVER:-letsencrypt}"
  - "traefik.tcp.services.mqtt.loadbalancer.server.port=1883"
```

Traefik terminates TLS on port 8883 and forwards plain MQTT to NanoMQ on port 1883 within the internal network.

## Services exposed by Traefik

| Compose service | Domain variable | Protocol | Internal port |
|---|---|---|---|
| `orchestrator` | `ORCHESTRATOR_DOMAIN` | HTTPS | 8000 |
| `user-interface` | `UI_DOMAIN` | HTTPS | 3000 |
| `telemetry-broker` | `MQTT_DOMAIN` | MQTT over TLS (8883) | 1883 |
| `message-broker` | `RABBITMQ_DOMAIN` | HTTPS (management UI) | 15672 |
| `analytics-engine` | `ANALYTICS_DOMAIN` | HTTPS | 4200 |
| `task-monitoring` | `FLOWER_DOMAIN` | HTTPS | 5555 |
| `docs` | `DOCS_DOMAIN` | HTTPS | 80 |

Internal-only (no Traefik exposure): `database`, `state`, `realtime-engine`, `schedule-engine`, `scheduler`.

## Documentation service

The `docs` service is production-only (it does not appear in `compose.dev.yml`). It runs nginx serving the pre-built Zensical static site from `./docs/site`:

```yaml
docs:
  image: nginx:alpine
  volumes:
    - ./docs/site:/usr/share/nginx/html:ro
```

To update the documentation site after editing content:

```bash
# Build the static site (from the docs/ directory)
cd docs && zensical build

# Restart the docs container to pick up new files
docker compose -f compose.prod.yml restart docs
```

## Volumes and persistence

| Volume | Mounted by | Contents |
|---|---|---|
| `database_data` | `database` | PostgreSQL data directory |
| `state_data` | `state` | Redis AOF journal (`--appendonly yes`) |
| `message_broker_data` | `message-broker` | RabbitMQ message store |
| `backend_venv` | `orchestrator`, `realtime-engine`, `schedule-engine`, `scheduler` | Shared Python virtual environment (`uv`) |
| `static_files` | `orchestrator` | Django `collectstatic` output (served externally) |

Redis runs with `--appendonly yes` for durability. The AOF journal persists the current run state across Redis restarts. Note that run-state data is relatively small and fast to rebuild — a Redis restart is not catastrophic, but a full `FLUSHALL` will require manual run-state recovery (see [Troubleshooting](troubleshooting.md)).

## Common operations

```bash
# Rebuild and restart after code changes
docker compose -f compose.prod.yml build orchestrator user-interface
docker compose -f compose.prod.yml up -d orchestrator user-interface

# Django management in production
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py createsuperuser

# View logs
docker compose -f compose.prod.yml logs -f orchestrator
docker compose -f compose.prod.yml logs -f realtime-engine

# Full stop
docker compose -f compose.prod.yml down
```

## Security notes

All services in `compose.prod.yml` set:

```yaml
security_opt:
  - no-new-privileges:true
restart: unless-stopped
```

AMQP (port 5672) is internal-only — only RabbitMQ's management UI is exposed via Traefik. PostgreSQL (5432) and Redis (6379) are internal-only with no Traefik exposure. Change default credentials (`DB_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_PASS`) before deploying.

## Related pages

- [Configuration & env vars](configuration.md) — all variables.
- [Troubleshooting & debugging](troubleshooting.md) — production failure modes.
- [Architecture: deployment topology](../architecture/deployment-topology.md) — compose network diagram.
