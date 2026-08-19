# API · public REST layer (DRF)

- **Purpose**: the orchestrator's control plane. Exposes run registration and lifecycle
  transitions, read-only GTFS Schedule resources, two lookup endpoints that back the
  run-registration UI cascade, and the static realtime OpenAPI schema. Django models: none —
  `api` is a REST layer over `runs`, `operations`, and `feed` models.
- **Key modules**:
  - `views.py` — all ViewSets/APIViews (operations, runs, GTFS Schedule, auxiliary GTFS)
  - `serializers.py` — DRF serializers, including `CreateRunSerializer` / `RunUpdateSerializer`
  - `urls.py` — router registrations + custom paths
  - `realtime.yml` — static GTFS Realtime/MQTT OpenAPI/AsyncAPI schema, served as a file download

## Run registration & lifecycle

- `POST /api/create-run/` (`CreateRunViewSet`) — validates the payload, resolves
  `vehicle_id`/`operator_id`, creates the `Run` row (implicit `RUN_REQUESTED`), then drives it
  through `RunLifecycleEvents.VALIDATE_RUN` → `RunLifecycleEvents.INITIALIZE_RUN` via
  `RunLifecycleService`. Any failed step returns the failing stage (`serialization`,
  `operational_validation`, `registration`, `gtfs_validation`, `initialization`) with a matching
  HTTP status (`api/views.py:199-279`).
- `GET /api/runs/<uuid:run_id>/state/` — current `run_lifecycle_state`.
- `POST /api/runs/<uuid:run_id>/update/` (`RunUpdateViewSet`) — advances a run's FSM. The `event`
  field takes the **lowercase** `RunLifecycleEvents` value (e.g. `run_confirmed_by_operator`, not
  the enum member name); `RunUpdateSerializer` validates against `RunLifecycleEvents` and any
  extra `details` are flattened into the payload before `process_event` (`api/views.py:303-366`).
- `GET /api/runs/<uuid:run_id>/history/` — ordered `RunLifecycleTransition` audit log.

## GTFS Schedule + registration-UI lookups

- Router-registered read/write resources for `agency`, `stops`/`geo-stops`, `shapes`/`geo-shapes`,
  `routes`, `calendars`, `calendar-dates`, `trips`, `stop-times`, `fare-attributes`, `fare-rules`,
  `feed-info` (all backed by `feed.models`, unauthenticated).
- `GET /api/service-today/?date=YYYY-MM-DD` — active GTFS `service_id`s for a date.
- `GET /api/which-shapes/?route_id=` — step 1 of the registration cascade: distinct
  `GeoShape`s used by a route's stops in the current (`is_current=True`) feed.
- `GET /api/find-trips/?route_id=&service_id=&shape_id=` — step 2: candidate trips, each tagged
  with its matching `Run`'s lifecycle state (or `"UNKNOWN"`).

## Operations resources

Router-registered ViewSets over `operations.models`: `company`, `operator`, `data-provider`,
`vehicle` (filterable by `company`), `equipment`, `equipment-log` (filterable by `equipment`,
`data_provider`, `vehicle`), plus `position`, `stop-status`, `occupancy`, `congestion` from
`runs.models`. All except `CompanyViewSet` use `TokenAuthentication`.

## Auth & docs

- `POST /api/login/` — username/password → DRF auth `Token` + operator basic info.
- Global default authentication is `TokenAuthentication` (`databus/settings.py` `REST_FRAMEWORK`).
- `GET /api/docs/schema/` — serves the **static** file `api/realtime.yml` as a download
  (`api/views.py:89-94`); this is a hand-maintained schema, not the dynamic drf-spectacular route.
- `GET /api/docs/` — ReDoc page (`SpectacularRedocView`, clickjacking-exempt so it can be
  embedded). Note `drf_spectacular`'s dynamic OpenAPI generation is installed (`SPECTACULAR_SETTINGS`
  in `databus/settings.py`) but the `docs/schema/` route intentionally serves the static YAML
  instead of the generated schema — the dynamic route is unfinished.

## Configuration

No app-specific env vars; auth/schema settings come from `databus/settings.py`
(`REST_FRAMEWORK`, `SPECTACULAR_SETTINGS`).

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest api/ -q
```
`api/tests/` covers `company`, `find-trips`, and `which-shapes`; `make test` runs the full suite.

## Docs

- [REST API](../../docs/content/interfaces/rest-api.md)
- [Run lifecycle states](../../docs/content/runs/lifecycle-states.md)
