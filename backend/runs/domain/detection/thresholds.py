"""Single source of truth for telemetry-staleness thresholds.

Previously these lived in two places that disagreed: ``realtime_engine/tasks.py``
used a 300 s expiry while ``runs/domain/lifecycle/guards.py`` used 600 s, so the
periodic scan could fire ``run_tracking_expired`` in a window where the guard then
rejected it. Both now import from here.

This module imports nothing so it is safe to import from any layer (detectors,
guards, tasks) without pulling in Django or Redis.
"""

# Telemetry older than this (seconds) is "stale": an IN_PROGRESS run drops to
# NO_SIGNAL.
TELEMETRY_GRACE_S = 60

# Telemetry older than this (seconds) is "expired": a NO_SIGNAL run is cancelled.
TELEMETRY_EXPIRY_S = 600
