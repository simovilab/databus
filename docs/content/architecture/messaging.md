---
icon: lucide/send
---

# Messaging model

Databús defines three distinct message types that flow between services. The distinction is semantic, not just technical — it determines who may send a message and what obligations the receiver has.

## The three message kinds

| Kind | Producer | Meaning | Examples |
|---|---|---|---|
| **Command** | `orchestrator` | An intentional, authorized request to change state | `VALIDATE_RUN`, `CANCEL_RUN`, `RUN_CONFIRMED_BY_OPERATOR` |
| **Observation** | `realtime-engine` | A derived fact detected from telemetry | `run_tracking_started`, `run_started`, `run_completed`, `run_tracking_lost` |
| **Assertion** | `schedule-engine` (publisher role) | A claim about published output | "GTFS-RT feed rebuilt at time T" |

Commands originate from human actors (dispatcher, operator) or from system automation acting on their behalf. Observations are the outputs of the detection layer — they are facts inferred from the real world, never manufactured. Assertions are accountability signals from the projection layer.

See [../runs/commands-vs-detections.md](../runs/commands-vs-detections.md) for a detailed treatment of the commands-vs-observations distinction in the run lifecycle.

## AMQP layout

The designed exchange topology is:

- **Exchange:** `databus.events` (type: `direct`)
- **Routing key namespace:** `runs.*`

Routing keys sketched in `backend/messages/publisher.py`:

```
runs.submission.requested
runs.submission.succeeded
runs.submission.failed
runs.validation.succeeded
runs.validation.failed
runs.initialization.succeeded
runs.initialization.failed
```

Subscribers interested in all run events bind with `runs.*`.

## Implementation status

!!! warning "AMQP publisher is a stub"
    The publisher module at `backend/messages/publisher.py` is **not yet wired**. The `publish_event` function currently only prints to stdout:

    ```python
    def publish_event(name: str, data: dict):
        """Publish an event to the databus.events exchange."""
        print(f"Printing event {name} with data: {data}")
    ```

    The `Connection`, `Exchange`, and `Producer` objects are instantiated at module import but `publish_event` does not use them. Domain event emission via AMQP is designed and the routing-key namespace is settled, but the actual publish call and delivery guarantees are not yet implemented.

    Celery task routing (the RabbitMQ backbone that drives `realtime-engine` and `schedule-engine`) is fully operational and unaffected by this stub. The stub only concerns application-level domain events that other systems might subscribe to.

## Current inter-service communication

In the current implementation, inter-service coordination happens via:

1. **Celery tasks over RabbitMQ** — `scheduler` fires beat tasks; `realtime-engine` and `schedule-engine` consume them. This is the primary coordination mechanism and is fully operational.
2. **Redis** — `realtime-engine` writes state; `schedule-engine` reads snapshots. No pub/sub; pure key-value reads.
3. **Django ORM (PostgreSQL)** — `orchestrator` persists domain records; `realtime-engine` reads run metadata during lifecycle service calls.

The AMQP domain event layer (`databus.events` exchange) sits alongside this and will emit structured domain events for external subscribers once the stub is replaced.

## Message envelope

All internal messages share a common envelope that includes correlation metadata (run_id, vehicle_id, actor_role, last_seen_at). The Celery payload dict is the current concrete form of this envelope — see `backend/runs/domain/detection/dispatch.py` for how the dispatcher assembles it.

## External telemetry

MQTT telemetry from vehicles is **not** treated as domain messaging. It is an untrusted edge signal that the `realtime-engine` validates and interprets before it enters the domain layer. See [../data-flow/telemetry-ingestion.md](../data-flow/telemetry-ingestion.md) and [../interfaces/mqtt-telemetry.md](../interfaces/mqtt-telemetry.md).
