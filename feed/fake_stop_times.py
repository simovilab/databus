# For the _fake_stop_times method (temporary!)
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import random
from typing import Any

_CSV_FILE_PATH = "./feed/aux/route_stops.csv"
# Time in seconds
_UNCERTAINTY_S = 120
_TIME_OFFSET_MIN_S = 150
_TIME_OFFSET_MAX_S = 300
_DEPARTURE_OFFSET_MAX_S = 120
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
    departure_time = arrival_time + timedelta(
        seconds=random.randint(0, _DEPARTURE_OFFSET_MAX_S)
    )
    return {
        "arrival": {"time": int(arrival_time.timestamp()), "uncertainty": uncertainty},
        "departure": {
            "time": int(departure_time.timestamp()),
            "uncertainty": uncertainty,
        },
        "stop_id": stop_id,
        "stop_sequence": stop_sequence,
    }


def fake_stop_times(journey, progression) -> list[dict[str, Any]]:
    """Generate fake stop times for the given journey.

    Parameters:
        journey:
        progression: An object containing current stop sequence and status.

    Returns:
        list[dict[str, Any]]: A list of dictionaries with stop time updates.

    Revisar en Progression por cuál parada está el viaje, y devolver los tiempos de llegada a las siguientes paradas, con la siguiente aproximación: 3 minutos de intervalo entre cada parada.

    Ejemplos:
    - current_stop_sequence = 5, current_status = "IN_TRANSIT_TO": Devolver los tiempos de llegada a las paradas 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    - current_stop_sequence = 5, current_status = "INCOMING_AT": Devolver los tiempos de llegada a las paradas 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    - current_stop_sequence = 5, current_status = "STOPPED_AT": Devolver los tiempos de llegada a las paradas 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    """
    stop_time_update: list[dict[str, Any]] = []
    route_stops = _load_route_stops(csv_file_path=_CSV_FILE_PATH)

    filtered_stops = route_stops[
        (route_stops["route_id"] == journey.route_id)
        & (route_stops["shape_id"] == journey.shape_id)
    ]

    if filtered_stops.empty:
        return stop_time_update

    # Start with an invalid value to ensure the first comparison is always true
    previous_stop_sequence = -1
    arrival_time = datetime.now() + timedelta(
        minutes=random.randint(0, _ARRIVAL_MAX_MIN)
    )

    for _, row in filtered_stops.iterrows():
        stop_sequence = row["stop_sequence"]

        if stop_sequence < progression.current_stop_sequence:
            continue

        if stop_sequence < previous_stop_sequence:
            # Modify the last entry to remove "departure"
            if stop_time_update:
                stop_time_update[-1].pop("departure", None)
            break

        if (
            progression.current_status == "STOPPED_AT"
            and stop_sequence == progression.current_stop_sequence
        ):
            continue

        stop_entry = _generate_stop_entry(
            arrival_time=arrival_time,
            stop_sequence=stop_sequence,
            stop_id=row["stop_id"],
            uncertainty=_UNCERTAINTY_S,
        )
        stop_time_update.append(stop_entry)
        previous_stop_sequence = stop_sequence
        arrival_time += timedelta(
            seconds=random.randint(_TIME_OFFSET_MIN_S, _TIME_OFFSET_MAX_S)
        )

    return stop_time_update
