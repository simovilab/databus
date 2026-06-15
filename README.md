# Databús

![Static Badge](https://img.shields.io/badge/backend-Django-white?logo=django)
![Static Badge](https://img.shields.io/badge/task_queue-Celery-white?logo=celery)
![Static Badge](https://img.shields.io/badge/package_manager-uv-white?logo=uv)
![Static Badge](https://img.shields.io/badge/frontend-Nuxt-white?logo=nuxt)
![Static Badge](https://img.shields.io/badge/database-PostgreSQL-white?logo=postgresql)
![Static Badge](https://img.shields.io/badge/memory-Redis-white?logo=redis)
![Static Badge](https://img.shields.io/badge/broker-RabbitMQ-white?logo=rabbitmq)
![Static Badge](https://img.shields.io/badge/workflow-Prefect-white?logo=prefect)
![Static Badge](https://img.shields.io/badge/mqtt-NanoMQ-white?logo=mqtt)
![Static Badge](https://img.shields.io/badge/infrastructure-Docker-white?logo=docker)

A distributed transit data system implementing GTFS Schedule and GTFS Realtime specifications. The system is composed of independent services coordinated via message brokers: a Django control plane, Celery workers for real-time processing and feed generation, MQTT telemetry ingestion, a Nuxt frontend, and Prefect for batch analytics — all orchestrated through Docker Compose.

<img width="250" alt="databus" src="https://github.com/user-attachments/assets/b2ad45ac-83e5-44cf-a93e-898868763530" />

## Architecture

| Service              | Role                                          | Tech                   |
| -------------------- | --------------------------------------------- | ---------------------- |
| **orchestrator**     | Control plane, REST API, admin                | Django / Daphne (ASGI) |
| **realtime-engine**  | Processes MQTT telemetry, updates Redis state | Celery worker          |
| **schedule-engine**  | Processes schedules tasks                     | Celery worker          |
| **scheduler**        | Triggers periodic tasks                       | Celery Beat            |
| **user-interface**   | Web frontend                                  | Nuxt                   |
| **database**         | Durable persistence                           | PostgreSQL + PostGIS   |
| **state**            | Authoritative real-time state                 | Redis                  |
| **message-broker**   | Async messaging                               | RabbitMQ               |
| **telemetry-broker** | Vehicle telemetry ingestion                   | NanoMQ (MQTT)          |
| **analytics-engine** | Batch processing and ML                       | Prefect                |
| **task-monitoring**  | Celery task dashboard                         | Flower                 |

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed service mandates, message semantics, and data flow diagrams. See [MODEL.md](MODEL.md) for functional diagrams and state machine flows.

## Getting Started

### Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Git

### Setup

```bash
git clone https://github.com/simovilab/databus.git
cd databus
cp .env.example .env   # edit with your values
./scripts/dev.sh
```

The startup script initializes Git submodules, pulls images, builds containers, and waits for all services to become healthy. On first run this takes 1–2 minutes.

### Development URLs

| URL                             | Description                       |
| ------------------------------- | --------------------------------- |
| http://localhost:8000           | Orchestrator / API                |
| http://localhost:8000/admin     | Django admin                      |
| http://localhost:8000/api/      | REST API root                     |
| http://localhost:8000/api/docs/ | API documentation (ReDoc)         |
| http://localhost:3000           | Nuxt frontend                     |
| http://localhost:15672          | RabbitMQ management (guest/guest) |
| http://localhost:4200           | Prefect dashboard                 |
| http://localhost:5555           | Flower (Celery monitoring)        |

### Common commands

```bash
# Logs
docker compose -f compose.dev.yml logs -f              # all services
docker compose -f compose.dev.yml logs -f orchestrator  # single service

# Django management
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py createsuperuser
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py shell
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py loaddata gtfs.json

# Stop
docker compose -f compose.dev.yml down
```

### Code quality

```bash
# From backend/
ruff check .
ruff format .
mypy .
pytest
```

## Production Deployment

Production runs on Docker Compose behind a [Traefik](https://traefik.io/) reverse proxy that handles TLS termination via Let's Encrypt. All HTTP traffic goes through port **443**; MQTT through port **8883** (TLS). No services expose ports directly to the host.

### Quick start

```bash
cp .env.example .env   # add production domains and credentials (see below)
./scripts/prod.sh
```

### Required environment variables

```bash
# Domain routing (Traefik)
ORCHESTRATOR_DOMAIN=api.example.com
UI_DOMAIN=app.example.com
MQTT_DOMAIN=mqtt.example.com
RABBITMQ_DOMAIN=rabbitmq.example.com
ANALYTICS_DOMAIN=analytics.example.com
FLOWER_DOMAIN=flower.example.com
DOCS_DOMAIN=docs.example.com
CERT_RESOLVER=letsencrypt

# Credentials
SECRET_KEY=<generate-a-strong-key>
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
RABBITMQ_USER=databus
RABBITMQ_PASS=<strong-password>
```

### Production services

| Service          | Domain variable       | Description                |
| ---------------- | --------------------- | -------------------------- |
| orchestrator     | `ORCHESTRATOR_DOMAIN` | Django API and admin       |
| user-interface   | `UI_DOMAIN`           | Nuxt frontend              |
| telemetry-broker | `MQTT_DOMAIN`         | MQTT over TLS (port 8883)  |
| message-broker   | `RABBITMQ_DOMAIN`     | RabbitMQ management UI     |
| analytics-engine | `ANALYTICS_DOMAIN`    | Prefect dashboard          |
| task-monitoring  | `FLOWER_DOMAIN`       | Celery Flower              |
| docs             | `DOCS_DOMAIN`         | Documentation site (nginx) |

Internal-only (not exposed): `database`, `state`, `realtime-engine`, `schedule-engine`, `scheduler`.

### Common operations

```bash
# Rebuild and restart after code changes
docker compose -f compose.prod.yml build orchestrator user-interface
docker compose -f compose.prod.yml up -d orchestrator user-interface

# Django management
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py createsuperuser

# Stop
docker compose -f compose.prod.yml down
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Service mandates, message semantics, and design principles
- [MODEL.md](MODEL.md) — Functional diagrams and state machine flows
- [HOWTO.md](HOWTO.md) — Step-by-step development environment guide
- [docs/development.md](docs/development.md) — Functional development notes (Spanish)
- [docs/deployment.md](docs/deployment.md) — Legacy systemd deployment reference
- [docs/api.md](docs/api.md) — API specification and data formats
- [docs/obe.md](docs/obe.md) — On-board equipment specifications

## Demo: full run lifecycle

End-to-end demo of a complete run lifecycle driven by MQTT telemetry from the simulator.

```bash
# Terminal 1 — start the full databus stack
cd databus && bash scripts/dev.sh

# Terminal 2 — load GTFS feed
docker compose -f compose.dev.yml exec orchestrator \
    uv run python manage.py loaddata gtfs.json

# Terminal 3 — start the simulator (wired to databus broker)
# The simulator's scheduler posts to /api/create-run on each schedule entry's
# start_time. The UI's Operator tab handles confirmation. No databus-side
# bootstrap command is required.
cd ../simulator && docker compose up simulator web

# Terminal 4 — observe (optional)
open http://localhost:8080                      # live map
watch ls backend/feed/files/                   # GTFS-RT outputs (refresh every 15 s)
```

Within ~30 s of starting the simulator:

- Every run advances `CONFIRMED → TRACKING → IN_PROGRESS`
- `backend/feed/files/vehicle_positions.pb` contains one `FeedEntity` per active run
- `backend/feed/files/trip_updates.pb` contains stop-time predictions

Killing the simulator triggers `RUN_TRACKING_LOST` after 60 s and
`RUN_TRACKING_EXPIRED → CANCELLED` after 300 s.

Verify the protobuf output:

```python
from google.transit import gtfs_realtime_pb2
msg = gtfs_realtime_pb2.FeedMessage()
msg.ParseFromString(open("backend/feed/files/vehicle_positions.pb", "rb").read())
print(len(msg.entity))  # should equal the number of active runs
```

## 🛣️ Roadmap

SIMOVI's [roadmap](https://github.com/simovilab/context/blob/main/roadmap.md).

## Contributing

See the [guidelines](https://github.com/simovilab/.github/blob/main/CONTRIBUTING.md).

## Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## License

Apache 2.0
