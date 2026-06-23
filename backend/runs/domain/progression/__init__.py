"""Server-side stop-status progression package (seam / placeholder implementation).

Provides a stable contract for deriving ``run:<run_id>:vehicle_stop_status``
from the vehicle's latest GPS position and run assignment.

Public API
----------
- :func:`.compute_stop_status` — pure function, no I/O (import-light).
- :func:`.produce_stop_status` — impure Redis glue; reads, computes, writes.

The real map-matching algorithm (GPS → polyline projection → stop radius rules)
is deferred to a future port.  See :mod:`.compute` for the TODO note and
the stable function signature that the port will swap.
"""

from runs.domain.progression.compute import compute_stop_status  # noqa: F401
from runs.domain.progression.producer import produce_stop_status  # noqa: F401
