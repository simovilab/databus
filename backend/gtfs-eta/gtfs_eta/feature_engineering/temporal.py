"""
Temporal feature extraction for gtfs_eta.

Ported verbatim from eta_prediction/feature_engineering/temporal.py on
branch feature/eta_prediction; only the import path was changed (no
sys.path hacks needed in this package).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

try:
    import zoneinfo  # py3.9+
except ImportError:  # pragma: no cover
    from backports import zoneinfo  # type: ignore


def _get_holiday_calendar(region: str):
    """
    Try to build a holiday calendar. Falls back to empty set if 'holidays' isn't installed.
    region:
      - 'US_MA' -> U.S. w/ Massachusetts state holidays (good for MBTA)
      - 'CR'    -> Costa Rica
    """
    try:
        import holidays
    except Exception:
        return None

    if region.upper() == "US_MA":
        return holidays.US(state="MA")
    if region.upper() == "CR":
        # Requires holidays>=0.52 which includes CostaRica
        try:
            return holidays.CostaRica()
        except Exception:
            return None
    # Fallback: US federal only
    return holidays.US()


def _to_local(dt: datetime, tz: str) -> datetime:
    """Ensure timezone-aware datetime localized to tz."""
    tzinfo = zoneinfo.ZoneInfo(tz)
    if dt.tzinfo is None:
        # assume input is UTC if naive
        return dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(tzinfo)
    return dt.astimezone(tzinfo)


def _tod_bin(hour: int) -> str:
    """
    Map hour -> time-of-day bin.
    Spec requires: 'morning' | 'midday' | 'afternoon' | 'evening'.
    """
    if 5 <= hour <= 9:
        return "morning"
    if 10 <= hour <= 13:
        return "midday"
    if 14 <= hour <= 17:
        return "afternoon"
    return "evening"


def extract_temporal_features(
    timestamp: datetime,
    *,
    tz: str = "America/New_York",
    region: str = "US_MA",
) -> Dict[str, object]:
    """
    Returns:
        - hour: 0-23
        - day_of_week: 0-6 (Monday=0)
        - is_weekend: bool
        - is_holiday: bool
        - time_of_day_bin: 'morning'|'midday'|'afternoon'|'evening'
        - is_peak_hour: bool (7-9am, 4-7pm; weekdays only)
    """
    dt_local = _to_local(timestamp, tz)
    hour = dt_local.hour
    dow = dt_local.weekday()  # Monday=0
    is_weekend = dow >= 5

    cal = _get_holiday_calendar(region)
    is_holiday = bool(cal and (dt_local.date() in cal))

    is_peak_hour = (dow < 5) and ((7 <= hour <= 9) or (16 <= hour <= 19))

    return {
        "hour": hour,
        "day_of_week": dow,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "time_of_day_bin": _tod_bin(hour),
        "is_peak_hour": is_peak_hour,
    }
