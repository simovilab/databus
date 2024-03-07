from celery import shared_task


@shared_task
def build_vehicle_position():
    print("Building feed VehiclePosition...")
    # Query the database for new vehicle positions
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
    print("Building feed Alert")
    return "Feed ServiceAlert built"
