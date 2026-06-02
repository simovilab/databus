"""Ordered detector registries.

Adding a new detection is a one-line change here. Order only matters within a
single FSM (the planner fires at most one event per FSM per evaluation, taking
the first match); across FSMs detectors are independent.
"""

from runs.domain.detection.lifecycle_detectors import (
    RunTrackingStartedDetector,
    RunStartedDetector,
    RunTrackingRestoredDetector,
    RunCompletedDetector,
)
from runs.domain.detection.periodic_detectors import (
    RunTrackingLostDetector,
    RunTrackingExpiredDetector,
)

# Evaluated on every incoming telemetry message.
TELEMETRY_DETECTORS = [
    RunTrackingStartedDetector,
    RunStartedDetector,
    RunTrackingRestoredDetector,
    RunCompletedDetector,
]

# Evaluated by the periodic staleness scan.
PERIODIC_DETECTORS = [
    RunTrackingLostDetector,
    RunTrackingExpiredDetector,
]
