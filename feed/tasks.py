from celery import shared_task

import json
import datetime
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format

# For the fake_stop_times function (temporary!)
import pandas as pd

from .models import Trip, Position, Path, Occupancy


@shared_task
def build_vehicle_position():

    # Feed message dictionary
    feed_message = {}
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = int(datetime.datetime.now().timestamp())
    feed_message["entity"] = []

    trips = Trip.objects.filter(ongoing=True)

    for trip in trips:
        vehicle = trip.equipment.vehicle
        position = Position.objects.filter(trip=trip).latest("timestamp")
        path = Path.objects.filter(trip=trip).latest("timestamp")
        occupancy = Occupancy.objects.filter(trip=trip).latest("timestamp")
        # Entity
        entity = {}
        entity["id"] = f"bus-{vehicle.id}"
        entity["vehicle"] = {}
        # Timestamp
        entity["vehicle"]["timestamp"] = int(position.timestamp.timestamp())
        # Trip
        entity["vehicle"]["trip"] = {}
        entity["vehicle"]["trip"]["trip_id"] = trip.trip_id
        entity["vehicle"]["trip"]["route_id"] = trip.route_id
        entity["vehicle"]["trip"]["direction_id"] = trip.direction_id
        entity["vehicle"]["trip"]["start_time"] = str(trip.start_time)
        entity["vehicle"]["trip"]["start_date"] = trip.start_date.strftime("%Y%m%d")
        entity["vehicle"]["trip"]["schedule_relationship"] = trip.schedule_relationship
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
        # Path
        entity["vehicle"]["current_stop_sequence"] = path.current_stop_sequence
        entity["vehicle"]["stop_id"] = path.stop_id
        entity["vehicle"]["current_status"] = path.current_status
        entity["vehicle"]["congestion_level"] = path.congestion_level
        # Occupancy
        entity["vehicle"]["occupancy_status"] = occupancy.occupancy_status
        entity["vehicle"]["occupancy_percentage"] = occupancy.occupancy_percentage
        # Append entity to feed message
        feed_message["entity"].append(entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message, indent=2)
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
    print("Building feed TripUpdate...")
    return "Feed TripUpdate built"


@shared_task
def build_alert():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"


def fake_stop_times():
    """
    Revisar en Path por cuál parada está el viaje, y devolver los tiempos de llegada a las siguientes paradas, con la siguiente aproximación: 3 minutos de intervalo entre cada parada.

    Ejemplos:
    - current_stop_sequence = 5, current_status = "IN_TRANSIT_TO": Devolver los tiempos de llegada a las paradas 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    - current_stop_sequence = 5, current_status = "INCOMING_AT": Devolver los tiempos de llegada a las paradas 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    - current_stop_sequence = 5, current_status = "STOPPED_AT": Devolver los tiempos de llegada a las paradas 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 (última).
    """
    route_stops = pd.read_csv("aux/route_stops.csv")
    stop_times = []
    return stop_times
