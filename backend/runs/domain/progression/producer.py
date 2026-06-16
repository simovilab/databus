"""Redis glue for the server-side stop-status producer.

This module is the impure counterpart to the pure :mod:`.compute` module.
It reads from Redis, delegates computation (real GPS→polyline map-matching,
with a defensive ``IN_TRANSIT_TO`` carry-forward fallback in :mod:`.compute`),
validates the result, and writes back to Redis.

Called by ``realtime_engine/mqtt.py`` after every successful position write
so that ``run:<run_id>:vehicle_stop_status`` is kept current.

The Redis client mirrors the pattern used in other producer modules in this
package: module-level client configured from environment variables.
"""

import logging
import os

import redis

from runs.domain.telemetry import keys, position, vehicle_stop_status
from runs.domain.progression.compute import compute_stop_status

logger = logging.getLogger(__name__)

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


def produce_stop_status(run_id: str, vehicle_id: str) -> dict | None:
    """Derive and write ``run:<run_id>:vehicle_stop_status`` from the latest position.

    Reads the current position, run hash, and previous stop status from Redis,
    delegates to :func:`.compute_stop_status`, validates the result, and writes
    it back to ``run:<run_id>:vehicle_stop_status``.

    Returns immediately without writing anything if no position data is
    available for the vehicle (nothing to derive from).

    Parameters
    ----------
    run_id:
        The active run id (string, as stored in ``vehicle:<id>:current_run``).
    vehicle_id:
        The vehicle id whose position was just updated.

    Returns
    -------
    dict | None
        The computed vehicle_stop_status contract dict (contains at minimum
        ``current_status`` and optionally ``stop_id`` / ``current_stop_sequence``)
        when position data is available, or ``None`` when there is no position
        data to derive from.
    """
    pos_raw = r.hgetall(keys.position_key(vehicle_id))
    if not pos_raw:
        # No position data yet — nothing to derive stop status from.
        return None

    position_hash = position.from_redis(pos_raw)

    run_hash = r.hgetall(keys.run_key(run_id))

    prev_raw = r.hgetall(keys.stop_status_key(run_id))
    prev_state = vehicle_stop_status.from_redis(prev_raw) if prev_raw else None

    computed = compute_stop_status(run_hash, position_hash, prev_state=prev_state)

    mapping = vehicle_stop_status.validate_for_write(computed)
    r.hset(keys.stop_status_key(run_id), mapping=mapping)

    return computed
