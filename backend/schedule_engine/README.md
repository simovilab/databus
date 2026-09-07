# schedule_engine

Celery worker (queue `schedule_engine`) that builds the GTFS-RT feeds and the
GTFS Schedule zip. It only ever **reads** the real-time Redis state —
`realtime_engine` is the sole writer.

## Tasks (`tasks.py`)

| Task | Beat schedule | What it does |
|---|---|---|
| `build_vehicle_positions` | every 15 s | Reads Redis via `builders.build_vehicle_positions_feed`, writes `feed/files/vehicle_positions.json` + `.pb` (GTFS-RT `FeedMessage`, protobuf). |
| `build_trip_updates` | every 15 s | Same, via `build_trip_updates_feed` → `feed/files/trip_updates.json` + `.pb`. Also broadcasts a build-status message (`last_update`, count of `runs:in_progress`) to the `status` WebSocket group. |
| `build_schedule` | daily | Exports the current GTFS `Feed` (`is_current=True`) to a zip via `feed.schedule.exporter.publish_gtfs_zip`; skips (returns `None`, logs a warning) if no current feed exists. |
| `build_alerts` | **not scheduled** | Placeholder — returns a fixed string. The ServiceAlert feed builder is not yet implemented and this task is deliberately not registered in `databus/celery.py`'s `beat_schedule`. |

Beat schedule is defined in `databus/celery.py` (`app.conf.beat_schedule`),
not Django admin.

`build_vehicle_positions_feed` / `build_trip_updates_feed`
(`builders.py`) read the entity hashes `realtime_engine` writes —
`run:<id>` / `run:<id>:trip` / `run:<id>:vehicle_stop_status` /
`run:<id>:stop_time_updates`, `vehicle:<id>:position` /
`vehicle:<id>:occupancy` / `vehicle:<id>:metadata` — over the run IDs in
`runs:in_progress`. See `runs/domain/telemetry/keys.py` for the canonical
key templates.

## WebSocket consumer (`consumers.py`, `routing.py`)

`StatusConsumer` (`AsyncWebsocketConsumer`) joins/broadcasts on the `status`
channel-layer group at `ws/status/`. `build_trip_updates` sends a status
message to that group after each build; `StatusConsumer.receive` also
re-broadcasts any client-sent message to the group, and `status_message`
forwards group events out to each connected socket.

## Notes

- `filters.py` has been removed from this app; there are no remaining
  references to it.
- No feed-building code runs inline in the WebSocket path — `consumers.py`
  only relays status, it never reads Redis or writes feed files itself.
