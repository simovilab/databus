# Databús · Django project package

- **Purpose**: the Django project itself — settings, the Celery app (task discovery, MQTT
  consumer bootstep registration, beat schedule), ASGI/WSGI entry points, and root URL
  configuration. Every other app under `backend/` is `INSTALLED_APPS`-registered here.
- **Key modules**:
  - `settings.py` — all Django/Celery/Channels/DRF configuration, env-driven via `python-decouple`
  - `celery.py` — the `Celery("databus")` app, MQTT consumer bootstep registration, `beat_schedule`
  - `urls.py` — root URLconf (`admin/`, `website.urls` at `/`, `api.urls` at `/api/`,
    `feed.urls` at `/feed/`)
  - `asgi.py` / `wsgi.py` — ASGI (Daphne, for Channels/WebSocket) and WSGI entry points

## Settings — required env vars (`decouple.config`)

| Variable | Notes |
| --- | --- |
| `SECRET_KEY` | required, no default |
| `DEBUG` | required, cast `bool` |
| `ALLOWED_HOSTS` | required, cast `Csv()` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | required, PostGIS connection |
| `GDAL_LIBRARY_PATH`, `GEOS_LIBRARY_PATH` | required only on macOS (`platform.system() == "Darwin"`) |
| `REDIS_HOST`, `REDIS_PORT` | required — used for `CHANNEL_LAYERS` (`channels_redis`) |
| `RABBITMQ_HOST`, `RABBITMQ_PORT` | required — compose `CELERY_BROKER_URL` |
| `RABBITMQ_USER`, `RABBITMQ_PASS` | optional, default `guest`/`guest` |
| `STATIC_URL` | optional, default `/static/` |
| `MEDIA_URL` | optional, default `/media/` |

`CELERY_BROKER_URL` is derived, not read directly: `amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//`
(`settings.py:146-148`). `CELERY_RESULT_BACKEND = "django-db"`, results are extended
(`CELERY_RESULTS_EXTENDED = True`), and `django_celery_beat`/`django_celery_results` are both
installed apps. `DJANGO_SERVE_STATIC` (plain `os.environ`, not decouple) additionally toggles
serving static/media through Django outside `DEBUG` (`urls.py:33-42`).

## Celery app (`celery.py`)

- Discovers tasks from every installed app (`app.autodiscover_tasks()`).
- Registers `realtime_engine.mqtt.MQTTConsumerStep` as a worker bootstep
  (`app.steps["worker"].add(MQTTConsumerStep)`); the step itself no-ops unless
  `MQTT_CONSUMER_ENABLED` is set, so only the `realtime-engine` container actually starts an MQTT
  connection.
- `debug_task` — prints the current task's request context, for sanity-checking worker
  connectivity.

### Beat schedule (`app.conf.beat_schedule`, `celery.py:47-74`)

| Name | Task | Interval | Notes |
| --- | --- | --- | --- |
| `fetch-positions` | `realtime_engine.tasks.fetch_positions` | every 10s | `options: {"expires": 10}` — a task that hasn't started within its own cycle is revoked rather than queued behind a slow HTTP source |
| `build-vehicle-positions-every-15s` | `schedule_engine.tasks.build_vehicle_positions` | every 15s | |
| `build-trip-updates-every-15s` | `schedule_engine.tasks.build_trip_updates` | every 15s | |
| `scan-stale-runs-every-30s` | `realtime_engine.tasks.scan_stale_runs` | every 30s | |
| `build-schedule-daily` | `schedule_engine.tasks.build_schedule` | every 1 day | rebuilds `feed/files/gtfs.zip` |

This is the beat schedule as actually configured in code — it lives in `app.conf.beat_schedule`
here, not in Django admin.

## ASGI / WSGI / URLs

- `ASGI_APPLICATION = "databus.asgi.application"` — served by Daphne (`daphne` + `channels` apps
  installed) to support the Channels layer (`CHANNEL_LAYERS` → `channels_redis`, keyed off
  `REDIS_HOST`/`REDIS_PORT`).
- `WSGI_APPLICATION = "databus.wsgi.application"`.
- Root URLconf mounts: `admin/` (Django admin), `""` (`website.urls`), `api/` (`api.urls`),
  `feed/` (`feed.urls`); media/static are served through Django when `DEBUG` or
  `DJANGO_SERVE_STATIC` is set.

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest -q
```
No `databus/tests.py` of its own — this package is exercised indirectly by every other app's test
suite. `make test` runs the full suite.

## Docs

- [Celery workers, queues & beat](../../docs/content/operations/celery.md)
- [Configuration & environment variables](../../docs/content/operations/configuration.md)
