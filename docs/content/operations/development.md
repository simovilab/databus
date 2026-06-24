---
icon: lucide/terminal
description: Docker-based local development workflow — first-time setup, daily start/stop commands, Django management, code quality tools, and a full end-to-end demo sequence.
---

# Local development

All development is Docker-based. The `scripts/dev.sh` wrapper handles submodule initialisation, image pulls, and health-check waiting, so the recommended workflow is a single command.

**Quick start** (after copying `.env.example` to `.env`):

```bash
./scripts/dev.sh   # start all services; API at http://localhost:8000/api/docs/
```

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- Git

For macOS/Linux bare-metal work (without Docker), you additionally need:

- Python 3.11+
- `uv` (package manager)
- Redis, PostgreSQL/PostGIS, RabbitMQ, NanoMQ running locally

## First-time setup

```bash
git clone https://github.com/simovilab/databus.git
cd databus

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your local values (see Configuration for details)

# Start all services
./scripts/dev.sh
```

`dev.sh` initialises Git submodules (the `gtfs` submodule under `backend/`), pulls and builds images, starts all compose services, and waits for health checks to pass. On first run this takes 1–2 minutes.

## Daily workflow

### Start / stop

```bash
# Start (or restart after code changes)
./scripts/dev.sh

# View logs — all services
docker compose -f compose.dev.yml logs -f

# View logs — single service
docker compose -f compose.dev.yml logs -f orchestrator
docker compose -f compose.dev.yml logs -f realtime-engine

# Stop
docker compose -f compose.dev.yml down
```

### Django management commands

All management commands run inside the `orchestrator` container:

```bash
# Migrations
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py makemigrations
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py migrate

# Create admin user
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py createsuperuser

# Open Django shell
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py shell

# Load bUCR GTFS fixture
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py loaddata gtfs.json

# Refresh GTFS model foreign keys after a feed import
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py update_foreign_keys
```

## Development URLs

| URL | Service |
|---|---|
| http://localhost:8000 | Orchestrator (Django / Daphne) |
| http://localhost:8000/admin | Django admin |
| http://localhost:8000/api/ | REST API root |
| http://localhost:8000/api/docs/ | API documentation (ReDoc) |
| http://localhost:3000 | Nuxt frontend (user-interface) |
| http://localhost:15672 | RabbitMQ management UI (guest / guest) |
| http://localhost:4200 | Prefect analytics dashboard |
| http://localhost:5555 | Flower (Celery task monitoring) |

## Code quality

All quality tools run from `backend/`:

```bash
cd backend

# Linting and auto-fix
ruff check .
ruff format .

# Type checking
mypy .

# Tests
pytest
pytest tests/ -v
pytest tests/test_specific.py::test_function  # single test
```

## Non-Docker (bare-metal) setup

For situations where Docker is not available:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux / macOS

# Install dependencies
uv pip install -r backend/requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env: set DB_HOST=localhost, REDIS_HOST=localhost, etc.

# Run migrations
cd backend
python manage.py migrate

# Start workers separately (requires Redis, RabbitMQ, NanoMQ running locally)
# Terminal 1: Django
python manage.py runserver

# Terminal 2: realtime-engine Celery worker (with MQTT consumer)
MQTT_CONSUMER_ENABLED=true celery -A databus worker -Q realtime_engine -l info

# Terminal 3: schedule-engine Celery worker
celery -A databus worker -Q schedule_engine -l info

# Terminal 4: Celery beat
celery -A databus beat -l info
```

!!! note "macOS GDAL/GEOS"
    PostGIS/GeoDjango on macOS requires GDAL and GEOS to be installed and discoverable. A common approach is `brew install gdal geos`. If Django raises `OSError: Could not find the GDAL library`, set `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` in your environment to point to the Homebrew lib paths (e.g. `/opt/homebrew/lib/libgdal.dylib`).

## Running a full demo

This sequence exercises the complete run lifecycle end-to-end:

```bash
# Terminal 1 — start the full stack
./scripts/dev.sh

# Terminal 2 — load GTFS feed
docker compose -f compose.dev.yml exec orchestrator \
    uv run python manage.py loaddata gtfs.json

# Terminal 3 — start the simulator (separate repo)
cd ../simulator && docker compose up simulator web

# Terminal 4 — observe output
watch ls backend/feed/files/   # GTFS-RT files refresh every 15 s
open http://localhost:8080     # live map (simulator UI)
```

Within about 30 seconds:

- Runs advance `CONFIRMED → TRACKING → IN_PROGRESS` as the simulator publishes telemetry.
- `backend/feed/files/vehicle_positions.pb` contains one `FeedEntity` per active run.
- `backend/feed/files/trip_updates.pb` contains stop-time predictions.

Stopping the simulator triggers `run_tracking_lost` after 60 seconds and `run_tracking_expired` after 600 seconds.

## Related pages

- [Configuration & env vars](configuration.md) — `.env` variable reference.
- [Celery workers, queues & beat](celery.md) — understanding the worker processes.
- [Troubleshooting & debugging](troubleshooting.md) — what to do when things go wrong.
