# API Reference

Base URL: `http://localhost:8000/api/` (dev) — `https://<host>/api/` (prod)

Interactive docs (ReDoc): `/api/docs/`

All responses follow [JSON:API](https://jsonapi.org/) format:
```json
{ "data": [ { "id": "...", "type": "...", "attributes": {}, "relationships": {} } ] }
```

---

## Authentication

Most endpoints are public. Write operations (POST/PUT/PATCH/DELETE) require a token.

```http
POST /api/login/
Content-Type: application/json

{ "username": "...", "password": "..." }
```

Response:
```json
{ "token": "abc123", "operator_id": 1, "first_name": "Ana", "last_name": "García" }
```

Pass the token in subsequent requests:
```
Authorization: Token abc123
```

---

## Real-time endpoints

Backed by **Redis** (vehicles) and the publisher's `trip_updates.json` feed file (predictions).
These reflect the live operational state — data is at most 15 seconds old.

### GET /api/realtime/vehicles/

All vehicles currently on a run.

**Filters**

| Parameter | Description |
|---|---|
| `filter[route]` | Only vehicles on this route |
| `filter[trip]` | Only the vehicle running this trip |
| `filter[vehicle]` | Exact vehicle ID match |

**Example**
```
GET /api/realtime/vehicles/?filter[route]=bUCR_L1
```

**Response**
```json
{
  "data": [
    {
      "id": "unit-10",
      "type": "vehicle",
      "attributes": {
        "label": "Bus 10",
        "latitude": 9.9365,
        "longitude": -84.0511,
        "speed": 14.0,
        "bearing": 270.0,
        "current_status": "IN_TRANSIT_TO",
        "current_stop_sequence": 5,
        "stop_id": "UCR_0_05",
        "updated_at": "2024-01-15T14:30:02+00:00",
        "occupancy_status": "FEW_SEATS_AVAILABLE",
        "occupancy_percentage": 40
      },
      "relationships": {
        "trip":  { "data": { "id": "trip-bUCR_L1-0700", "type": "trip" } },
        "route": { "data": { "id": "bUCR_L1", "type": "route" } },
        "stop":  { "data": { "id": "UCR_0_05", "type": "stop" } }
      }
    }
  ]
}
```

---

### GET /api/realtime/predictions/

Predicted arrival/departure times at upcoming stops, derived from the publisher's GTFS-RT feed.

Returns `503` if the feed file hasn't been generated yet.

**Filters**

| Parameter | Description |
|---|---|
| `filter[trip]` | Predictions for a specific trip |
| `filter[stop]` | Next predictions at a given stop across all trips |
| `include` | `stop` — sideloads stop name/coordinates in `included` |

**Example**
```
GET /api/realtime/predictions/?filter[stop]=UCR_0_05&include=stop
```

**Response**
```json
{
  "data": [
    {
      "id": "prediction-UCR_0_05-trip-001-5",
      "type": "prediction",
      "attributes": {
        "arrival_time": "2024-01-15T14:32:30+00:00",
        "departure_time": "2024-01-15T14:32:30+00:00",
        "stop_sequence": 5,
        "stop_id": "UCR_0_05",
        "direction_id": 0,
        "schedule_relationship": "SCHEDULED",
        "uncertainty": 120
      },
      "relationships": {
        "stop":    { "data": { "id": "UCR_0_05", "type": "stop" } },
        "trip":    { "data": { "id": "trip-001", "type": "trip" } },
        "route":   { "data": { "id": "bUCR_L1", "type": "route" } },
        "vehicle": { "data": { "id": "unit-10", "type": "vehicle" } }
      }
    }
  ],
  "included": [
    {
      "id": "UCR_0_05",
      "type": "stop",
      "attributes": { "name": "Parada UCR 05", "latitude": 9.9366, "longitude": -84.0512 }
    }
  ]
}
```

---

## Schedule endpoints

Backed by **PostgreSQL** GTFS Schedule data. All endpoints filter automatically to the current feed (`feed__is_current=True`).

### GET /api/schedule/routes/

| Filter | Description |
|---|---|
| `filter[type]` | Route type: `0`=tram, `1`=subway, `2`=rail, `3`=bus, `4`=ferry |
| `filter[stop]` | Routes that serve this stop ID |

**Response attributes:** `short_name`, `long_name`, `description`, `type`, `color`, `text_color`, `sort_order`

---

### GET /api/schedule/stops/

| Filter | Description |
|---|---|
| `filter[route]` | Stops served by this route |
| `filter[id]` | Exact `stop_id` match |
| `filter[location_type]` | `0`=stop/platform, `1`=station, `2`=entrance |

**Response attributes:** `name`, `description`, `latitude`, `longitude`, `location_type`, `wheelchair_boarding`

---

### GET /api/schedule/trips/

| Filter | Description |
|---|---|
| `filter[route]` | Trips on this route |
| `filter[direction_id]` | `0` or `1` |
| `filter[service]` | Trips for this service ID |

**Response attributes:** `headsign`, `short_name`, `direction_id`, `wheelchair_accessible`, `bikes_allowed`

**Relationships:** `route`, `service`, `shape`

---

### GET /api/schedule/shapes/

Polyline geometries for map rendering (GeoJSON LineString).

| Filter | Description |
|---|---|
| `filter[route]` | Shapes used by trips on this route |

**Response attributes:** `geometry` (GeoJSON), `name`, `from`, `to`

---

### GET /api/schedule/schedules/

Scheduled arrival/departure times from `stop_times.txt`.

**At least one of `filter[trip]`, `filter[stop]`, or `filter[route]` is required.** Returns `400` otherwise.

| Filter | Description |
|---|---|
| `filter[trip]` | All stops for this trip |
| `filter[stop]` | All scheduled visits to this stop |
| `filter[route]` | All stop times for trips on this route |
| `filter[direction_id]` | `0` or `1` |
| `filter[min_time]` | Earliest departure time (`HH:MM:SS`) |
| `filter[max_time]` | Latest departure time (`HH:MM:SS`) |

**Response attributes:** `arrival_time`, `departure_time`, `stop_sequence`, `timepoint`, `pickup_type`, `drop_off_type`

**Relationships:** `stop`, `trip`

**Example — next departures from a stop in the morning:**
```
GET /api/schedule/schedules/?filter[stop]=UCR_0_01&filter[min_time]=07:00:00&filter[max_time]=09:00:00
```

---

### GET /api/schedule/services/

Calendar entries describing which days a service operates.

| Filter | Description |
|---|---|
| `filter[id]` | Exact `service_id` match |
| `filter[route]` | Services that operate on this route |

**Response attributes:** `start_date`, `end_date`, `valid_days` (array of weekday indexes, 0=Monday)

---

### GET /api/schedule/route-patterns/

Distinct travel patterns — one resource per unique `(route, direction, shape)` combination.
Useful for rendering route variants on a map.

| Filter | Description |
|---|---|
| `filter[route]` | Patterns for this route |
| `filter[direction_id]` | `0` or `1` |

**Response attributes:** `direction_id`

**Relationships:** `route`, `representative_trip`

---

## Common query patterns

**"Show me all buses on route L1 right now"**
```
GET /api/realtime/vehicles/?filter[route]=bUCR_L1
```

**"When does the next bus arrive at stop UCR_0_05?"**
```
GET /api/realtime/predictions/?filter[stop]=UCR_0_05&include=stop
```

**"What is the scheduled timetable for trip X?"**
```
GET /api/schedule/schedules/?filter[trip]=trip-bUCR_L1-0700
```

**"What stops does route L1 serve?"**
```
GET /api/schedule/stops/?filter[route]=bUCR_L1
```

**"Draw route L1 on a map"**
```
GET /api/schedule/shapes/?filter[route]=bUCR_L1
```

**"Is service running today?"**
```
GET /api/service-today/
GET /api/service-today/?date=2024-01-15
```
