---
icon: lucide/link
---

# URL Directory

Reference for all service endpoints — subdomains in production and ports in
development. Routing is handled by Traefik in production; services bind directly
to localhost ports in development.

---

## Production (Traefik, TLS)

All production traffic goes through Traefik on port **443** (HTTPS) or port
**8883** (MQTT over TLS). No service exposes a direct port to the host.
Domains are configured via environment variables in `.env`.

| Environment variable | Service | Backend port | Notes |
| --- | --- | --- | --- |
| `ORCHESTRATOR_DOMAIN` | Django API + admin | 8000 | REST API, admin, WebSocket |
| `UI_DOMAIN` | Nuxt frontend | 3000 | Passenger / operator UI |
| `MQTT_DOMAIN` | NanoMQ broker | 8883 (TCP/TLS) | MQTT over TLS |
| `RABBITMQ_DOMAIN` | RabbitMQ management UI | 15672 | Requires credentials |
| `ANALYTICS_DOMAIN` | Prefect dashboard | 4200 | `PREFECT_API_URL` uses this domain |
| `FLOWER_DOMAIN` | Flower (Celery monitoring) | 5555 | Task queue dashboard |
| `DOCS_DOMAIN` | Documentation (nginx) | 80 | This site |

Example — if your base domain is `example.com`:

```
https://api.example.com       — Orchestrator (REST API, admin)
https://app.example.com       — User interface
mqtt://mqtt.example.com:8883  — MQTT (TLS)
https://rabbitmq.example.com  — RabbitMQ management
https://flows.example.com     — Prefect dashboard
https://flower.example.com    — Flower (Celery task monitoring)
https://docs.example.com      — Documentation site
```

Subdomain names (`api.`, `app.`, `flows.`, `flower.`, `docs.`) are just
examples — use whatever `*_DOMAIN` values you set in `.env`. There is no
enforced naming convention.

---

## Development (localhost)

In development (`compose.dev.yml`), services bind directly to `localhost` ports.
No Traefik, no TLS.

| URL | Service | Notes |
| --- | --- | --- |
| `http://localhost:8000` | Orchestrator / API | |
| `http://localhost:8000/admin` | Django admin | Superuser required |
| `http://localhost:8000/api/` | REST API root | |
| `http://localhost:8000/api/docs/` | API documentation (ReDoc) | |
| `ws://localhost:8000/ws/status/` | WebSocket live updates | |
| `http://localhost:3000` | Nuxt frontend | |
| `mqtt://localhost:1883` | NanoMQ broker | No TLS in dev |
| `http://localhost:15672` | RabbitMQ management | guest / guest |
| `http://localhost:4200` | Prefect dashboard | |
| `http://localhost:5555` | Flower (Celery monitoring) | |

---

## Notable paths on the orchestrator

| Path | Purpose |
| --- | --- |
| `/admin/` | Django admin |
| `/api/` | REST API root (DRF browsable) |
| `/api/docs/` | ReDoc API documentation |
| `/api/docs/schema/` | AsyncAPI schema download (`realtime.yml`) |
| `/api/create-run/` | Create a new run |
| `/api/runs/<id>/state/` | Get current run state |
| `/api/runs/<id>/update/` | Send a lifecycle event to a run |
| `/api/runs/<id>/history/` | Run lifecycle audit log |
| `/ws/status/` | WebSocket — live feed status updates |

---

## Internal services (not exposed externally)

The following services are internal-only and have no external Traefik route:

| Service | Role |
| --- | --- |
| `database` | PostgreSQL + PostGIS |
| `state` | Redis |
| `realtime-engine` | Celery worker (MQTT + telemetry processing) |
| `schedule-engine` | Celery worker (GTFS-RT building) |
| `scheduler` | Celery Beat |

Source: `compose.prod.yml` Traefik labels, `README.md §Production services`.
