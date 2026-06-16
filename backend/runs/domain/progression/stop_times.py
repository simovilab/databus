"""Redis glue for the server-side stop-time-updates producer (seam / placeholder).

This module is the impure counterpart to the pure computation in
``schedule_engine/fake_stop_times.py``.  It reads from Redis, delegates to the
existing fake builder, maps the fake output to the typed contract, and writes the
projection back to Redis as a JSON string under ``run:<run_id>:stop_time_updates``.

Called by ``realtime_engine/mqtt.py`` after every successful position write so
that ``run:<run_id>:stop_time_updates`` is kept current for the GTFS-RT builder.

The Redis client mirrors the pattern used in ``producer.py``: module-level client
configured from environment variables.

Do NOT export ``produce_stop_times`` from ``runs.domain.progression.__init__``.
Import it by full module path::

    from runs.domain.progression.stop_times import produce_stop_times
"""

import logging
import os

import redis

from runs.domain.telemetry import keys, stop_time_updates

logger = logging.getLogger(__name__)

# Comfortably above the position-update interval (~1-5 s) so a stalled producer
# expires the projection instead of serving stale arrivals; run lifecycle still
# owns hard cleanup.
STOP_TIME_UPDATES_TTL_S = 60

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "state"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


def produce_stop_times(run_id: str, vehicle_id: str) -> None:  # noqa: ARG001
    """Derive and write ``run:<run_id>:stop_time_updates`` from the current run state.

    Reads the run hash and the current stop-status progression hash from Redis,
    delegates to the fake stop-time builder, maps each fake entry to the typed
    contract, and writes the JSON projection back to Redis with a staleness TTL.

    Returns immediately without writing anything if the run hash is absent (nothing
    to derive from).

    Parameters
    ----------
    run_id:
        The active run id (string, as stored in ``vehicle:<id>:current_run``).
    vehicle_id:
        The vehicle id whose position was just updated (reserved for future use).
    """
    run_hash = r.hgetall(keys.run_key(run_id))
    if not run_hash:
        return

    prev_raw = r.hgetall(keys.stop_status_key(run_id))

    from schedule_engine.fake_stop_times import build_stop_time_updates

    fake_entries = build_stop_time_updates(run=run_hash, progression=prev_raw)

    # Map fake entries {stop_sequence, stop_id, eta_posix, uncertainty}
    # → contract entries {stop_sequence, stop_id, arrival_time, departure_time, uncertainty}
    mapped = [
        {
            stop_time_updates.STOP_SEQUENCE: entry["stop_sequence"],
            stop_time_updates.STOP_ID: entry["stop_id"],
            stop_time_updates.ARRIVAL_TIME: entry["eta_posix"],
            stop_time_updates.DEPARTURE_TIME: entry["eta_posix"],
            stop_time_updates.UNCERTAINTY: entry["uncertainty"],
        }
        for entry in fake_entries
    ]

    payload = stop_time_updates.to_redis(mapped)
    r.set(keys.stop_time_updates_key(run_id), payload, ex=STOP_TIME_UPDATES_TTL_S)
