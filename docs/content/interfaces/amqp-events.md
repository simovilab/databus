---
icon: lucide/git-branch
description: AMQP event semantics for the databus.events direct exchange — routing-key namespace, message envelope, and current stub status.
---

# AMQP Event Semantics

Databús® uses RabbitMQ as its internal async message backbone. The design
defines three message types routed through a single direct exchange, and the
routing-key namespace for run-lifecycle events.

!!! warning "Publisher stub — not yet wired"
    The AMQP event publisher (`backend/messages/publisher.py`) is currently a
    **stub**. The `publish_event` function prints to stdout instead of
    publishing to RabbitMQ. The exchange declaration and producer are
    instantiated at module import, but no message is actually sent.

    Domain event emission is **designed, not fully wired**. This page
    documents the intended semantics so integrators can plan against the
    target API.

---

## Exchange

| Attribute | Value |
| --- | --- |
| Name | `databus.events` |
| Type | `direct` |
| Protocol | AMQP 0-9-1 via Kombu |
| Broker | RabbitMQ (`message-broker` service) |

---

## Message types

From `ARCHITECTURE.md §6`:

| Type | Producer | Meaning |
| --- | --- | --- |
| **Command** | Orchestrator (REST API) | An intentional request directed at another service |
| **Observation** | Realtime-engine | A derived fact detected from telemetry |
| **Assertion** | Schedule-engine (publisher) | A claim about what was published to GTFS-RT |

All internal messages share a common envelope and include correlation metadata
(intended; not yet enforced by the stub).

---

## Routing keys — `runs.*` namespace

The docstring in `backend/messages/publisher.py` sketches the intended
routing-key set:

| Routing key | Meaning |
| --- | --- |
| `runs.submission.requested` | A run creation was requested |
| `runs.submission.succeeded` | Run creation and initialization succeeded |
| `runs.submission.failed` | Run creation or initialization failed |
| `runs.validation.succeeded` | GTFS consistency check passed |
| `runs.validation.failed` | GTFS consistency check failed |
| `runs.initialization.succeeded` | Redis state written successfully |
| `runs.initialization.failed` | Redis state write failed |

Client bindings should use `runs.*` to receive all run-lifecycle events.

---

## Topology diagram

```mermaid
flowchart LR
    O[orchestrator<br/>REST API] -->|publish| E["databus.events<br/>(direct exchange)"]
    RE[realtime-engine<br/>Celery worker] -->|publish| E
    E -->|runs.submission.*| C1[Consumer A<br/>bind: runs.*]
    E -->|runs.validation.*| C1
    E -->|runs.initialization.*| C1
    E -->|runs.submission.*| C2[Consumer B<br/>bind: runs.submission.*]
```

!!! warning "Publisher stub — not yet wired"
    The diagram shows the **intended** topology. The `publish_event` function currently prints to stdout instead of publishing to the exchange. No messages flow through RabbitMQ until the stub is replaced with a real `producer.publish()` call.

---

## Intended event envelope and consumer stub

The following examples reflect the **intended** contract once the publisher is wired.

**Sample event envelope payload** (the shape `publish_event` is designed to send):

```json
{
    "name": "runs.submission.succeeded",
    "data": {
        "run_id": "550e8400-e29b-41d4-a716-446655440000",
        "run_lifecycle_state": "Initialized"
    }
}
```

**Consumer stub** — binding to `runs.*` on the `databus.events` exchange using Kombu:

```python
from kombu import Connection, Exchange, Queue

AMQP_URL = "amqp://guest:guest@localhost:5672/"
exchange = Exchange("databus.events", type="direct")

# Bind a queue to every runs.* routing key
runs_queue = Queue("my-service.runs", exchange=exchange, routing_key="runs.*")

def process_event(body, message):
    print(f"Event: {body['name']}, data: {body['data']}")
    message.ack()

with Connection(AMQP_URL) as conn:
    with conn.Consumer(runs_queue, callbacks=[process_event]):
        conn.drain_events(timeout=None)  # blocks; use in a thread or Celery task
```

!!! note
    The `runs.*` wildcard works with a **direct** exchange only if you bind to each routing key explicitly, or use a **topic** exchange instead. The current design uses `direct`; the stub above binds to a single queue but in practice you would create one binding per routing key (e.g. `runs.submission.succeeded`, `runs.validation.failed`, etc.). Check the git log for any exchange-type change before implementing.

---

## Current stub implementation

```python
# backend/messages/publisher.py

from kombu import Connection, Exchange, Producer

connection = Connection("amqp://guest:guest@localhost/")
exchange = Exchange("databus.events", type="direct")
producer = Producer(connection, exchange=exchange)


def publish_event(name: str, data: dict):
    """Publish an event to the databus.events exchange."""
    print(f"Printing event {name} with data: {data}")
```

The `connection`, `exchange`, and `producer` objects are instantiated but
`publish_event` only prints. No `producer.publish()` call exists yet.

---

## What this means for integrators

- RabbitMQ (`message-broker`) is running and healthy in both dev and prod
  compose stacks.
- The exchange `databus.events` will need to be declared and bound before any
  consumer can receive messages.
- Do not build production integrations against AMQP events until the publisher
  is wired. Check the git log or CHANGELOG for the commit that replaces the
  `print(...)` stub with a real `producer.publish(...)` call.
- The REST API (`POST /api/runs/<id>/update/`) and the run lifecycle audit log
  (`GET /api/runs/<id>/history/`) are the stable integration points today.

---

## Communication boundaries

From `ARCHITECTURE.md §7`:

- **Internal messaging** (AMQP): services within the compose network.
  Spec: AsyncAPI (domain). Currently stub.
- **External telemetry** (MQTT): vehicles and devices.
  Spec: `backend/api/realtime.yml`. See [MQTT telemetry](mqtt-telemetry.md).

External telemetry is treated as untrusted signal and must be validated before
entering the domain messaging layer.
