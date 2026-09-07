"""Fire-and-forget AMQP publisher for run lifecycle domain events.

Publishes to the durable ``databus.events`` topic exchange, keyed by
``runs.lifecycle.<event>``. The broker connection is built lazily on first
use (never at import time) so importing this module never opens a socket,
and it is safe to import from both the Daphne/ASGI process and Celery
workers. Publishing is best-effort: any broker/connection error is caught,
logged, and dropped -- it must never propagate into the caller's lifecycle
path.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from kombu import Connection, Exchange
from kombu.pools import producers

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "databus.events"
ROUTING_KEY_PREFIX = "runs.lifecycle"
PRODUCER_NAME = "databus"
ENVELOPE_VERSION = 1

#: Durable topic exchange all domain events are published to.
events_exchange = Exchange(EXCHANGE_NAME, type="topic", durable=True)

#: Small bounded retry policy handed to kombu's ``ensure()`` via ``Producer.publish(retry=True, ...)``.
_RETRY_POLICY: dict[str, float] = {
    "max_retries": 2,
    "interval_start": 0,
    "interval_step": 0.2,
    "interval_max": 0.5,
}

# Process-wide broker connection, built lazily by `_get_connection`.
_connection: Connection | None = None


def routing_key_for(event: str) -> str:
    """Derive the topic routing key `runs.lifecycle.<event>` for a lowercase lifecycle event name."""
    return f"{ROUTING_KEY_PREFIX}.{event.lower()}"


def build_envelope(
    event: str,
    run_id: Any,
    from_state: str,
    to_state: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the JSON-serializable envelope for a run lifecycle domain event."""
    return {
        "event": event,
        "version": ENVELOPE_VERSION,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": PRODUCER_NAME,
        "run_id": str(run_id),
        "from_state": from_state,
        "to_state": to_state,
        "data": data or {},
    }


def _get_connection() -> Connection:
    """Return the lazily-initialized, process-wide broker connection built from Django settings."""
    global _connection
    if _connection is None:
        from django.conf import settings

        _connection = Connection(settings.CELERY_BROKER_URL)
    return _connection


def publish_event(
    event: str,
    run_id: Any,
    from_state: str,
    to_state: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish a run lifecycle domain event; broker errors are logged and swallowed, never raised."""
    envelope = build_envelope(event, run_id, from_state, to_state, data)
    routing_key = routing_key_for(event)
    try:
        connection = _get_connection()
        with producers[connection].acquire(block=True) as producer:
            producer.publish(
                envelope,
                exchange=events_exchange,
                routing_key=routing_key,
                declare=[events_exchange],
                serializer="json",
                retry=True,
                retry_policy=_RETRY_POLICY,
            )
    except Exception:
        logger.warning(
            "Failed to publish run lifecycle event %r for run %s (routing_key=%s)",
            event,
            run_id,
            routing_key,
            exc_info=True,
        )
