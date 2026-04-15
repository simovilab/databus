# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Databús is a distributed transit data system implementing GTFS Schedule and GTFS Realtime specifications. The system consists of multiple services coordinated via message brokers, with Django backend as the control plane and separate Python services for real-time processing and feed generation.

**Tech Stack:** Django 5.2+, Python 3.11+, PostgreSQL/PostGIS, Redis, RabbitMQ, MQTT, Celery, Docker

## Development Commands

### Initial Setup

```bash
# Docker-based development (recommended)
./scripts/dev.sh

# Non-Docker setup
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
uv pip install -r backend/requirements.txt
cp .env.example .env  # Configure environment variables
cd backend && python manage.py migrate
```

### Running Services

**Docker (recommended):**

```bash
./scripts/dev.sh  # Starts all services
docker compose -f compose.dev.yml logs -f  # View logs
docker compose -f compose.dev.yml logs -f orchestrator  # Single service logs
docker compose -f compose.dev.yml down  # Stop all services
```

**Non-Docker (requires running services separately in multiple terminals):**

```bash
# Terminal 1: Django
cd backend && python manage.py runserver

# Terminal 2: Redis
redis-server

# Terminal 3: RabbitMQ
# (see installation docs for your OS)

# Terminal 4: Publisher (Celery worker)
cd publisher && uv run python -m celery -A publisher worker -l info

# Terminal 5: Scheduler (Celery beat)
cd scheduler && uv run python -m celery -A scheduler beat -l info
```

### Database Operations

```bash
# Docker
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py makemigrations
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py shell
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py createsuperuser

# Custom management command to refresh GTFS model FKs
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py update_foreign_keys

# Load fixture data (bUCR GTFS)
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py loaddata gtfs.json

# Non-Docker
cd backend
python manage.py makemigrations
python manage.py migrate
python manage.py shell
```

### Code Quality

```bash
# Run from backend/ directory
cd backend

# Linting and formatting
ruff check .
ruff format .

# Type checking
mypy .

# Tests (minimal coverage currently)
pytest
pytest tests/ -v
pytest tests/test_specific.py::test_function  # Single test
```

### Accessing Services

- Orchestrator: http://localhost:8000
- Django Admin: http://localhost:8000/admin
- API Root: http://localhost:8000/api/
- API Docs: http://localhost:8000/api/docs/
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- Prefect Analytics: http://localhost:4200

## Architecture

### Service-Oriented Architecture

The system is composed of independent services communicating asynchronously:

1. **orchestrator** (Django) - Control plane and HTTP API
   - Django apps: `gtfs` (submodule), `feed`, `api`, `website`
   - Manages domain models, issues commands, exposes REST APIs
   - Does NOT process real-time telemetry or maintain operational state
   - Located in: `backend/`

2. **realtime-engine** (Python) - Real-time processing
   - Consumes MQTT telemetry and AMQP commands
   - Updates authoritative state in Redis
   - Emits observations to message broker
   - Located in: `realtime-engine/`

3. **publisher** (Celery worker) - GTFS Realtime generation
   - Reads state snapshots from Redis
   - Generates protobuf feeds (`vehicle_positions.pb`, `trip_updates.pb`)
   - Emits assertions to message broker
   - Located in: `publisher/`

4. **scheduler** (Celery beat) - Temporal orchestration
   - Triggers periodic publishing tasks
   - Located in: `scheduler/`

5. **analytics-engine** (Prefect) - Batch processing and ML
   - Processes historical data for insights
   - Located in: `analytics-engine/`

### Infrastructure Services

- **database** - PostgreSQL with PostGIS (durable persistence)
- **state** - Redis (authoritative in-memory operational state)
- **message-broker** - RabbitMQ (AMQP for commands/observations/assertions)
- **telemetry-broker** - NanoMQ (telemetry ingestion from vehicles)

### Key Architectural Principles

- **Single writer per responsibility** - Each service owns specific concerns
- **Async-first** - Services communicate via brokers, not synchronous calls
- **In-memory state is authoritative for real-time** - Database is NOT used for coordination
- **Explicit message semantics** - Commands (orchestrator→engine), observations (engine→orchestrator), assertions (publisher→orchestrator)

### Data Flow Example

1. Dispatcher issues "begin run" command via backend HTTP API
2. Backend stores run metadata in PostgreSQL and emits command to RabbitMQ
3. Realtime-engine receives command, initializes run state in Redis
4. Vehicle sends telemetry via MQTT
5. Realtime-engine processes telemetry, updates Redis state, emits observations
6. Scheduler triggers publisher task (every 15 seconds)
7. Publisher reads Redis snapshot, generates GTFS Realtime protobuf files
8. Publisher stores GTFS RT records in PostgreSQL, emits assertions

