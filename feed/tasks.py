from celery import shared_task

import json
import datetime
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format

from .models import Trip, Vehicle, Position, Path, Occupancy


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
        vehicle_entity = {}
        vehicle_entity["id"] = f"bus-{vehicle.id}"
        vehicle_entity["vehicle"] = {}
        # Timestamp
        vehicle_entity["vehicle"]["timestamp"] = int(position.timestamp.timestamp())
        # Trip
        vehicle_entity["vehicle"]["trip"] = {}
        vehicle_entity["vehicle"]["trip"]["trip_id"] = trip.trip_id
        vehicle_entity["vehicle"]["trip"]["route_id"] = trip.route_id
        vehicle_entity["vehicle"]["trip"]["direction_id"] = trip.direction_id
        vehicle_entity["vehicle"]["trip"]["start_time"] = str(trip.start_time)
        vehicle_entity["vehicle"]["trip"]["start_date"] = trip.start_date.strftime('%Y%m%d')
        vehicle_entity["vehicle"]["trip"]["schedule_relationship"] = trip.schedule_relationship
        # Vehicle
        vehicle_entity["vehicle"]["vehicle"] = {}
        vehicle_entity["vehicle"]["vehicle"]["id"] = vehicle.id
        vehicle_entity["vehicle"]["vehicle"]["label"] = vehicle.label
        vehicle_entity["vehicle"]["vehicle"]["license_plate"] = vehicle.license_plate
        # Position
        vehicle_entity["vehicle"]["position"] = {}
        vehicle_entity["vehicle"]["position"]["latitude"] = position.point.y
        vehicle_entity["vehicle"]["position"]["longitude"] = position.point.x
        vehicle_entity["vehicle"]["position"]["bearing"] = position.bearing
        vehicle_entity["vehicle"]["position"]["odometer"] = position.odometer
        vehicle_entity["vehicle"]["position"]["speed"] = position.speed
        # Path
        vehicle_entity["vehicle"]["current_stop_sequence"] = path.current_stop_sequence
        vehicle_entity["vehicle"]["stop_id"] = path.stop_id
        vehicle_entity["vehicle"]["current_status"] = path.current_status
        vehicle_entity["vehicle"]["congestion_level"] = path.congestion_level
        # Occupancy
        vehicle_entity["vehicle"]["occupancy_status"] = occupancy.occupancy_status
        vehicle_entity["vehicle"]["occupancy_percentage"] = occupancy.occupancy_percentage
        # Append entity to feed message
        feed_message["entity"].append(vehicle_entity)

    # Create and save JSON
    feed_message_json = json.dumps(feed_message, indent=4)
    with open("feed/files/vehicle_positions.json", "w") as f:
        f.write(feed_message_json)
    
    # Create and save Protobuf
    feed_message_json = json.loads(feed_message_json)
    feed_message_pb = json_format.ParseDict(feed_message_json, gtfs_rt.FeedMessage())
    with open("feed/files/vehicle_positions.pb", "wb") as f:
        f.write(feed_message_pb.SerializeToString())
    
    print(feed_message_json)

    return "Feed VehiclePosition built"


@shared_task
def build_trip_update():
    print("Building feed TripUpdate...")
    return "Feed TripUpdate built"


@shared_task
def build_alert():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"
