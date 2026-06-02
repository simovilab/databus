"""Actions for the progress FSM.

Side effects only: keep the Redis ``run_progress_state`` in sync and append an
immutable ``RunProgressEvent`` audit row. Model/Redis access is done lazily inside
the functions so the FSM definition stays import-pure for unit testing.
"""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

import redis

if TYPE_CHECKING:
    from runs.domain.progress.transitions import Transition

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


class RunProgressActions:
    @staticmethod
    def sync_progress_state(
        run: Any, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Mirror the new progress state into the ``run:{id}`` Redis hash."""
        r.hset(f"run:{run.id}", "run_progress_state", transition.to_state.value)
        return True

    @staticmethod
    def persist_progress_event(
        run: Any, transition: "Transition", payload: dict[str, Any]
    ) -> bool:
        """Append a RunProgressEvent audit record for the transition."""
        from django.utils.timezone import now

        from runs.models import RunProgressEvent

        RunProgressEvent.objects.create(
            run=run,
            event_type=transition.event.value,
            stop_id=payload.get("stop_id"),
            payload={
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "current_stop_sequence": payload.get("current_stop_sequence"),
            },
            timestamp=now(),
        )
        return True
