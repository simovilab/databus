"""The value a detector returns when it recognises an event."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DetectionResult:
    """A detected state-machine event, ready to be routed to an FSM service.

    Attributes:
        fsm: Routing key for the target state machine (``"lifecycle"`` or
            ``"progress"``). The dispatcher uses this to pick the service/task.
        event: The event to fire — a ``RunLifecycleEvents`` member. As a
            ``str`` enum it compares equal to its value, so downstream string
            consumers (Celery payloads, seed-event checks) keep working.
        extra_payload: Fields the detector adds on top of the base payload
            (e.g. ``{"stop_id": ...}`` for completion). Merged by the dispatcher.
    """

    fsm: str
    event: str
    extra_payload: dict[str, Any] = field(default_factory=dict)
