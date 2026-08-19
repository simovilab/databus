# Feed · GTFS Schedule domain + published feed files

- **Purpose**: owns the GTFS Schedule domain models, feed versioning (`GTFSProvider`/`Feed`), the
  Schedule zip exporter, and the HTTP endpoints that serve published GTFS Schedule and GTFS
  Realtime files from disk. Not to be confused with `schedule_engine`, which *builds* the GTFS-RT
  protobufs consumed here.
- **Key modules**:
  - `models.py` — `GTFSProvider`, `Feed`, and one concrete model per GTFS Schedule table
  - `schedule/exporter.py` — `build_gtfs_zip` / `publish_gtfs_zip`
  - `management/commands/export_gtfs.py` — `manage.py export_gtfs`
  - `views.py` / `urls.py` — file-serving endpoints

## Domain models

Every GTFS Schedule table (`Agency`, `Stop`, `Route`, `Calendar`, `CalendarDate`, `Shape`, `Trip`,
`StopTime`, `FareAttribute`, `FareRule`, `FeedInfo`) subclasses an abstract `Base*` model imported
from the `gtfs-django` workspace package (`feed/models.py:10-22`), then adds a `feed` FK, a
per-feed uniqueness constraint, and (for most) a `linked_*` FK resolved on `save()` for fast joins
(e.g. `Trip.linked_route`, `StopTime.linked_trip`/`linked_stop`). `GeoShape`, `RouteStop`,
`TripDuration`, and `TripTime` are app-specific auxiliary models (not from `gtfs-django`) used by
the registration-UI lookups in `api`. `FeedMessage`/`TripUpdate`/`StopTimeUpdate`/`VehiclePosition`
model the normalized GTFS-RT entities for persisted blobs; `Alert` is a placeholder (TODO in
source, not fed by any current pipeline).

`GTFSProvider` is the org that supplies a feed (may serve multiple agencies); `Feed` is one
retrieved version, marked `is_current=True` to select the active feed. `is_current` is read
directly by `api`'s `WhichShapesView`/`FindTripsView` and by the exporter — there is no automatic
supersession logic in this app; whichever `Feed` is flagged is authoritative.

## Schedule exporter

`feed/schedule/exporter.py` reads the ORM for one `Feed` and serializes it into a GTFS-compliant
`.zip` in memory (`build_gtfs_zip`), excluding internal-only columns (`id`, `feed`, `geoshape`,
`stop_point`, `stop_heading`, `holiday_name`, any `linked_*`). `publish_gtfs_zip` writes it
atomically (`.tmp` + `Path.replace`) to `feed/files/gtfs.zip` by default. Invoked by
`manage.py export_gtfs` (requires a `Feed` with `is_current=True`) and by the daily
`build-schedule` Celery beat entry in `schedule_engine` (see `backend/databus/README.md`).

## Data in / data out

- **Reads**: PostgreSQL, via the models above (no Redis, no queues).
- **Serves** (via `feed/urls.py`, mounted at `/feed/`):
  - `GET /feed/schedule/feed.zip` → `feed/files/gtfs.zip` (404 with a helpful message if not yet
    exported)
  - `GET /feed/realtime/vehicle_positions.json` / `.pb` → `feed/files/vehicle_positions.{json,pb}`
  - `GET /feed/realtime/trip_updates.json` / `.pb` → `feed/files/trip_updates.{json,pb}`
  - `GET /feed/` → status page (`feed/views.py:status`)
  - These realtime files are written by `schedule_engine`, not by this app.

## Configuration

No app-specific env vars.

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest feed/ -q
```
`make test` runs the full suite.

## Docs

- [Django Models](../../docs/content/data-model/django-models.md)
- [GTFS-RT publishing](../../docs/content/data-flow/gtfs-rt-publishing.md)
