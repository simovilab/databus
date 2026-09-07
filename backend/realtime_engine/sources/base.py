"""Pluggable telemetry source adapter contract + registry.

A ``SourceAdapter`` fetches raw vehicle telemetry from wherever a Sensor is
configured to read from (HTTP endpoint today; MQTT bridge, file, etc. could
follow) and normalizes it into ``(vehicle_id, position_payload)`` tuples
ready to be published on the MQTT topic ``transit/vehicle/<id>/position``
(see ``publisher.py``).

Kept tiny and dependency-free — no Django, no requests, no paho — so
importing this module never has side effects and adapters can be unit
tested without any I/O.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    # Type-checking only: the runtime import graph stays Django-free (see
    # module docstring), but the real model gives accurate hover/mypy types.
    from operations.models import Sensor


class SourceAdapter(Protocol):
    """Structural contract for a telemetry source adapter."""

    def fetch(self, sensor: "Sensor") -> list[tuple[str, dict]]:
        """Fetch and normalize telemetry for a sensor.

        Returns a list of ``(vehicle_id, position_payload)`` tuples. Each
        payload is a dict shaped for
        ``runs.domain.telemetry.position.validate_for_write`` (i.e. at
        least ``latitude``/``longitude``, with any of ``bearing``,
        ``speed``, ``odometer``, ``timestamp`` included only when known).
        """
        ...


_REGISTRY: dict[str, SourceAdapter] = {}


def register(kind: str) -> Callable[[Any], Any]:
    """Class/function decorator registering an adapter under ``kind``.

    Usable on a class (instantiated once at registration time) or on an
    already-constructed adapter instance/function.
    """

    def _decorator(adapter: Any) -> Any:
        """Register `adapter` (instantiating it first if it's a class) under `kind`."""
        _REGISTRY[kind] = adapter() if isinstance(adapter, type) else adapter
        return adapter

    return _decorator


def get_adapter(kind: str) -> SourceAdapter:
    """Look up a registered adapter by kind. Raises ``KeyError`` if unknown."""
    try:
        return _REGISTRY[kind]
    except KeyError as exc:
        raise KeyError(f"No source adapter registered for kind={kind!r}") from exc
