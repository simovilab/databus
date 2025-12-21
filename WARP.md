# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Databús is a Django-based backend server implementing GTFS Schedule and GTFS Realtime specifications for transit data management. It provides RESTful API endpoints for static schedule data and real-time vehicle information with PostgreSQL/PostGIS storage, Celery for background processing, and Redis for caching and message brokering.

**Tech Stack:** Django 5.2+, Python 3.11+, PostgreSQL/PostGIS, Redis, Celery, Django Channels, uv package manager

## Development Commands

### Initial Setup

```bash
# Docker-based development (recommended)
./scripts/dev.sh

# Non-Docker setup
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
uv pip install -r requirements.txt
cp .env.example .env  # Configure environment variables
python manage.py migrate
python manage.py createsuperuser
```

### Running the Application

**Docker (Development):**
```bash
./scripts/dev.sh  # Starts all services (web, worker, beat, db, redis)

# Access services
# Web: http://localhost:8000
# Admin: http://localhost:8000/admin
# API: http://localhost:8000/api/
# API Docs: http://localhost:8000/api/docs/
```

**Non-Docker (Development):**
```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Redis
redis-server

# Terminal 3: Celery worker
celery -A realtime worker -l info

# Terminal 4: Celery beat (optional, for scheduled tasks)
celery -A realtime beat --scheduler django_celery_beat.schedulers:DatabaseScheduler -l info
```

### Common Development Tasks

```bash
# Database migrations
docker compose -f docker-compose.dev.yml exec web uv run python manage.py makemigrations
docker compose -f docker-compose.dev.yml exec web uv run python manage.py migrate

# Non-Docker:
python manage.py makemigrations
python manage.py migrate

# Create superuser
docker compose -f docker-compose.dev.yml exec web uv run python manage.py createsuperuser
# Non-Docker: python manage.py createsuperuser

# Django shell
docker compose -f docker-compose.dev.yml exec web uv run python manage.py shell
# Non-Docker: python manage.py shell

# View logs
docker compose -f docker-compose.dev.yml logs -f
docker compose -f docker-compose.dev.yml logs -f web  # Web container only

# Stop environment
docker compose -f docker-compose.dev.yml down

# Custom management command
python manage.py update_foreign_keys  # Updates FK relationships for GTFS models
```

### Code Quality and Testing

```bash
# Linting and formatting (Ruff)
ruff check .
ruff format .

# Type checking (mypy)
mypy .

# Tests (pytest)
pytest
pytest tests/  # Run specific directory
pytest -v  # Verbose output
```

Note: Tests are minimal in this project currently. When adding tests, use pytest with pytest-django.

### Production Commands

```bash
# Production deployment
./scripts/prod.sh

# Collect static files
python manage.py collectstatic --noinput
```

## Architecture

### Django Apps Structure

The project consists of four main Django apps:

1. **`gtfs`** (GTFS Schedule app - Git submodule)
   - Manages GTFS Schedule static data (routes, stops, trips, calendars, shapes, etc.)
   - Models: `Agency`, `Stop`, `Route`, `Trip`, `StopTime`, `Shape`, `Calendar`, `FareAttribute`, etc.
   - Provides foundation for real-time data by storing the static schedule
   - Custom management command: `update_foreign_keys` to refresh FK relationships

2. **`feed`** (Real-time Feed Generation)
   - Handles real-time vehicle data collection and GTFS Realtime feed generation
   - Models: `Company`, `Operator`, `DataProvider`, `Vehicle`, `Equipment`, `Journey`, `Position`, `Progression`, `Occupancy`
   - Celery tasks (`feed/tasks.py`):
     - `build_vehicle_positions()`: Creates VehiclePositions FeedMessage (.pb and .json)
     - `build_trip_updates()`: Creates TripUpdates FeedMessage (.pb and .json)
   - Outputs GTFS Realtime protobuf files to `feed/files/`
   - Uses Django Channels for WebSocket real-time status updates

3. **`api`** (RESTful API)
   - Django REST Framework API endpoints for all GTFS and real-time data
   - ViewSets for: agencies, stops, routes, trips, vehicles, journeys, positions, etc.
   - Token-based authentication (DRF TokenAuthentication)
   - OpenAPI schema via drf-spectacular
   - Endpoints at `/api/`

