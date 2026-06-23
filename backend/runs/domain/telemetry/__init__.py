"""GTFS-RT entity contract package.

This package is the single shared contract that both producers (write) and
builders (read) use for the Redis entity division. Each sub-module owns one
GTFS-RT entity:

- :mod:`.keys`                — Central Redis key templates (no hardcoded strings elsewhere).
- :mod:`.position`            — ``vehicle:<id>:position`` hash (edge / MQTT).
- :mod:`.occupancy`           — ``vehicle:<id>:occupancy`` hash (edge / MQTT).
- :mod:`.vehicle_stop_status` — ``run:<id>:vehicle_stop_status`` hash (server).
- :mod:`.congestion_level`    — ``run:<id>:congestion_level`` hash (server, deferred).
- :mod:`.trip`                — ``run:<id>:trip`` hash + projection helper (server).
- :mod:`.stop_time_updates`   — ``run:<id>:stop_time_updates`` JSON string (server projection).

All modules are import-light (no Django, no Redis at module top level) so they
are safe to use in unit tests under plain pytest.

Import sub-modules directly for clarity::

    from runs.domain.telemetry import keys, position, occupancy
    from runs.domain.telemetry.occupancy import classify_status
    from runs.domain.telemetry.trip import project_from_run_hash
"""

from runs.domain.telemetry import (  # noqa: F401
    keys,
    position,
    occupancy,
    vehicle_stop_status,
    congestion_level,
    trip,
    stop_time_updates,
)
