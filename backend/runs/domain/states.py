from enum import Enum


class RunStatus(str, Enum):
    REQUESTED = "Requested"
    VALIDATED = "Validated"
    INITIALIZED = "Initialized"
    CONFIRMED = "Confirmed"
    TRACKING = "Tracking"
    CANCELLED = "Cancelled"
    IN_PROGRESS = "In Progress"
    NO_SIGNAL = "No Signal"
    COMPLETED = "Completed"
    INTERRUPTED = "Interrupted"
    SHORT_TURNED = "Short Turned"


def choices():
    return [(status.value, status.name) for status in RunStatus]