4. **`website`** (Web Interface)
   - Miscellaneous web pages, admin panel enhancements, and data visualizations
   - Frontend interfaces for monitoring transit data

### Key Architectural Patterns

**Multi-Tenant Support:** The `GTFSProvider` model enables serving multiple transit agencies from a single deployment. Each feed is associated with a provider.

**Real-time Data Flow:**
1. Vehicles send telemetry data via API endpoints (authenticated)
2. Data stored in database models: `Position`, `Progression`, `Occupancy`
3. Celery periodic tasks build GTFS Realtime FeedMessages (protobuf)
4. FeedMessages served at static file endpoints or via API
5. WebSocket channels push status updates to connected clients

**GTFS Realtime Implementation:**
- Supports two of three GTFS Realtime entity types:
  - **VehiclePositions**: Real-time vehicle location, speed, bearing, occupancy
  - **TripUpdates**: Predicted arrival/departure times for stops
  - ServiceAlerts are not implemented (requires manual agency input)
- Uses `google.transit.gtfs_realtime_pb2` for protobuf serialization
- Files generated: `feed/files/vehicle_positions.pb|json` and `feed/files/trip_updates.pb|json`

**Geospatial Support:** Uses PostGIS for location-based queries. Models with geometry fields: `Stop.stop_point`, `Shape.point`, `Position.point`.

**Background Processing:** Celery with Redis broker handles:
- Periodic GTFS Realtime feed generation
- Data validation
- Long-running imports/exports
- Scheduled tasks configured via django-celery-beat (database-backed)

### Database Models

**GTFS Schedule hierarchy:**
- `Feed` → `Agency` → `Route` → `Trip` → `StopTime`
- `Stop`, `Calendar`, `Shape` are referenced by trips and routes

**Real-time hierarchy:**
- `Company` (wraps GTFS Agency)
- `Vehicle` → belongs to `Company`
- `Equipment` → tracks vehicle hardware/software
- `Journey` → represents a vehicle's active trip assignment
- `Position`, `Progression`, `Occupancy` → telemetry data linked to vehicle/journey

**Important**: The `gtfs` app is a Git submodule. Initialize with `git submodule update --init --recursive`.

## Environment Configuration

Required environment variables:

- `SECRET_KEY`: Django secret key
- `DEBUG`: Boolean for debug mode
- `ALLOWED_HOSTS`: Comma-separated host list
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: PostgreSQL/PostGIS credentials
- `REDIS_HOST`, `REDIS_PORT`: Redis connection
- For macOS local development: `GDAL_LIBRARY_PATH`, `GEOS_LIBRARY_PATH`

**Files:**
- `.env`: Local configuration with secrets (not in git)
- `.env.dev`: Development-specific overrides (tracked in git)
- `.env.prod`: Production-specific overrides (tracked in git)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/` | REST API root |
| `/api/docs/` | Interactive API documentation (ReDoc) |
| `/api/docs/schema/` | OpenAPI schema |
| `/admin/` | Django admin interface |
| `/feed/` | GTFS feed endpoints |
| `/gtfs/` | GTFS Schedule data endpoints |

## Important Notes

- **GTFS submodule**: The `gtfs/` directory is a Git submodule. Always run `git submodule update --init --recursive` after cloning.
- **Timezone**: Project uses `America/Costa_Rica` timezone and `es-cr` locale.
- **Package manager**: This project uses `uv` for dependency management, not pip directly in Docker.
- **Celery tasks**: Scheduled tasks are configured via Django admin panel (`/admin/django_celery_beat/`), not crontab.
- **WebSockets**: Daphne ASGI server required for Django Channels WebSocket support (production only).
- **GDAL/GEOS**: macOS users need to set library paths in `.env` for PostGIS functionality.

## Production Deployment

Production uses systemd services for Celery worker, Celery beat, and Daphne. See `docs/deployment.md` for complete systemd configuration details.

Key production services:
- Gunicorn (WSGI) for HTTP
- Daphne (ASGI) for WebSockets
- Celery worker
- Celery beat scheduler
- Nginx reverse proxy

## Documentation

Additional documentation in `docs/`:
- `development.md`: Detailed functional development notes (Spanish)
- `deployment.md`: Production deployment with systemd
- `api.md`: API specification details
