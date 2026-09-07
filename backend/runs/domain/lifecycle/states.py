"""Enumeration of run lifecycle states and their Django model choices."""

from enum import Enum


class RunLifecycleStates(str, Enum):
    """
    Defines the possible lifecycle states of a run.
    """

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


def choices() -> list[tuple[str, str]]:
    """Return the (value, name) choices list for the `Run.run_lifecycle_state` model field."""
    return [(status.value, status.name) for status in RunLifecycleStates]
