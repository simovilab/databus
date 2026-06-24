---
icon: lucide/bus
description: What Databús is, who built it, and the problem it solves.
---

# What is Databús

Databús is a distributed transit data platform that ingests real-time vehicle
telemetry, maintains authoritative in-memory operational state, and publishes
GTFS Realtime feeds to transit consumers. It was built at the
[SIMOVI Lab](https://simovilab.org) (UCR — Universidad de Costa Rica) for the
Costa Rica public transit network, with `America/Costa_Rica` as the canonical
timezone.

## The problem it solves

Transit agencies need live vehicle location and schedule-adherence data to
serve passengers and dispatchers. Raw GPS pings from vehicles are noisy and
ambiguous: they must be matched to a specific trip and route before they become
useful. Databús sits between the vehicle fleet and downstream consumers and
handles that translation.

```text
Vehicle (GPS + occupancy)
        │  MQTT
        ▼
  Databús telemetry ingestion
        │
        ├─ server-side map-matching → vehicle stop status
        ├─ run lifecycle FSM        → confirmed/in-progress/completed
        ├─ stop-time projections    → predicted arrival times
        └─ GTFS-RT feed builder    → VehiclePositions + TripUpdates (protobuf)
```

## What it does

1. **Ingests** MQTT telemetry (position and occupancy) from vehicles or
   simulators on topics `transit/vehicle/<id>/{position,occupancy}`.
2. **Maintains** an authoritative Redis snapshot of every active run:
   current position, stop relationship, occupancy, and trip assignment.
3. **Produces** GTFS Realtime feeds — `vehicle_positions.pb` and
   `trip_updates.pb` — refreshed every 15 seconds, written to
   `backend/feed/files/`.
4. **Manages** run lifecycle: from a dispatcher creating a run
   (`POST /api/create-run`) through detection of tracking, motion,
   completion, and eventual expiry.
5. **Persists** durable operational traces in PostgreSQL (with PostGIS for
   geospatial queries) for auditing and analytics.

## What it is not

Databús is not a passenger-facing app. It provides the data infrastructure
that powers such apps. It does not directly control vehicles, issue passenger
alerts (the ServiceAlert builder is a future work item), or perform batch
scheduling — that belongs to the upstream agency's GTFS Schedule data.

## Context

| Attribute | Value |
| --- | --- |
| Institution | SIMOVI Lab, UCR (bUCR / Universidad de Costa Rica) |
| Timezone | `America/Costa_Rica` |
| Language | Spanish in the field (operator UI); English in code and docs |
| Contact | simovi@ucr.ac.cr |
| License | Apache 2.0 |

## Technology stack

| Layer | Technology |
| --- | --- |
| Control plane | Django / Daphne (ASGI), Django REST Framework |
| Task workers | Celery (two queues: `realtime_engine`, `schedule_engine`) |
| MQTT ingestion | NanoMQ broker + paho-mqtt Celery bootstep |
| In-memory state | Redis |
| Durable storage | PostgreSQL + PostGIS |
| Async messaging | RabbitMQ |
| Analytics | Prefect |
| Frontend | Nuxt |
| Infrastructure | Docker Compose + Traefik (production) |

See [Architecture › Services & mandates](../architecture/services.md) for the
full service-by-service breakdown and
[Data model › Redis state keys](../data-model/redis-keys.md) for the
authoritative state reference.
