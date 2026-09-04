---
icon: lucide/calendar
---

# Schedule Engine (GTFS Schedule side)

The `schedule_engine` Django app (`backend/schedule_engine/`) serves two
distinct roles:

1. **GTFS Schedule querying** — providing routes, trips, stops, and shapes to
   the operator UI and run-creation workflow.
2. **GTFS Realtime publishing** — building protobuf feed files from the Redis
   snapshot.

This page covers role 1. For role 2, see
[Data flow › GTFS Realtime publishing](../data-flow/gtfs-rt-publishing.md)
and [Interfaces › GTFS Realtime feeds](../interfaces/gtfs-rt-feeds.md).

---

## Builders — run UI helpers

`backend/schedule_engine/builders.py` is the **GTFS-RT assembler module** —
pure functions, no Django, no Channels, no Celery. It is the Django-free half
of the feed pipeline called by the Celery tasks in `tasks.py`.

Key functions:

| Function | Purpose |
| --- | --- |
| `build_vehicle_position_entity(r, run_id)` | Assemble one GTFS-RT VehiclePosition entity dict from Redis |
| `build_trip_update_entity(r, run_id)` | Assemble one GTFS-RT TripUpdate entity dict from Redis |
| `build_vehicle_positions_feed(r)` | Build the full VehiclePositions FeedMessage dict |
| `build_trip_updates_feed(r)` | Build the full TripUpdates FeedMessage dict |

Both feed-level functions iterate `runs:in_progress` (the Redis set of active
run IDs), call the per-entity helper, and skip `None` results.

The builders read Redis via the telemetry contract `from_redis` helpers and
never write to Redis or the database.

---

## Routing — query helpers

`backend/schedule_engine/routing.py` wires the WebSocket consumer to a Django
Channels routing pattern:

```python
websocket_urlpatterns = [
    re_path(r"ws/status/$", StatusConsumer.as_asgi()),
]
```

The `StatusConsumer` receives `status_message` group messages sent by
`build_trip_updates` (via `async_to_sync(channel_layer.group_send)`) and
forwards them to connected WebSocket clients.

---

## Fake stop times

`backend/schedule_engine/fake_stop_times.py` generates synthetic stop-time
projections from a static CSV (`aux_files/route_stops.csv`). This module was
used before the real server-side stop-time projection was implemented and is
retained for simulator compatibility.

Key constants:

| Constant | Value | Meaning |
| --- | --- | --- |
| `_UNCERTAINTY_S` | 120 | Default uncertainty in seconds |
| `_TIME_OFFSET_MIN_S` | 150 | Minimum random time offset |
| `_TIME_OFFSET_MAX_S` | 300 | Maximum random time offset |

!!! note "Temporary module"
    The `fake_stop_times` module is marked `# For the _fake_stop_times method (temporary!)`.
    The real projection lives in `runs/domain/progression/stop_times.py`.

---

## Celery tasks

`backend/schedule_engine/tasks.py` contains four Celery tasks routed to the
`schedule_engine` queue; three of them are on the beat schedule:

| Task | Schedule | Notes |
| --- | --- | --- |
| `build_vehicle_positions` | Every 15 s | Writes `vehicle_positions.{pb,json}` |
| `build_trip_updates` | Every 15 s | Writes `trip_updates.{pb,json}` + pushes WebSocket heartbeat |
| `build_schedule` | Daily | Exports the current GTFS Schedule zip via `feed.schedule.exporter.publish_gtfs_zip` |
| `build_alerts` | **Not scheduled** | **Stub** — returns the placeholder string `"Feed ServiceAlert built"`, writes no feed file. Its own docstring notes it is "Deliberately NOT registered in the Celery beat schedule." Callable directly (routed to `schedule_engine`), but beat never fires it. |

The schedule is configured in `backend/databus/celery.py` via `app.conf.beat_schedule`
and **not** in `django_celery_beat` admin (despite what `AGENTS.md` states).

---

## REST API for schedule queries

The `api` app exposes schedule data via DRF ViewSets registered in
`backend/api/urls.py`:

| Endpoint | Model | Notes |
| --- | --- | --- |
| `GET /api/agency/` | `feed.Agency` | Transit agencies |
| `GET /api/stops/` | `feed.Stop` | Stops; filterable by `stop_id`, `stop_name`, etc. |
| `GET /api/geo-stops/` | `feed.Stop` | GeoJSON stop representation |
| `GET /api/routes/` | `feed.Route` | Routes; filterable by `route_type`, `route_id` |
| `GET /api/trips/` | `feed.Trip` | Trips; filterable by `shape_id`, `direction_id`, `trip_id`, `route_id`, `service_id` |
| `GET /api/stop-times/` | `feed.StopTime` | Stop times; filterable by `trip_id`, `stop_id` |
| `GET /api/shapes/` | `feed.Shape` | Shapes |
| `GET /api/geo-shapes/` | `feed.GeoShape` | Geo shapes |
| `GET /api/calendars/` | `feed.Calendar` | Service calendars |
| `GET /api/calendar-dates/` | `feed.CalendarDate` | Service exceptions |
| `GET /api/service-today/` | — | Returns service_id list active on a given date |
| `GET /api/which-shapes/?route_id=` | — | Returns GeoShapes for a route |
| `GET /api/find-trips/?route_id=&service_id=&shape_id=` | — | Returns trips with scheduled times and run states |

See [Interfaces › REST API](../interfaces/rest-api.md) for the full endpoint
reference.
