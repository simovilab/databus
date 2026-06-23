---
icon: lucide/compass
---

# Design Principles

Five architectural principles govern every decision in Databús. Violating one
of these is a signal that the architecture needs a deliberate discussion, not
a workaround.

Source: `ARCHITECTURE.md §4`.

---

## 1. Single writer per responsibility

Each concern has exactly one authoritative service that writes to it.

- Only the **realtime-engine** writes `vehicle:<id>:*` and `run:<id>:*` Redis
  keys from telemetry. The schedule-engine reads them but never writes them.
- Only the **schedule-engine** writes GTFS-RT feed files to
  `backend/feed/files/`.
- Only the **lifecycle actions** write `run:<id>:trip` and
  `vehicle:<id>:metadata`.

This rule prevents write conflicts and makes the data flow auditable: to find
out who wrote something, look at the key's namespace.

---

## 2. Explicit message semantics

Commands, observations, and assertions are distinct types with distinct
producers. They are not generic events or fire-and-forget notifications.

| Type | Producer | Meaning |
| --- | --- | --- |
| Command | Orchestrator (REST API / dispatcher) | An intentional request to do something |
| Observation | Realtime-engine | A derived fact detected from telemetry |
| Assertion | Schedule-engine (publisher) | A claim about what was published |

Mixing these types — e.g., having the realtime-engine accept REST commands
directly, or having the schedule-engine write lifecycle state — violates this
principle.

---

## 3. In-memory state is authoritative for real-time

Redis is the single source of truth for live operational state. PostgreSQL is
not used as a coordination mechanism for real-time decisions.

The schedule-engine reads Redis to build GTFS-RT feeds; it does not query the
database for current vehicle positions. The lifecycle FSM writes state to Redis
so the feed builder sees it immediately, without waiting for a database round
trip.

This is why the [Redis key reference](../data-model/redis-keys.md) is a
Tier-1 document: if you want to know what the system knows right now, that
is where you look.

---

## 4. Async-first, loosely coupled services

Services communicate through brokers, not synchronous calls. The MQTT broker
(NanoMQ) decouples vehicles from the realtime-engine. The Celery task queue
(via RabbitMQ) decouples the MQTT network thread from the heavy processing in
`process_position_update`. Beat schedules periodic tasks without requiring any
service to poll another.

The one deliberate exception is the REST API, which is synchronous by
definition — but even there, the heavy work (e.g., lifecycle FSM transitions
that write Redis) is kept out of the HTTP request/response cycle where
possible.

---

## 5. Auditability over raw data hoarding

Meaningful derived facts are preserved; raw signals are transient.

Raw GPS pings are not persisted individually. What is persisted is:

- The `RunLifecycleTransition` record for every FSM state change (with event,
  from-state, to-state, guards, actions, and timestamp).
- The `RunProgressEvent` record for stop-arrival events.
- GTFS-RT feed blobs (retained approximately one year) as durable snapshots of
  what was published.
- Position and occupancy records for historical analysis.

This keeps the database size manageable and keeps the audit trail focused on
what the system concluded, not every raw byte it received.
