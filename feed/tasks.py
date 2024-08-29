from celery import shared_task

import json
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format

from .models import Journey, Progression, Position, Progression, Occupancy

# For the _fake_stop_times method (temporary!)
import pandas as pd
import numpy as np
import random
from typing import Any

_CSV_FILE_PATH = "./aux/route_stops.csv"
# Time in seconds
_UNCERTAINTY_S = 120
_TIME_OFFSET_MIN_S = 150
_TIME_OFFSET_MAX_S = 300
_DEPARTURE_OFFSET_MAX_S = 120
_ARRIVAL_MAX_MIN = 5


@shared_task
def build_vehicle_position():

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = int(datetime.now().timestamp())

    # Feed message entity
    feed_message["entity"] = []

    journeys = Journey.objects.filter(journey_status="IN_PROGRESS")

    for journey in journeys:
        vehicle = journey.equipment.vehicle
        position = Position.objects.filter(journey=journey).latest("timestamp")
        progression = Progression.objects.filter(journey=journey).latest("timestamp")
        occupancy = Occupancy.objects.filter(journey=journey).latest("timestamp")
        # Entity
        entity = {}
        entity["id"] = f"bus-{vehicle.id}"
        entity["vehicle"] = {}
        # Timestamp
        entity["vehicle"]["timestamp"] = int(position.timestamp.timestamp())
        # Trip
        entity["vehicle"]["trip"] = {}
        entity["vehicle"]["trip"]["trip_id"] = journey.trip_id
        entity["vehicle"]["trip"]["route_id"] = journey.route_id
        entity["vehicle"]["trip"]["direction_id"] = journey.direction_id
        entity["vehicle"]["trip"]["start_time"] = _format_time(journey.start_time)
        entity["vehicle"]["trip"]["start_date"] = journey.start_date.strftime("%Y%m%d")
        entity["vehicle"]["trip"][
            "schedule_relationship"
        ] = journey.schedule_relationship
        # Vehicle
        entity["vehicle"]["vehicle"] = {}
        entity["vehicle"]["vehicle"]["id"] = vehicle.id
        entity["vehicle"]["vehicle"]["label"] = vehicle.label
        entity["vehicle"]["vehicle"]["license_plate"] = vehicle.license_plate
        # Position
        entity["vehicle"]["position"] = {}
        entity["vehicle"]["position"]["latitude"] = position.point.y
        entity["vehicle"]["position"]["longitude"] = position.point.x
        entity["vehicle"]["position"]["bearing"] = position.bearing
        entity["vehicle"]["position"]["odometer"] = position.odometer
        entity["vehicle"]["position"]["speed"] = position.speed
        # Progression
        entity["vehicle"]["current_stop_sequence"] = progression.current_stop_sequence
        entity["vehicle"]["stop_id"] = progression.stop_id
        entity["vehicle"]["current_status"] = progression.current_status
        entity["vehicle"]["congestion_level"] = progression.congestion_level
        # Occupancy
        entity["vehicle"]["occupancy_status"] = occupancy.occupancy_status
        entity["vehicle"]["occupancy_percentage"] = occupancy.occupancy_percentage
        # Append entity to feed message
        feed_message["entity"].append(entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message)   
    with open("feed/files/vehicle_positions.json", "w") as f:
        f.write(feed_message_json)

    # Create and save Protobuf
    feed_message_json = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_message_json, gtfs_rt.FeedMessage())
    with open("feed/files/vehicle_positions.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    return "Feed VehiclePosition built"


@shared_task
def build_trip_update():

    # Feed message dictionary
    feed_message = {}
    
    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = int(datetime.now().timestamp())
    
    # Feed message entity
    feed_message["entity"] = []

    journeys = Journey.objects.filter(journey_status="IN_PROGRESS")

    for journey in journeys:
        vehicle = journey.equipment.vehicle
        position = Position.objects.filter(journey=journey).latest("timestamp")
        progression = Progression.objects.filter(journey=journey).latest("timestamp")
        # Entity
        entity = {}
        entity["id"] = f"bus-{vehicle.id}"
        entity["trip_update"] = {}
        # Timestamp
        entity["trip_update"]["timestamp"] = int(position.timestamp.timestamp())
        # Trip
        entity["trip_update"]["trip"] = {}
        entity["trip_update"]["trip"]["trip_id"] = journey.trip_id
        entity["trip_update"]["trip"]["route_id"] = journey.route_id
        entity["trip_update"]["trip"]["direction_id"] = journey.direction_id
        entity["trip_update"]["trip"]["start_time"] = _format_time(journey.start_time)
        entity["trip_update"]["trip"]["start_date"] = journey.start_date.strftime(
            "%Y%m%d"
        )
        entity["trip_update"]["trip"][
            "schedule_relationship"
        ] = journey.schedule_relationship
        # Vehicle
        entity["trip_update"]["vehicle"] = {}
        entity["trip_update"]["vehicle"]["id"] = vehicle.id
        entity["trip_update"]["vehicle"]["label"] = vehicle.label
        entity["trip_update"]["vehicle"]["license_plate"] = vehicle.license_plate
        # Stop time update
        entity["trip_update"]["stop_time_update"] = _fake_stop_times(
            journey=journey, progression=progression
        )
        # Append entity to feed message
        feed_message["entity"].append(entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message)
    with open("feed/files/trip_updates.json", "w") as f:
        f.write(feed_message_json)

    # Create and save Protobuf
    feed_message_json = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_message_json, gtfs_rt.FeedMessage())
    with open("feed/files/trip_updates.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())

    return "Feed TripUpdate built"


@shared_task
def build_alert():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"


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


def _fake_stop_times(journey, progression) -> list[dict[str, Any]]:
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


def _format_time(time) -> str:
    """Format start time into a string in HH:MM:SS format.

    Args:
        start_time: The start time.

    Returns:
        str: The formatted start time as a string.
    """
    total_seconds = int(time.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
