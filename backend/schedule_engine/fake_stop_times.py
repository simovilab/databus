# For the _fake_stop_times method (temporary!)
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_CSV_FILE_PATH = Path(__file__).resolve().parent / "aux_files" / "route_stops.csv"
# Time in seconds
_UNCERTAINTY_S = 120
_TIME_OFFSET_MIN_S = 150
_TIME_OFFSET_MAX_S = 300
_ARRIVAL_MAX_MIN = 5


def _load_route_stops(csv_file_path) -> pd.DataFrame:
    """Load route stops from a CSV file.

    Parameters:
        csv_file_path: Name of CSV file with route stops.

    Returns:
        pd.DataFrame: Information of CSV file as a Pandas DataFrame.
    """
    return pd.read_csv(csv_file_path, dtype={"stop_sequence": np.uint32})


def _generate_stop_entry(
    arrival_time, stop_sequence, stop_id, uncertainty
) -> dict[str, Any]:
    """Generate a stop entry with given parameters.

    Parameters:
        arrival_time: Estimated time of arrival to stop as absolute time. In POSIX time.
        stop_sequence: Order of stops in route.
        stop_id: ID of stop.
        uncertainty: Margin of error in the estimated time of arrival.

    Returns:
        dict[str, Any]: A dictionary entry with stop time updates.
    """
    return {
        "stop_sequence": int(stop_sequence),
        "stop_id": str(stop_id),
        "eta_posix": int(arrival_time.timestamp()),
        "uncertainty": uncertainty,
    }


def _safe_int(value, default: int = -1) -> int:
    """Coerce a Redis-string value to int, returning ``default`` on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_stop_time_updates(run, progression) -> list[dict[str, Any]]:
    """Generate fake stop times for the given run.

    Parameters:
        run: Mapping with at least ``route_id`` and ``shape_id`` keys
            (typically a Redis hash dict).
        progression: Mapping with ``current_stop_sequence`` and
            ``current_status`` keys (typically a Redis hash dict).

    Returns:
        list[dict[str, Any]]: A list of dictionaries with stop time updates.
    """
    stop_time_update: list[dict[str, Any]] = []

    run = run or {}
    progression = progression or {}

    route_id = str(run.get("route_id") or "").strip()
    shape_id = str(run.get("shape_id") or "").strip()
    if not route_id:
        logger.warning("build_stop_time_updates: run missing route_id (run=%s)", run)
        return stop_time_update

    try:
        route_stops = _load_route_stops(csv_file_path=_CSV_FILE_PATH)
    except FileNotFoundError:
        logger.exception("Route stops CSV not found at %s", _CSV_FILE_PATH)
        return stop_time_update

    # Primary match: route_id AND shape_id
    filtered_stops = route_stops[
        (route_stops["route_id"].astype(str) == route_id)
        & (route_stops["shape_id"].astype(str) == shape_id)
    ]

    # Fallback: match on route_id only (if shape_id is unknown or unmapped)
    if filtered_stops.empty:
        logger.info(
            "No CSV rows for route_id=%r shape_id=%r — falling back to route_id only",
            route_id,
            shape_id,
        )
        filtered_stops = route_stops[
            route_stops["route_id"].astype(str) == route_id
        ]

    if filtered_stops.empty:
        logger.warning(
            "build_stop_time_updates: no stops for route_id=%r (CSV has routes=%s)",
            route_id,
            sorted(route_stops["route_id"].astype(str).unique().tolist()),
        )
        return stop_time_update

    # Ensure ascending order so we walk stops in sequence
    filtered_stops = filtered_stops.sort_values("stop_sequence")

    current_stop_sequence = _safe_int(
        progression.get("current_stop_sequence"), default=-1
    )
    current_status = (progression.get("current_status") or "").upper()

    arrival_time = datetime.now() + timedelta(
        minutes=random.randint(0, _ARRIVAL_MAX_MIN)
    )

    for _, row in filtered_stops.iterrows():
        stop_sequence = int(row["stop_sequence"])

        # Skip stops the vehicle has already passed
        if stop_sequence < current_stop_sequence:
            continue

        # If the bus is currently stopped at this sequence, the next ETA is
        # the following stop, so skip the current one.
        if (
            current_status == "STOPPED_AT"
            and stop_sequence == current_stop_sequence
        ):
            continue

        stop_entry = _generate_stop_entry(
            arrival_time=arrival_time,
            stop_sequence=stop_sequence,
            stop_id=row["stop_id"],
            uncertainty=_UNCERTAINTY_S,
        )
        stop_time_update.append(stop_entry)
        arrival_time += timedelta(
            seconds=random.randint(_TIME_OFFSET_MIN_S, _TIME_OFFSET_MAX_S)
        )

    logger.debug(
        "build_stop_time_updates: route_id=%s shape_id=%s current_seq=%s status=%s -> %d stops",
        route_id,
        shape_id,
        current_stop_sequence,
        current_status,
        len(stop_time_update),
    )
    return stop_time_update
