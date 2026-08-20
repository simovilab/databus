# Messages · AMQP domain-event publisher

- **Purpose**: fire-and-forget publisher for run lifecycle domain events, used by
  `runs.services.lifecycle.RunLifecycleService` so every completed FSM transition is broadcast to
  other services over RabbitMQ. Publishing failures are logged and swallowed — they never affect
  the caller's lifecycle path (`messages/publisher.py:1-9`).
- **Key modules**: `publisher.py` — the entire app (no models, no views, no URLs).

## Transport

- Broker: kombu over the same RabbitMQ instance Celery uses as its broker
  (`Connection(settings.CELERY_BROKER_URL)`, built lazily on first publish —
  `messages/publisher.py:66-73` — never at import time, so importing the module never opens a
  socket).
- Exchange: `databus.events`, a **durable topic exchange** (`messages/publisher.py:21,27`).
- Routing key: `runs.lifecycle.<event>`, lowercased (`routing_key_for`, `publisher.py:41-43`) —
  e.g. `runs.lifecycle.run_confirmed_by_operator`.
- Publishing goes through kombu's `producers` connection pool (`kombu.pools.producers`), with a
  bounded retry policy (`max_retries=2`, `interval_start=0`, `interval_step=0.2`,
  `interval_max=0.5`) passed to `Producer.publish(retry=True, ...)` (`publisher.py:29-35, 86-97`).

## Envelope

`build_envelope` (`publisher.py:46-63`) produces:

```json
{
  "event": "run_confirmed_by_operator",
  "version": 1,
  "occurred_at": "2026-08-19T00:00:00+00:00",
  "producer": "databus",
  "run_id": "<run uuid, stringified>",
  "from_state": "Initialized",
  "to_state": "Confirmed",
  "data": { "vehicle_id": "...", "trip_id": "...", "route_id": "..." }
}
```

`event`/`from_state`/`to_state` are the enum `.value`s from `RunLifecycleEvents` /
`RunLifecycleStates`. `data` is populated by the caller — for the lifecycle service it includes
whatever of `vehicle_id`, `trip_id`, `route_id` are available on the `Run`
(`runs/services/lifecycle.py:112-132`).

## Consumer contract

An external consumer should:
1. Declare (or rely on this publisher declaring) the `databus.events` topic exchange, durable.
2. Bind its own durable queue to that exchange with a topic pattern under `runs.lifecycle.*`
   (e.g. `runs.lifecycle.run_completed` for one event, `runs.lifecycle.#` for all run lifecycle
   events).
3. Deserialize the body as JSON and expect the envelope shape above — `version` is included so
   consumers can branch on schema changes.
4. Not expect delivery guarantees beyond the small retry policy above: this publisher is
   fire-and-forget and does not use publisher confirms, so a consumer that needs strict
   at-least-once semantics should treat `messages` as best-effort and reconcile via
   `GET /api/runs/<id>/history/` (the authoritative audit log) rather than relying on AMQP alone.

## Configuration

- `CELERY_BROKER_URL` — read indirectly via `settings.CELERY_BROKER_URL`, itself built from
  `RABBITMQ_HOST`/`RABBITMQ_PORT`/`RABBITMQ_USER`/`RABBITMQ_PASS` (see `backend/databus/README.md`).

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest messages/ -q
```
`messages/tests/test_publisher.py` covers routing-key derivation, envelope shape, the
publish-with-mocked-pool happy path, error-swallowing on connection/publish failures, and lazy
connection caching. `make test` runs the full suite.

## Note on docs drift

`docs/content/interfaces/amqp-events.md` currently describes this publisher as an unwired stub
(direct exchange, `print()` instead of `producer.publish()`, different routing-key namespace). That
page is stale — the code in this app is fully implemented as described above (topic exchange,
`runs.lifecycle.*` routing keys, real `producer.publish()` via kombu's pool). Worth a doc refresh,
out of scope for this README.
