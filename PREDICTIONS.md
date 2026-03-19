# MBTA Predictions — Architecture Reference

This document describes exactly how the MBTA V3 API handles real-time vehicle tracking,
stop sequencing, and arrival predictions. It is written as a design reference for building
a compatible or inspired system — specifically for a university transit API that will
generate a GTFS-RT feed and an ETA prediction suite.

---

## 1. Underlying standard: GTFS-RT

MBTA's real-time system is a JSON:API wrapper around **GTFS Realtime (GTFS-RT)**, the
Google-originated protobuf feed standard. Everything below maps to GTFS-RT concepts.
Understanding the standard first makes the API design self-explanatory.

GTFS-RT defines three feed message types:

| Feed | GTFS-RT entity | MBTA V3 endpoint |
|---|---|---|
| Vehicle positions | `VehiclePosition` | `GET /vehicles` |
| Trip updates (ETAs) | `TripUpdate` + `StopTimeUpdate[]` | `GET /predictions` |
| Service alerts | `Alert` | `GET /alerts` |

Your university system needs to generate all three. Start with vehicle positions,
then trip updates. Alerts are optional for phase 1.

---

## 2. Vehicle position data (`/vehicles`)

### What the MBTA API returns per vehicle

```json
{
  "id": "y1795",
  "type": "vehicle",
  "attributes": {
    "label":                "1795",
    "latitude":             42.3601,
    "longitude":            -71.0589,
    "speed":                14.0,
    "bearing":              270,
    "current_status":       "IN_TRANSIT_TO",
    "current_stop_sequence": 14,
    "stop_id":              "70196",
    "updated_at":           "2024-01-15T14:31:42-05:00",
    "direction_id":         0,
    "occupancy_status":     "MANY_SEATS_AVAILABLE"
  },
  "relationships": {
    "trip":  { "data": { "id": "trip-66-12345", "type": "trip" } },
    "route": { "data": { "id": "66",            "type": "route" } },
    "stop":  { "data": { "id": "70196",         "type": "stop" } }
  }
}
```

### `current_status` — the three states

This is a **VehicleStopStatus** enum from GTFS-RT. It has exactly three values:

```
INCOMING_AT   — vehicle is approaching the referenced stop (< ~200m away)
STOPPED_AT    — vehicle is currently at the referenced stop (doors open or just closed)
IN_TRANSIT_TO — vehicle has departed the previous stop and is traveling to the referenced stop
```

**Critical semantics:** `stop_id` and `current_stop_sequence` always reference the
**same stop**, but what that stop *means* depends on the status:

| Status | What `stop_id` / `stop_sequence` refers to |
|---|---|
| `IN_TRANSIT_TO` | The **next** stop — where the vehicle is heading |
| `INCOMING_AT` | The **next** stop — vehicle is nearly there |
| `STOPPED_AT` | The **current** stop — vehicle is there now |

This asymmetry is the most common source of bugs when building a tracker.
Always branch on status before interpreting the stop reference.

### `current_stop_sequence`

This integer is the `stop_sequence` from the static GTFS `stop_times.txt` file
for this trip. It is **not** a simple index — it is the value from the schedule
and can have gaps (e.g., 1, 3, 5, 8...) depending on how the agency produced
the GTFS data. MBTA typically uses consecutive integers.

It is scoped to the **trip**, not the route. Two trips on the same route serving
the same stop can have different `stop_sequence` values if they skip stops.

### `direction_id`

Binary: `0` or `1`. Maps to the two directions a route travels. MBTA defines
direction names per route (e.g., route 66: `0 = Harvard Square`, `1 = Dudley Station`).
These are stored in the static GTFS `trips.txt` file and exposed via `/routes` as
`direction_destinations`.

---

## 3. Prediction data (`/predictions`)

### Query pattern

```
GET /predictions?filter[trip]={tripId}&include=stop&sort=stop_sequence
```

The `include=stop` parameter causes stop names and coordinates to be sideloaded in
the `included` array of the response — avoiding a separate stop lookup per prediction.

### What one prediction object looks like

