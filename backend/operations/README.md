# Operations · fleet & operator domain

- **Purpose**: owns the fleet/operator domain models — companies, operators, telemetry equipment,
  and vehicles — that `runs` and `api` reference. No views of its own (`operations/views.py` is a
  placeholder; reads/writes go through `api`'s router-registered ViewSets).
- **Key modules**: `models.py` (all domain models), `admin.py` (Django admin registration).

## Models

| Model | Role |
| --- | --- |
| `Company` | The legal entity behind a GTFS `Agency` (via `linked_agency` M2M). |
| `Operator` | A driver/dispatcher/administrator; one-to-one with a Django `User`, M2M to `Company`. |
| `DataProvider` | Owner of telemetry `Equipment`, M2M to `Company`. |
| `Vehicle` | A fleet vehicle; FK to `Company`; amenity/accessibility/status choice fields. |
| `Equipment` | An onboard telemetry device (GPS/sensor unit); FK to `DataProvider` and `Vehicle`. Every `save()` appends a snapshot to `EquipmentLog` (`models.py:162-175`). |
| `Sensor` | A logical data feed registered on an `Equipment`, flagged by what it provides (`provides_position`, `provides_occupancy`, ...). `source_type` is one of `mqtt` / `http` / `both`; `source_http_url` is the polled URL and `source_json_mapping` its field mapping. |
| `EquipmentLog` | Immutable audit trail — one row per `Equipment.save()`. |

## `Sensor.source_type=http` → `fetch_positions`

`Sensor` rows with `status="ACTIVE"`, `provides_position=True`, and `source_type in {"http",
"both"}` are exactly what `realtime_engine.tasks.fetch_positions` polls every 10 seconds
(`realtime_engine/tasks.py:177-182`): it fetches each sensor's `source_http_url` through the
`"http"` adapter, filters to vehicles with an active run, and republishes readings on
`transit/vehicle/<id>/position` for the MQTT consumer path. `Equipment.vehicle` is what resolves a
sensor to a vehicle for the in-service filter.

## Data in / data out

- PostgreSQL only via the ORM — no Redis keys, no queues, no HTTP endpoints of its own.
- `logo`/`photo` `ImageField`s are written under `MEDIA_ROOT` (`companies/`, `operators/`,
  `data-providers/`).

## Configuration

No app-specific env vars.

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest operations/ -q
```
`operations/tests.py` is currently empty (Django's generated stub); coverage of this app's
behavior lives in `realtime_engine`'s `fetch_positions` tests. `make test` runs the full suite.

## Docs

- [Django Models](../../docs/content/data-model/django-models.md)