### Django Apps (backend/)

- **gtfs** (Git submodule at `backend/gtfs/`)
  - GTFS Schedule models: `Agency`, `Stop`, `Route`, `Trip`, `StopTime`, `Calendar`, `Shape`
  - MUST initialize submodule: `git submodule update --init --recursive`
- **feed**
  - Real-time models: `Company`, `Vehicle`, `Run`, `Position`, `Progression`, `Occupancy`
  - Celery tasks: `build_vehicle_positions()`, `build_trip_updates()` (in `feed/tasks.py`)
  - Output directory: `backend/feed/files/`

- **api**
  - DRF ViewSets for all models
  - Token authentication
  - OpenAPI schema via drf-spectacular

- **website**
  - Web interfaces and visualizations
  - Admin panel customizations

### Message Broker Semantics

| Producer        | Message Type | Meaning                                   | Queue/Exchange |
| --------------- | ------------ | ----------------------------------------- | -------------- |
| Orchestrator    | Commands     | Intentional requests (begin run, end run) | RabbitMQ       |
| Realtime Engine | Observations | Derived facts from telemetry              | RabbitMQ       |
| Publisher       | Assertions   | Claims about published outputs            | RabbitMQ       |

### State Management

- **Redis (state service)** - Authoritative real-time state
  - Key patterns: `runs:in_progress`, `run:{id}`, `vehicle:{id}:data`, `vehicle:{id}:position`, `vehicle:{id}:progression`, `vehicle:{id}:occupancy`
  - Updated by: realtime-engine
  - Read by: publisher

- **PostgreSQL (database service)** - Durable persistence
  - GTFS Schedule data
  - Run metadata and historical records
  - GTFS Realtime feed blobs (retained ~1 year)

## Environment Configuration

Required variables in `.env`:

- Django: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- Database: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Redis: `REDIS_HOST`, `REDIS_PORT`
- macOS only: `GDAL_LIBRARY_PATH`, `GEOS_LIBRARY_PATH` (for PostGIS)

Files:

- `.env` - Local secrets (not in git)
- `.env.dev` - Development overrides (tracked)
- `.env.prod` - Production overrides (tracked)
- `.env.example` - Template

## Important Notes

- **GTFS submodule**: Always run `git submodule update --init --recursive` after cloning
- **Package manager**: Uses `uv`, not pip directly
- **Timezone**: `America/Costa_Rica` (es-cr locale)
- **Multiple services**: Backend is just one service; realtime-engine, publisher, scheduler are separate Python projects
- **Service names in Docker**: Use compose service names (`database`, `state`, `message-broker`) not `localhost` for inter-service communication
- **Tests**: Minimal coverage currently. Use pytest with pytest-django for new tests
- **Celery tasks**: Configured via Django admin at `/admin/django_celery_beat/`, not crontab
- **State vs Persistence**: Real-time decisions use Redis state; PostgreSQL is for durability and analytics only

## Common Patterns

### Adding a New Celery Task

1. Define task in appropriate location (`publisher/` for GTFS RT generation, `backend/feed/tasks.py` for backend tasks)
2. Register in Celery app configuration
3. Schedule via Django admin if periodic, or invoke manually/on-demand

### Working with Real-time State

```python
import redis
r = redis.Redis(host='state', port=6379, decode_responses=True)

# Get all in-progress runs
runs = r.smembers('runs:in_progress')

# Get specific run metadata
run = r.hgetall(f'run:{run_id}')

# Get vehicle position
position = r.hgetall(f'vehicle:{vehicle_id}:position')
```

### Adding a New API Endpoint

1. Define model in appropriate Django app (`gtfs/`, `feed/`)
2. Create ViewSet in `backend/api/views.py`
3. Register router in `backend/api/urls.py`
4. Document with drf-spectacular decorators

### Debugging Message Flow

1. Check RabbitMQ management UI: http://localhost:15672
2. View queue depths, message rates, bindings
3. Trace messages: orchestrator→message-broker→realtime-engine
4. Check service logs: `docker compose -f compose.dev.yml logs -f <service>`

## Documentation

- `ARCHITECTURE.md` - Detailed service mandates and principles
- `MODEL.md` - Functional diagrams and state machine flows
- `docs/development.md` - Functional notes (Spanish)
- `docs/deployment.md` - Production systemd setup
- `docs/api.md` - API specifications
- `README.md` - Quick start guide
