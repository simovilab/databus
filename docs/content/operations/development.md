---
icon: lucide/terminal
---

# Local development

All development is Docker-based. The `scripts/dev.sh` wrapper handles image pulls and health-check waiting, so the recommended workflow is a single command. (It also runs a legacy Git-submodule step that is a no-op today — see the note below.)

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- Git

For macOS/Linux bare-metal work (without Docker), you additionally need:

- Python 3.14+ (`backend/pyproject.toml` pins `requires-python = ">=3.14"`)
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

`dev.sh` pulls and builds images, starts all compose services, and waits for health checks to pass. On first run this takes 1–2 minutes.

!!! note "GTFS dependencies: three different mechanisms, not a submodule"
    `scripts/dev.sh` still contains a legacy step that tries to `git submodule update --init --recursive` for a `backend/gtfs` submodule — but the repo has no `.gitmodules` file and no `backend/gtfs` directory, so that step is a no-op today. The GTFS dependencies actually come from:

    - **`gtfs-io`** and **`gtfs-django`** — cloned directly from GitHub (`simovilab/gtfs-io`, `simovilab/gtfs-django`) by `backend/docker-entrypoint.sh` the first time any backend container starts, then installed editable (`uv add --editable ./gtfs-io`, `./gtfs-django`) as part of Django setup on the `orchestrator` container (gated by `DJANGO_SETUP=True`). All four Python services share the resulting `backend_venv` volume.
    - **`gtfs-eta`** — a sibling-repo path dependency, *not* cloned automatically. `backend/gtfs-eta` is a committed symlink to `../../gtfs-eta`, and `compose.dev.yml` bind-mounts `../gtfs-eta:/gtfs-eta` (read-write, since `uv sync`'s editable install writes a gitignored `.egg-info/` into the source tree) for `orchestrator`, `realtime-engine`, `schedule-engine`, and `scheduler`. You must have `simovilab/gtfs-eta` checked out as a sibling directory of `databus/` (i.e. `../gtfs-eta` relative to this repo) before `docker compose -f compose.dev.yml up` will build successfully. See `backend/pyproject.toml`'s `[tool.uv.sources]` comment for the full path-resolution rationale.

    `compose.prod.yml` has no equivalent `gtfs-eta` bind mount yet — this is a known pre-release gap, not something resolved in the current compose files.

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

!!! note "Migrations are regenerated automatically at container start"
    `backend/docker-entrypoint.sh` runs `manage.py makemigrations feed schedule_engine realtime_engine operations` (when `DEBUG` is true) followed by `manage.py migrate --noinput` every time the `orchestrator` container starts (gated by `DJANGO_SETUP=True`, which only `orchestrator` sets in both compose files). Migration directories are gitignored (`migrations/` in the root `.gitignore`) and regenerated from current models rather than committed — you normally don't need to run `makemigrations`/`migrate` by hand in dev; the commands below are for the cases where you do (e.g. re-running after editing models without restarting the container).

```bash
# Migrations (usually not needed — see note above)
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

The repository root has a `Makefile` with the three canonical entry points — use these unless you have a reason not to:

```bash
make lint       # ruff check . — runs locally against backend/, no Docker needed
make typecheck  # mypy . — runs inside the orchestrator container (docker compose run --rm)
make test       # pytest -q — runs inside the orchestrator container (docker compose run --rm)
```

`lint` runs locally because `ruff` doesn't import Django settings. `typecheck` and `test` run inside the `orchestrator` container because `mypy`'s `django-stubs` plugin (and `pytest-django`) import `databus.settings`, which reads env vars via `python-decouple` and fails outside the container. See the comments in the root `Makefile` for the full rationale.

Equivalently, from `backend/` (matches what the Makefile invokes):

```bash
cd backend

# Linting and auto-fix
ruff check .
ruff format .

# Type checking (inside the orchestrator container — see above)
mypy .

# Tests (inside the orchestrator container — see above)
pytest
pytest tests/ -v
pytest tests/test_specific.py::test_function  # single test
```

`ruff` enforces the `D1` (missing-docstring) rule family — every module, class, and function needs a docstring (see `[tool.ruff.lint]` in `backend/pyproject.toml`). `mypy` runs with `django-stubs` and `check_untyped_defs = false`. Both exclude `gtfs-eta` (the sibling repo's own lint/type baseline) and `migrations/` (gitignored, regenerated at container start — see above).

## Non-Docker (bare-metal) setup

For situations where Docker is not available:

```bash
# Copy environment variables
cp .env.example .env
# Edit .env: set DB_HOST=localhost, REDIS_HOST=localhost, etc.

# Install dependencies (creates backend/.venv from pyproject.toml + uv.lock —
# there is no backend/requirements.txt in this project)
cd backend
uv sync

# Run migrations
uv run python manage.py migrate

# Start workers separately (requires Redis, RabbitMQ, NanoMQ running locally)
# Terminal 1: Django
uv run python manage.py runserver

# Terminal 2: realtime-engine Celery worker (with MQTT consumer)
MQTT_CONSUMER_ENABLED=true uv run celery -A databus worker -Q realtime_engine --loglevel=info

# Terminal 3: schedule-engine Celery worker
uv run celery -A databus worker -Q schedule_engine --loglevel=info

# Terminal 4: Celery beat
uv run celery -A databus beat --loglevel=info
```

!!! note "GTFS workspace members aren't fetched automatically outside Docker"
    `backend/pyproject.toml` declares `gtfs-io` and `gtfs-django` as `[tool.uv.workspace]` members and `gtfs-eta` as an editable `[tool.uv.sources]` path dependency (`backend/gtfs-eta`). Inside Docker, `backend/docker-entrypoint.sh` clones `gtfs-io`/`gtfs-django` from GitHub automatically and `gtfs-eta` arrives via the `compose.dev.yml` bind mount (see the GTFS dependencies note above) — none of that automation runs bare-metal. For a bare-metal `uv sync` to succeed you need `backend/gtfs-io/` and `backend/gtfs-django/` cloned manually (`git clone https://github.com/simovilab/gtfs-io.git backend/gtfs-io`, same for `gtfs-django`) and a `gtfs-eta` checkout reachable at the path `backend/gtfs-eta` resolves to.

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
