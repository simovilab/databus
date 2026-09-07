# Databús

Django apps:

- `api`: API endpoints for Databús, including REST, WebSocket, and SSE.
- `realtime_engine`: Real-time engine (Celery tasks) for handling dynamic updates and events.
- `schedule_engine`: Schedule engine (Celery tasks) for handling scheduled updates and events.
- `operations`: Operational data
- `runs`: Run data (_anima machinae_)
- `website`: Miscellaneous website features (e.g., admin interface, users, etc.)
- `feed`: GTFS data handling and processing

## Workspace layout (uv)

This project is a `uv` workspace (see `pyproject.toml` `[tool.uv.workspace]`):

- `gtfs-django`, `gtfs-io` — workspace members, editable installs from the
  local `backend/gtfs-django/` and `backend/gtfs-io/` directories.
- `gtfs-eta` — **not** a workspace member. It's an editable *path* dependency
  (`[tool.uv.sources]`) pointing at `backend/gtfs-eta`, which is a symlink
  (`gtfs-eta -> ../../gtfs-eta`) to the sibling `simovilab/gtfs-eta` repo
  checked out next to `databus/`. `compose.dev.yml` bind-mounts
  `../gtfs-eta:/gtfs-eta` read-write so the OS-resolved symlink target exists
  inside the container too. `gtfs-eta` is excluded from ruff/mypy/pytest here
  — it's a separately-maintained codebase with its own lint baseline and test
  suite.

## Celery services

Four services share this codebase (see `Dockerfile` build targets and
`compose.dev.yml`):

| Service | Build target | Role | Queue |
|---|---|---|---|
| `orchestrator` | `dev` | Django HTTP + admin + REST API | — (not a worker) |
| `realtime-engine` | `realtime-engine` | Celery worker: MQTT ingestion bootstep, lifecycle events, HTTP polling, staleness scan | `realtime_engine` |
| `schedule-engine` | `schedule-engine` | Celery worker: builds the two GTFS-RT feeds + the daily GTFS Schedule zip | `schedule_engine` |
| `scheduler` | `scheduler` | Celery Beat (`databus/celery.py` `beat_schedule`) | — |

Queues are assigned per-task via `@shared_task(queue=...)`, not Celery
`task_routes`; each worker is started with a matching `-Q <queue>` flag.

## Code quality

Root `Makefile` targets:

```bash
make lint       # cd backend && uv run ruff check .   — runs locally, no Docker needed
make typecheck  # docker compose -f compose.dev.yml run --rm orchestrator uv run mypy .
make test       # docker compose -f compose.dev.yml run --rm orchestrator uv run pytest -q
```

`typecheck` and `test` run inside the dev container because Django settings
read env vars via `python-decouple`, which fails outside the container.
`lint` needs no Django settings import, so it runs locally against the
backend project.

Ruff enforces missing-docstring rules (`D1`, i.e. `D100`-`D107`) in addition
to its default `E`/`F` rules. Mypy runs with the `django-stubs` plugin
(`mypy_django_plugin.main`). Both exclude `migrations/`, `gtfs-eta/`, and
`.venv/`.

## Tests

445 tests (`pytest --collect-only`, `backend/`):

```bash
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest -q
```
