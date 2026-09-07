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

The publisher module `backend/messages/publisher.py` is fully implemented — not a stub. It is called from a single seam, `RunLifecycleService._publish_run_lifecycle_transition` (`backend/runs/services/lifecycle.py`), immediately after every successful FSM transition except `run_requested` (that event enters `Requested` at record creation, outside `process_event`).

- **Exchange:** `databus.events` — a durable **topic** exchange (not `direct`).
- **Routing key:** `runs.lifecycle.<event>`, where `<event>` is the lowercased `.value` of the `RunLifecycleEvents` member for the transition that just completed (`routing_key_for`, `publisher.py`) — e.g. `runs.lifecycle.run_confirmed_by_operator`.
- **Binding:** subscribers interested in every run lifecycle event bind `runs.lifecycle.#`.
- **Envelope:** a versioned JSON body — `event`, `version`, `occurred_at`, `producer`, `run_id`, `from_state`, `to_state`, `data` (`build_envelope`, `publisher.py`). `from_state`/`to_state` carry the FSM's display-style values (e.g. `"Initialized"`, `"Confirmed"`), not upper-snake enum member names.
- **Delivery:** fire-and-forget. Publishing goes through kombu's connection pool with a small bounded retry (`max_retries=2`), but there are no publisher confirms — any broker/connection error is caught, logged, and dropped. This is deliberate: telemetry and lifecycle processing must never block or fail because RabbitMQ is unavailable. The durable audit trail is `GET /api/runs/<id>/history/`, not the AMQP stream.

Full contract details (the complete routing-key table, envelope field reference, sequence diagram, and integration guidance for consumers) live on [Interfaces › AMQP event semantics](../interfaces/amqp-events.md). This page stays at the architectural level; that page is the authoritative reference.

## Current inter-service communication

In the current implementation, inter-service coordination happens via:

1. **Celery tasks over RabbitMQ** — `scheduler` fires beat tasks; `realtime-engine` and `schedule-engine` consume them. This is the primary coordination mechanism and is fully operational.
2. **Redis** — `realtime-engine` writes state; `schedule-engine` reads snapshots. No pub/sub; pure key-value reads.
3. **Django ORM (PostgreSQL)** — `orchestrator` persists domain records; `realtime-engine` reads run metadata during lifecycle service calls.
4. **AMQP domain events** (`databus.events` topic exchange) — live, not designed-but-pending. Every run lifecycle transition is broadcast fire-and-forget for external subscribers, alongside (not instead of) the three mechanisms above.

## Message envelope

Two distinct "envelope" concepts exist in the system — don't conflate them:

- **AMQP domain-event envelope** — the JSON body described under [AMQP layout](#amqp-layout) above, built by `build_envelope` in `backend/messages/publisher.py`. See [Interfaces › AMQP event semantics](../interfaces/amqp-events.md) for the full field reference.
- **Celery task payload** — the internal dict passed between the detection layer and `run_lifecycle_event`, carrying correlation metadata (`run_id`, `vehicle_id`, `actor_role`, `last_seen_at`). This is not published anywhere external; it only exists for the duration of one Celery task dispatch. See `backend/runs/domain/detection/dispatch.py` for how the dispatcher assembles it.

## External telemetry

MQTT telemetry from vehicles is **not** treated as domain messaging. It is an untrusted edge signal that the `realtime-engine` validates and interprets before it enters the domain layer. See [../data-flow/telemetry-ingestion.md](../data-flow/telemetry-ingestion.md) and [../interfaces/mqtt-telemetry.md](../interfaces/mqtt-telemetry.md).
