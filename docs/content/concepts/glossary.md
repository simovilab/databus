---
icon: lucide/book-open
description: One canonical definition for every domain term used in the Databús codebase.
---

# Glossary

Canonical definitions for terms used throughout the Databús codebase and
documentation. When in doubt about terminology, this page wins.

---

## Run

An instance of a GTFS trip being executed by a specific vehicle and operator
on a specific date. A run ties together a `trip_id`, a `vehicle`, an
`operator`, a `start_date`, and a `start_time`. Every run has a UUID primary
key and progresses through the [lifecycle FSM](../runs/lifecycle-states.md).

A run is **not** the same as a GTFS trip. A trip is a schedule template; a run
is a single real-world execution of that template.

Source: `backend/runs/models.py::Run`, `backend/runs/README.md`.

---

## Trip

A GTFS Schedule entity describing a planned sequence of stops at specific
times for a given route and service day. Trips are imported from the agency's
GTFS feed and stored in `backend/feed/models.py::Trip`. During a run, the
trip provides the shape geometry, stop sequence, and scheduled times used for
map-matching and stop-time projection.

---

## Shape

A GTFS Schedule entity (`shapes.txt`) describing the geographic path a vehicle
follows on a trip. Databús stores both the point-sequence form (`Shape`) and a
PostGIS `LineString` form (`GeoShape`). The `GeoShape.geometry` field is what
the map-matching algorithm (`runs/domain/progression/compute.py`) projects GPS
positions onto.

---

## Progression

The server-computed description of where a vehicle is relative to its assigned
trip's stops. Progression is **not** an edge-sent signal — the edge never
sends progression. It is computed server-side from GPS position via
polyline projection and haversine distance comparison against stop coordinates.

The result is stored in `run:<id>:vehicle_stop_status` as one of three GTFS-RT
`VehicleStopStatus` values: `INCOMING_AT`, `STOPPED_AT`, or `IN_TRANSIT_TO`.

!!! note "Decommissioned leaf"
    Early designs had the edge device publish a `progression` MQTT leaf. That
    leaf is decommissioned. The MQTT consumer does not subscribe to
    `transit/vehicle/+/progression`; any such messages are silently dropped.

---

## Stop status (`vehicle_stop_status`)

The three-valued GTFS-RT enum that describes a vehicle's relationship to the
next stop on its trip:

| Value | Meaning |
| --- | --- |
| `INCOMING_AT` | Vehicle is approaching the stop |
| `STOPPED_AT` | Vehicle is at the stop |
| `IN_TRANSIT_TO` | Vehicle is in transit toward the next stop |

Written to `run:<id>:vehicle_stop_status` by the server progression step.
Read by the GTFS-RT feed builder and the
[RunCompletedDetector](../runs/detection.md).

!!! note "Terminology: progression terms"
    Three related terms are easy to conflate:

    - **Progression / server-side progression** — the *act* of map-matching a GPS
      position to the trip shape to determine where the vehicle is relative to its
      stops. This is a computation, not a stored value.
    - **`vehicle_stop_status`** — the *output* of that computation: one of
      `INCOMING_AT`, `STOPPED_AT`, or `IN_TRANSIT_TO` (GTFS-RT `VehicleStopStatus`
      enum), stored in `run:<id>:vehicle_stop_status`.
    - **Progress FSM** — a *separate, not-yet-implemented* motion state machine
      tracking whether the vehicle is physically moving (`IS_MOVING`), stationary
      (`IS_STOPPED`), or paused (`IS_PAUSED`). Distinct from both progression and
      stop status.

---

## Observation

A message produced by the realtime-engine when it detects a meaningful state
change from telemetry — e.g., `run_tracking_started` or `run_completed`. In
the [messaging model](../architecture/messaging.md), observations are "derived
facts" emitted by the engine and consumed by the orchestrator. The AMQP event
publisher (`backend/messages/publisher.py`) is the intended transport.

See [Interfaces › AMQP event semantics](../interfaces/amqp-events.md).

---

## Command

A synchronous operator- or API-driven request to transition a run's lifecycle.
Examples: `RUN_CONFIRMED`, `RUN_COMPLETED` (when manually triggered),
`RUN_INTERRUPTED`, `RUN_SHORT_TURNED`. Commands arrive via the REST API
(`POST /api/runs/<id>/update/`). See the [messaging model](../architecture/messaging.md)
for how commands relate to observations and assertions.

The distinction between commands and detected facts is central to understanding
the lifecycle. See [Run lifecycle › Commands vs detected facts](../runs/commands-vs-detections.md).

---

## Assertion

A message type in the ARCHITECTURE.md model: a claim by the schedule-engine
about the published GTFS-RT output (e.g., "VehiclePositions feed written with
N entities"). Currently not emitted (the publisher is a stub).

---

## Detector

A pure function (no I/O, unit-testable) that, given the current run state and
a trigger signal, decides whether a lifecycle event should fire and which one.
Detectors live in `backend/runs/domain/detection/`.

The `detect_from_telemetry` and `detect_from_scan` impure wrappers call them
and apply the result (enqueue the lifecycle event, write Redis, etc.).

See [Run lifecycle › Detection layer](../runs/detection.md).

---

## Bootstep (Celery bootstep)

A Celery worker lifecycle hook (`celery.bootsteps.StartStopStep`) that runs
custom code when a worker starts or stops. Databús uses this mechanism to run
the MQTT subscriber inside the `realtime-engine` worker process without a
separate container.

The bootstep (`MQTTConsumerStep`) is registered in `backend/databus/celery.py`
but only activates when `MQTT_CONSUMER_ENABLED=true`.

See [Data flow › Telemetry ingestion](../data-flow/telemetry-ingestion.md).

---

## Telemetry leaf

One data stream from an edge device, identified by the last segment of its MQTT
topic. Databús subscribes to two leaves:

| Leaf | Topic | Redis key |
| --- | --- | --- |
| `position` | `transit/vehicle/<id>/position` | `vehicle:<id>:position` |
| `occupancy` | `transit/vehicle/<id>/occupancy` | `vehicle:<id>:occupancy` |

Each leaf has a typed contract in `backend/runs/domain/telemetry/` with
`validate_for_write` (strict, for the ingestion path) and `from_redis`
(tolerant, for the feed builder path).

---

## Telemetry contract

The module in `backend/runs/domain/telemetry/` that owns the field names,
types, validation rules, and Redis encoding for one Redis key. Contracts are
the single source of truth for what goes in and out of each key — no other
module hardcodes field names.

See [Data model › Telemetry contracts](../data-model/telemetry-contracts.md).