```json
{
  "id": "prediction-70196-trip-66-12345-1",
  "type": "prediction",
  "attributes": {
    "arrival_time":    "2024-01-15T14:35:00-05:00",
    "departure_time":  "2024-01-15T14:35:30-05:00",
    "stop_sequence":   14,
    "direction_id":    0,
    "schedule_relationship": "SCHEDULED",
    "status":          null
  },
  "relationships": {
    "stop":    { "data": { "id": "70196", "type": "stop" } },
    "trip":    { "data": { "id": "trip-66-12345", "type": "trip" } },
    "route":   { "data": { "id": "66", "type": "route" } },
    "vehicle": { "data": { "id": "y1795", "type": "vehicle" } }
  }
}
```

### The `included` sidecar for stop names

```json
"included": [
  {
    "id": "70196",
    "type": "stop",
    "attributes": {
      "name":      "Harvard Square",
      "latitude":  42.3736,
      "longitude": -71.1190,
      "platform_code": null
    }
  }
]
```

### What predictions cover

The predictions endpoint returns **only stops remaining in the trip** from the
vehicle's current position forward. Stops already passed are absent. This means:

- `predictions[0]` = the next stop (or current stop if `STOPPED_AT`)
- `predictions[N-1]` = the final stop of the trip
- A stop disappears from the array ~30s after departure

For past stops, there is no "actual arrival time" available through this API.
Historical actuals require the GTFS-RT `TripUpdate` archive feed or a separate
data warehouse.

### `schedule_relationship`

```
SCHEDULED  — prediction is operating as planned
SKIPPED    — this stop will be skipped (vehicle not stopping here)
NO_DATA    — no real-time data available; fall back to static schedule
UNSCHEDULED — an added stop not in the static GTFS
```

Your ETA model output should map to these states. If confidence is low, emit
`NO_DATA` rather than a bad prediction — downstream consumers know to use the
static schedule as fallback.

---

## 4. How `stop_sequence` links vehicles to predictions

The vehicle's `current_stop_sequence` and the predictions' `stop_sequence` values
are on the same integer scale for the same trip. This is what makes positional
resolution possible:

```
Vehicle: current_stop_sequence = 14, status = IN_TRANSIT_TO
Predictions: [..., {sequence: 13, arrivalTime: "14:32"}, {sequence: 14, arrivalTime: "14:35"}, ...]

→ sequence 13 = stop just passed (highest seq < 14)
→ sequence 14 = next stop (matches vehicle's seq)
```

```
Vehicle: current_stop_sequence = 14, status = STOPPED_AT
Predictions: [{sequence: 14, arrivalTime: "14:35"}, {sequence: 15, arrivalTime: "14:38"}, ...]

→ sequence 14 = current stop (vehicle just arrived)
→ sequence 15 = next stop
```

**Note:** when `STOPPED_AT`, sequence 14's prediction entry is still present briefly
(a few seconds after arrival) before disappearing. The arrival time on it reflects
the predicted time, not the actual — MBTA does not backfill actuals into this feed.

---

## 5. Trip data (`/trips`)

```
GET /trips/{tripId}
```

```json
{
  "id": "trip-66-12345",
  "attributes": {
    "headsign":    "Dudley Station",
    "name":        "66-12345",
    "direction_id": 0,
    "block_id":    "B-1234",
    "wheelchair_accessible": 1,
    "bikes_allowed": 0
  },
  "relationships": {
    "route":   { "data": { "id": "66" } },
    "shape":   { "data": { "id": "660012" } },
    "service": { "data": { "id": "FALL2024-66-Weekday" } }
  }
}
```

`headsign` is the human-facing destination sign shown on the bus. For a university
system, this maps to the route's displayed terminus.

`block_id` identifies the vehicle block — the sequence of trips a single physical
vehicle serves during a day. This enables dead-heading detection: if trip A ends
at stop X and the next trip in the block starts at stop Y ≠ X, the bus is
repositioning between trips.

---

## 6. The static schedule baseline (`/schedules`)

Predictions layer on top of the static schedule. When a vehicle has no real-time
data, consumers fall back to:

```
GET /schedules?filter[trip]={tripId}&filter[stop_sequence]=14
```

This returns the scheduled (non-predicted) arrival time from the GTFS `stop_times.txt`.
The prediction's `schedule_relationship: "NO_DATA"` signals this fallback condition.

