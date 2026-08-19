"""Unit tests for messages.publisher.

No real broker: `kombu.pools.producers` is monkeypatched with an in-memory
fake pool so `publish_event` never touches the network, and `_get_connection`
is monkeypatched directly where the test only cares about the publish call
(avoiding a dependency on real RabbitMQ settings). Errors raised anywhere in
the publish path must be swallowed -- publishing must never propagate into
the caller.
"""

import logging

import pytest

from messages import publisher


# ---------------------------------------------------------------------------
# routing_key_for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event,expected",
    [
        ("run_confirmed_by_operator", "runs.lifecycle.run_confirmed_by_operator"),
        ("run_completed", "runs.lifecycle.run_completed"),
        ("RUN_STARTED", "runs.lifecycle.run_started"),
    ],
)
def test_routing_key_for(event, expected):
    assert publisher.routing_key_for(event) == expected


# ---------------------------------------------------------------------------
# build_envelope
# ---------------------------------------------------------------------------


def test_build_envelope_has_expected_shape():
    envelope = publisher.build_envelope(
        event="run_completed",
        run_id="run-1",
        from_state="IN_PROGRESS",
        to_state="COMPLETED",
        data={"trip_id": "T1"},
    )

    assert envelope["event"] == "run_completed"
    assert envelope["version"] == 1
    assert envelope["producer"] == "databus"
    assert envelope["run_id"] == "run-1"
    assert envelope["from_state"] == "IN_PROGRESS"
    assert envelope["to_state"] == "COMPLETED"
    assert envelope["data"] == {"trip_id": "T1"}
    # occurred_at must be a parseable ISO-8601 UTC timestamp.
    from datetime import datetime

    parsed = datetime.fromisoformat(envelope["occurred_at"])
    assert parsed.utcoffset() is not None


def test_build_envelope_defaults_data_to_empty_dict():
    envelope = publisher.build_envelope(
        event="run_started", run_id="run-2", from_state="TRACKING", to_state="IN_PROGRESS"
    )
    assert envelope["data"] == {}


def test_build_envelope_stringifies_run_id():
    envelope = publisher.build_envelope(
        event="run_started", run_id=12345, from_state="A", to_state="B"
    )
    assert envelope["run_id"] == "12345"


# ---------------------------------------------------------------------------
# publish_event -- happy path
# ---------------------------------------------------------------------------


class _FakeAcquireCtx:
    """Context manager standing in for kombu's ProducerPool.acquire() result."""

    def __init__(self, producer):
        self._producer = producer

    def __enter__(self):
        return self._producer

    def __exit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, producer):
        self._producer = producer

    def acquire(self, block=True):
        return _FakeAcquireCtx(self._producer)


class _FakeProducers:
    """Stand-in for kombu.pools.producers: a dict keyed by connection."""

    def __init__(self, producer):
        self._producer = producer

    def __getitem__(self, connection):
        return _FakePool(self._producer)


def test_publish_event_uses_correct_exchange_routing_key_and_body(monkeypatch):
    from unittest.mock import MagicMock

    fake_producer = MagicMock()
    monkeypatch.setattr(publisher, "producers", _FakeProducers(fake_producer))
    monkeypatch.setattr(publisher, "_get_connection", lambda: object())

    publisher.publish_event(
        event="run_confirmed_by_operator",
        run_id="run-42",
        from_state="INITIALIZED",
        to_state="CONFIRMED",
        data={"vehicle_id": "veh-1"},
    )

    fake_producer.publish.assert_called_once()
    _, kwargs = fake_producer.publish.call_args
    body = fake_producer.publish.call_args.args[0]

    assert body["event"] == "run_confirmed_by_operator"
    assert body["run_id"] == "run-42"
    assert body["from_state"] == "INITIALIZED"
    assert body["to_state"] == "CONFIRMED"
    assert body["data"] == {"vehicle_id": "veh-1"}
    assert kwargs["exchange"] is publisher.events_exchange
    assert kwargs["routing_key"] == "runs.lifecycle.run_confirmed_by_operator"
    assert kwargs["serializer"] == "json"
    assert kwargs["retry"] is True


def test_publish_event_declares_the_exchange(monkeypatch):
    from unittest.mock import MagicMock

    fake_producer = MagicMock()
    monkeypatch.setattr(publisher, "producers", _FakeProducers(fake_producer))
    monkeypatch.setattr(publisher, "_get_connection", lambda: object())

    publisher.publish_event(
        event="run_completed", run_id="run-1", from_state="IN_PROGRESS", to_state="COMPLETED"
    )

    _, kwargs = fake_producer.publish.call_args
    assert kwargs["declare"] == [publisher.events_exchange]


# ---------------------------------------------------------------------------
# publish_event -- errors are swallowed, never propagated
# ---------------------------------------------------------------------------


def test_publish_event_swallows_connection_errors(monkeypatch, caplog):
    def _boom():
        raise ConnectionRefusedError("broker unreachable")

    monkeypatch.setattr(publisher, "_get_connection", _boom)

    with caplog.at_level(logging.WARNING):
        # Must not raise.
        publisher.publish_event(
            event="run_completed", run_id="run-1", from_state="IN_PROGRESS", to_state="COMPLETED"
        )

    assert any("Failed to publish run lifecycle event" in msg for msg in caplog.messages)


def test_publish_event_swallows_producer_publish_errors(monkeypatch, caplog):
    from unittest.mock import MagicMock

    fake_producer = MagicMock()
    fake_producer.publish.side_effect = RuntimeError("channel closed")
    monkeypatch.setattr(publisher, "producers", _FakeProducers(fake_producer))
    monkeypatch.setattr(publisher, "_get_connection", lambda: object())

    with caplog.at_level(logging.WARNING):
        # Must not raise.
        publisher.publish_event(
            event="run_completed", run_id="run-1", from_state="IN_PROGRESS", to_state="COMPLETED"
        )

    assert any("Failed to publish run lifecycle event" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# _get_connection -- lazy, cached, built from Django settings
# ---------------------------------------------------------------------------


def test_get_connection_is_lazily_cached(monkeypatch, settings):
    monkeypatch.setattr(publisher, "_connection", None)
    settings.CELERY_BROKER_URL = "amqp://guest:guest@message-broker:5672//"

    first = publisher._get_connection()
    second = publisher._get_connection()

    assert first is second
    assert first.as_uri().startswith("amqp://")

    # Cleanup so other tests build a fresh connection from their own settings.
    monkeypatch.setattr(publisher, "_connection", None)
