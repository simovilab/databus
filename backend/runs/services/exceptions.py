"""Domain exception raised when a run lifecycle guard or action rejects a transition."""

from typing import Any


class RunLifecycleError(Exception):
    """Raised when a guard rejects a transition or an action fails, carrying field-level error detail."""

    def __init__(self, errors: dict[str, Any]) -> None:
        """Store the field-level error detail dict for the caller (e.g. DRF serialization)."""
        self.errors = errors