Your system should maintain this two-tier model:
1. **Static schedule** — always available, baked into the GTFS feed
2. **Real-time prediction** — overlays the schedule when a vehicle is active

---

## 7. Feed architecture for a university system

### GTFS-RT feed generation

Your feed generator needs to emit two protobuf feeds at a regular interval
(MBTA publishes at ~5-10s):

**Feed 1: VehiclePositions**
```
FeedMessage
  header { gtfs_realtime_version: "2.0", timestamp: <unix> }
  entity {
    id: "vehicle-BUS01"
    vehicle {
      trip { trip_id: "trip-R1-0700", route_id: "R1", direction_id: 0 }
      position { latitude: ..., longitude: ..., speed: ..., bearing: ... }
      current_stop_sequence: 5
      stop_id: "STOP_42"
      current_status: IN_TRANSIT_TO
      timestamp: <unix>
      vehicle { id: "BUS01", label: "Bus 01" }
    }
  }
```

**Feed 2: TripUpdates (your ETA predictions)**
```
FeedMessage
  header { gtfs_realtime_version: "2.0", timestamp: <unix> }
  entity {
    id: "tripupdate-trip-R1-0700"
    trip_update {
      trip { trip_id: "trip-R1-0700" }
      vehicle { id: "BUS01" }
      stop_time_update {
        stop_sequence: 5
        stop_id: "STOP_42"
        arrival { time: <unix+90s>, uncertainty: 30 }
        departure { time: <unix+120s>, uncertainty: 30 }
        schedule_relationship: SCHEDULED
      }
      stop_time_update {
        stop_sequence: 6
        stop_id: "STOP_43"
        arrival { time: <unix+210s>, uncertainty: 45 }
        ...
      }
    }
  }
```

`uncertainty` is the ±seconds confidence interval on the prediction. Surface this
in your UI — it is the most honest signal you can give users.

### JSON:API wrapper (MBTA-style)

If you're building an HTTP API on top of the protobuf feeds (as MBTA does), structure
it so that:

1. The protobuf feeds are your source of truth (low-latency, machine-readable)
2. The JSON:API is a read layer that parses and re-exposes them (human/browser-friendly)
3. The JSON:API supports `include=` for sideloading related resources to reduce round-trips
4. Cache aggressively at the JSON:API layer (predictions: 5-10s TTL, shapes: hours TTL)

### Recommended endpoints for a MBTA-compatible design

```
GET /vehicles?filter[route]={routeId}
GET /vehicles?filter[trip]={tripId}

GET /predictions?filter[trip]={tripId}&include=stop
GET /predictions?filter[stop]={stopId}               ← useful for "next buses at this stop"

GET /trips/{tripId}
GET /schedules?filter[trip]={tripId}

GET /routes
GET /stops?filter[route]={routeId}&filter[direction_id]={0|1}
GET /shapes?filter[route]={routeId}&sort=-priority
```

The `filter[stop]={stopId}` predictions endpoint is one the MBTA exposes that this
web UI does not yet use — it powers "next bus at stop X" boards.

---

## 8. Using status flags for ETA model training and validation

The three status flags create natural ground-truth events in your GPS stream.
This is one of the most useful aspects of the GTFS-RT design for ML purposes.

### Training signal extraction

```
STOPPED_AT at stop S, timestamp T1
  → vehicle arrived at S at approximately T1
  → T1 is your ground-truth arrival time

First IN_TRANSIT_TO (or INCOMING_AT) at stop S+1 after T1 = T2
  → vehicle departed S at approximately T2
  → dwell time at S = T2 - T1

STOPPED_AT at stop S+1, timestamp T3
  → travel time from S to S+1 = T3 - T2
  → this is your regression target for the S→S+1 segment model
```

From a continuous GPS log you can reconstruct the full event sequence:

```
[IN_TRANSIT_TO S1, t=0]
[INCOMING_AT S1, t=85]       ← optional transition
[STOPPED_AT S1, t=92]        ← ARRIVAL EVENT: label = t=92
[IN_TRANSIT_TO S2, t=127]    ← DEPARTURE EVENT: dwell = 35s
[STOPPED_AT S2, t=203]       ← next arrival
```

