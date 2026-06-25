"""
Runtime configuration for gtfs_eta.

The registry dir is NOT derived from __file__ — it comes solely from the
MODEL_REGISTRY_DIR environment variable (or the registry's own discovery
logic).  This module only exposes the defaults that are safe to use at
import time without side effects.
"""

# Default timezone and region for Costa Rica operations
DEFAULT_TIMEZONE: str = "America/Costa_Rica"
DEFAULT_REGION: str = "CR"

# Weather defaults (used when no live weather feed is available)
DEFAULT_TEMPERATURE_C: float = 25.0
DEFAULT_PRECIPITATION_MM: float = 0.0
DEFAULT_WIND_SPEED_KMH: float | None = None


def get_config() -> dict:
    """Return the active configuration as a plain dict."""
    return {
        "default_timezone": DEFAULT_TIMEZONE,
        "default_region": DEFAULT_REGION,
        "default_temperature_c": DEFAULT_TEMPERATURE_C,
        "default_precipitation_mm": DEFAULT_PRECIPITATION_MM,
        "default_wind_speed_kmh": DEFAULT_WIND_SPEED_KMH,
    }
