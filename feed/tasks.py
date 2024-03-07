from celery import shared_task

from .models import BusData

import json
import datetime


@shared_task
def build_vehicle_position():
    print("Building feed VehiclePosition...")

    unprocessed_data = BusData.objects.filter(is_processed=False)

    feed_message = {}
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = int(datetime.datetime.now().timestamp())
    feed_message["entity"] = []

    for vehicle in unprocessed_data:
        vehicle_entity = {}
        vehicle_entity["id"] = vehicle.vehicle_id
        vehicle_entity["vehicle"] = {}

        vehicle_entity["vehicle"]["vehicle"] = {}
        vehicle_entity["vehicle"]["vehicle"]["id"] = vehicle.vehicle_id

        feed_message["entity"].append(vehicle_entity)

        vehicle.is_processed = True
        vehicle.save()

    feed_message_json = json.dumps(feed_message)
    print(feed_message_json)

    # Query the database ("BusData" table) for new vehicle positions
    # Create a new feed in a JSON format
    # Expose the JSON feed to the API (bus.ucr.ac.cr/gtfs/realtime/vehicle_position.json)
    # Save the feed to a binary protobuf file, available at a given URL (bus.ucr.ac.cr/gtfs/realtime/vehicle_position.pb)
    return "Feed VehiclePosition built"


@shared_task
def build_trip_update():
    print("Building feed TripUpdate...")
    return "Feed TripUpdate built"


@shared_task
def build_alert():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"