### Feature candidates for the ETA model

Per-segment features (S_n → S_{n+1}):
- Distance between stops (from shapes)
- Number of stops remaining in trip
- Time of day (rush hour bins or continuous)
- Day of week
- Historical mean travel time for this segment
- Historical variance for this segment
- Current speed of vehicle at departure
- Headway from previous vehicle on same route
- Dwell time at previous stop (congestion signal)
- Weather (if available)

Global state features:
- Route load factor (how many active vehicles on route)
- Network-wide congestion index

### Validation metrics

When comparing your model's predicted `arrival_time` against ground-truth `STOPPED_AT` events:

```
MAE  = mean(|predicted_arrival - actual_arrival|)   in seconds
RMSE = sqrt(mean((predicted_arrival - actual_arrival)^2))
Coverage at 60s = fraction of predictions within ±60s of actual
```

The `uncertainty` field in your GTFS-RT output should be calibrated:
a prediction with `uncertainty=30` should have ~68% of actuals fall within ±30s.
Calibration plots (predicted CI coverage vs. actual coverage) are the right diagnostic.

### Status transitions as model validation signals

During live operation, you can compare your model's predicted arrival for stop S
against the `STOPPED_AT` event for that stop as it happens — no separate test set needed.
This gives you **continuous production validation** at every stop, every trip.

A degradation alert fires if rolling MAE over the last N trips exceeds a threshold.
The `schedule_relationship: NO_DATA` field is the right escape hatch — emit it
when your model confidence drops below a threshold rather than publishing a bad prediction.

### Edge cases to model explicitly

- **Short-turn**: vehicle terminates early, does not complete the trip. Detectable
  when `STOPPED_AT` fires at a non-terminal stop and no subsequent `IN_TRANSIT_TO`
  is observed within a time window.
- **Skip stop**: stop is bypassed without `STOPPED_AT`. Emit `SKIPPED` in your
  TripUpdate for that stop.
- **Layover at terminus**: vehicle is `STOPPED_AT` the last stop for an extended
  period before starting the return trip. Filter dwell > threshold from travel-time
  regression targets.
- **GPS dropout**: position stream goes silent. Freeze last known position,
  degrade uncertainty, eventually emit `NO_DATA`.
- **Trip assignment change**: vehicle is reassigned mid-trip. `trip_id` changes.
  Close predictions for the old trip, open for the new one.

---

## 9. Caching strategy

| Resource | Change frequency | Recommended TTL |
|---|---|---|
| Routes, stops, shapes | Daily (GTFS static release) | 1 hour |
| Trip details | Daily | 1 hour |
| Vehicle positions | ~5s | 5–10s |
| Predictions | ~10s | 10–30s |
| Schedules (static) | Daily | 24 hours |

Predictions should not be cached longer than ~30s — stale predictions are worse
than no predictions (users making real decisions based on them).

---

## 10. Key design decisions to carry forward

1. **Separate static and real-time feeds.** GTFS static is your ground truth for
   scheduled operations. GTFS-RT is the delta. Never conflate them in your data model.

2. **`stop_sequence` is the join key.** Use it, not stop order in an array, to link
   vehicle position to prediction. Stop IDs can repeat on circular routes; sequences
   don't within a trip.

3. **Always include `uncertainty`.** It is the single most honest thing your
   prediction system can communicate. A bad estimate with correct uncertainty is
   better than a confident wrong one.

4. **Emit `NO_DATA` as a first-class state.** When the vehicle hasn't been seen
   recently, or the model confidence is below threshold, tell consumers explicitly.
   They will use the static schedule. This is correct behavior.

5. **`STOPPED_AT` events are your primary ground truth.** Log every one with a
   server-side timestamp. This log is your training data, your validation set,
   and your SLA evidence.

6. **Direction is a first-class field on every resource.** Stops for direction 0
   and direction 1 can overlap (same physical stop, different sequence number in
   the trip). Filter stops by direction everywhere — not doing so is the second
   most common tracker bug.

7. **Block ID enables fleet efficiency monitoring.** Track block assignments to
   detect dead-heading, missed trips, and vehicle swaps.
