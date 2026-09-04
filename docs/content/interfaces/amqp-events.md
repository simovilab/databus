---
icon: lucide/git-branch
---

# AMQP Event Semantics

Databús uses RabbitMQ as its internal async message backbone for run lifecycle
domain events. Every completed run lifecycle FSM transition is published as a
fire-and-forget message on a durable topic exchange, so other services can
react to run state changes without polling the REST API.

The publisher (`backend/messages/publisher.py`) is fully implemented — it is
not a stub. It is called from a single seam in the run lifecycle service and
never blocks or fails the caller's request path.

---

## Exchange

| Attribute | Value |
| --- | --- |
| Name | `databus.events` |
| Type | `topic` |
| Durable | Yes |
| Protocol | AMQP 0-9-1 via Kombu |
| Broker | RabbitMQ (`message-broker` service), same connection Celery uses as its broker |
| Connection | `Connection(settings.CELERY_BROKER_URL)`, built lazily on first publish — importing the module never opens a socket |

Source: `backend/messages/publisher.py`.

---

## Routing keys — `runs.lifecycle.*` namespace

Every publish is keyed `runs.lifecycle.<event>`, where `<event>` is the
lowercased `.value` of the `RunLifecycleEvents` enum member for the transition
that just completed (`routing_key_for`, `backend/messages/publisher.py`).

| Event (`RunLifecycleEvents`) | Routing key |
| --- | --- |
| `run_requested` | *(not published — set at record creation, not via `process_event`)* |
| `validate_run` | `runs.lifecycle.validate_run` |
| `initialize_run` | `runs.lifecycle.initialize_run` |
| `run_rejected` | `runs.lifecycle.run_rejected` |
| `run_confirmed_by_operator` | `runs.lifecycle.run_confirmed_by_operator` |
| `cancel_run` | `runs.lifecycle.cancel_run` |
| `run_tracking_started` | `runs.lifecycle.run_tracking_started` |
| `run_started` | `runs.lifecycle.run_started` |
| `run_tracking_lost` | `runs.lifecycle.run_tracking_lost` |
| `run_interrupted` | `runs.lifecycle.run_interrupted` |
| `run_short_turned` | `runs.lifecycle.run_short_turned` |
| `run_completed` | `runs.lifecycle.run_completed` |
| `run_tracking_restored` | `runs.lifecycle.run_tracking_restored` |
| `run_tracking_expired` | `runs.lifecycle.run_tracking_expired` |

Every event in `RunLifecycleEvents` that has at least one entry in the FSM
transition table (`backend/runs/domain/lifecycle/transitions.py`) publishes a
message the moment its transition succeeds. Consumers should bind:

- `runs.lifecycle.#` — all run lifecycle events, or
- `runs.lifecycle.run_completed` (etc.) — a single event, or
- `runs.#` — everything under the `runs` namespace (forward-compatible with
  any future non-lifecycle `runs.*` routing keys).

Source: `backend/runs/domain/lifecycle/transitions.py`, `backend/messages/publisher.py`.

---

## Message envelope

`build_envelope` (`backend/messages/publisher.py`) produces this JSON body:

```json
{
    "event": "run_confirmed_by_operator",
    "version": 1,
    "occurred_at": "2026-08-19T00:00:00+00:00",
    "producer": "databus",
    "run_id": "0b2b6b2e-...-uuid",
    "from_state": "Initialized",
    "to_state": "Confirmed",
    "data": {
        "vehicle_id": "...",
        "trip_id": "...",
        "route_id": "..."
    }
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `event` | string | `RunLifecycleEvents.<member>.value` — lowercase snake_case |
| `version` | int | Envelope schema version, currently `1`. Consumers should branch on this if the shape ever changes |
| `occurred_at` | string | ISO-8601 UTC timestamp, generated at publish time (`datetime.now(UTC)`) |
| `producer` | string | Always `"databus"` |
| `run_id` | string | The run's UUID, stringified |
| `from_state` | string | `RunLifecycleStates.<member>.value` (e.g. `"Initialized"`) — the state the run transitioned *from* |
| `to_state` | string | `RunLifecycleStates.<member>.value` (e.g. `"Confirmed"`) — the state the run transitioned *to* |
| `data` | object | Best-effort extras. The lifecycle service populates whichever of `vehicle_id`, `trip_id`, `route_id` are available on the `Run` at publish time; any missing field is simply omitted, never sent as `null` |

Note `from_state`/`to_state` carry the FSM's display-style state values
(`"Initialized"`, `"Confirmed"`, `"In Progress"`, …) as defined in
`RunLifecycleStates`, not the upper-snake enum member names.

Source: `backend/messages/publisher.py`, `backend/runs/services/lifecycle.py`.

---

## Where events are emitted from

Every event is published from a single seam:
`RunLifecycleService._publish_run_lifecycle_transition` in
`backend/runs/services/lifecycle.py`, called by `_apply_transition`
immediately after the transition's actions run and the new
`run_lifecycle_state` is persisted to Postgres — but the publish itself is a
fire-and-forget side effect that does not block the request/task path.

```mermaid
sequenceDiagram
    participant Caller as REST view / Celery task
    participant Service as RunLifecycleService
    participant DB as PostgreSQL (Run)
    participant Publisher as messages.publisher
    participant RMQ as RabbitMQ (databus.events)

    Caller->>Service: process_event(event, payload)
    Service->>Service: check guards, run actions
    Service->>DB: run.run_lifecycle_state = to_state; run.save()
    Service->>Publisher: publish_event(event, run_id, from_state, to_state, data)
    Publisher-->>RMQ: producer.publish(envelope, routing_key="runs.lifecycle.<event>")
    Note over Publisher,RMQ: On any broker error: logged and dropped.<br/>Never raised back to Service or Caller.
    Service-->>Caller: (to_state, guards, actions)
