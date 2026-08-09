"""Input validation helpers for gtfs_eta."""
from typing import Any


def require_keys(d: dict, keys: list[str], context: str = "") -> None:
    """Raise ValueError if any key is missing from d."""
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"Missing required keys {missing} in {context or 'input'}")


def require_positive(value: Any, name: str) -> None:
    """Raise ValueError if value is not a positive number."""
    if value is None or float(value) <= 0:
        raise ValueError(f"{name} must be a positive number, got {value!r}")