```

This means every REST-triggered transition (`POST /api/runs/<id>/update/`,
`POST /api/create-run/`) and every telemetry-triggered transition (fired from
`realtime_engine.tasks.run_lifecycle_event`, driven by the detection layer)
produces the same event shape on the same exchange — there is no separate
"internal" vs "external" event path.

---

## Error policy: fire-and-forget, log-and-drop

Publishing a domain event is a deliberate best-effort side effect, not a
guaranteed delivery:

- `publish_event` wraps the entire publish in a `try`/`except Exception`. Any
  connection error, channel error, or broker rejection is caught, logged with
  `logger.warning(..., exc_info=True)`, and **swallowed** — it never
  propagates back into the FSM transition path.
- A small bounded retry is attempted first (`max_retries=2`,
  `interval_start=0`, `interval_step=0.2`, `interval_max=0.5`, passed to
  kombu's `Producer.publish(retry=True, retry_policy=...)`), but there are no
  publisher confirms and no outbox/at-least-once guarantee beyond that.
- This is intentional: **telemetry and lifecycle processing must never block
  or fail because RabbitMQ is unavailable.** A run's FSM transition, its
  Postgres persistence, and its audit-log entry (`RunLifecycleTransition`, via
  `GET /api/runs/<id>/history/`) all complete regardless of whether the AMQP
  publish succeeds.
- Consequence for integrators: a consumer that needs strict at-least-once
  semantics should treat these AMQP messages as a best-effort notification
  stream and reconcile against `GET /api/runs/<id>/history/` — the
  authoritative, durable audit log — rather than relying on AMQP delivery
  alone.

Source: `backend/messages/publisher.py`, `backend/messages/README.md`.

---

## Which transitions produce events

Any transition executed through `RunLifecycleService.process_event` that
passes its guards publishes an event — this covers essentially the whole FSM:
registration (`validate_run`, `initialize_run`), rejection/cancellation
(`run_rejected`, `cancel_run`), operator confirmation
(`run_confirmed_by_operator`), tracking and progress
(`run_tracking_started`, `run_started`), deviations
(`run_tracking_lost`, `run_interrupted`, `run_short_turned`), completion
(`run_completed`), and recovery/expiry (`run_tracking_restored`,
`run_tracking_expired`). The one exception is `run_requested`: a run enters
`Requested` state at record creation (`Run.objects.create(...)` in
`CreateRunViewSet`), not through `process_event`, so no lifecycle event is
published for it.

See the full transition table in
`backend/runs/domain/lifecycle/transitions.py` and the REST-facing surface in
[REST API › Run lifecycle endpoints](rest-api.md#run-lifecycle-endpoints).

---

## Integration guidance

- RabbitMQ (`message-broker`) is running and healthy in both dev and prod
  compose stacks.
- The publisher declares the `databus.events` exchange on every publish
  (`declare=[events_exchange]`), so a consumer does not strictly need to
  declare it first — but should still declare it (idempotent) plus its own
  durable queue, to avoid depending on publish timing.
- Bind your queue with `runs.lifecycle.#` (all run lifecycle events) or a
  narrower pattern for the specific events you care about.
- Deserialize the body as JSON and branch on `version` for forward
  compatibility.
- Treat delivery as best-effort (see error policy above); use
  `GET /api/runs/<id>/history/` to reconcile or backfill missed events.

---

## Communication boundaries

- **Internal messaging** (AMQP): services within the compose network,
  currently limited to run lifecycle domain events described on this page.
- **External telemetry** (MQTT): vehicles and devices.
  Spec: `backend/api/realtime.yml`. See [MQTT telemetry](mqtt-telemetry.md).

External telemetry is treated as untrusted signal and must be validated
before entering the domain messaging layer (see
[MQTT telemetry › Untrusted edge signal stance](mqtt-telemetry.md#untrusted-edge-signal-stance)).
