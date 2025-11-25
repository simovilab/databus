from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from google.protobuf import json_format
from .models import Journey, Progression, Position, Progression, Occupancy
from .fake_stop_times import fake_stop_times


@shared_task
def build_vehicle_positions():
    """
    Build the VehiclePosition feed message."""

    # Feed message dictionary
    feed_message = {}

    # Feed message header
    feed_message["header"] = {}
    feed_message["header"]["gtfs_realtime_version"] = "2.0"
    feed_message["header"]["incrementality"] = "FULL_DATASET"
    feed_message["header"]["timestamp"] = int(datetime.now().timestamp())

    # Feed message entity
    feed_message["entity"] = []

    # TODO: Instrument this process with Prometheus
    journeys = Journey.objects.filter(journey_status="IN_PROGRESS")

    for journey in journeys:
        vehicle = journey.vehicle

        # Get position object
        positions = Position.objects.filter(vehicle=vehicle, is_new=True)
        if positions.exists():
            position = positions.latest("timestamp")
            for position in positions:
                position.is_new = False
                position.save()
        else:
            position = None
        # Get progression object
        progressions = Progression.objects.filter(vehicle=vehicle, is_new=True)
        if progressions.exists():
            progression = progressions.latest("timestamp")
            for progression in progressions:
                progression.is_new = False
                progression.save()
        else:
            progression = None
        # Get occupancy object
        occupancies = Occupancy.objects.filter(vehicle=vehicle, is_new=True)
        if occupancies.exists():
            occupancy = occupancies.latest("timestamp")
            for occupancy in occupancies:
                occupancy.is_new = False
                occupancy.save()
        else:
            occupancy = None

        if not position and not progression and not occupancy:
            # TODO: Log this event, create strategy to clean up stale journeys
            continue

        # Build entity
        entity = {}
        entity["id"] = f"{vehicle.id}"
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
        entity["vehicle"]["trip"]["schedule_relationship"] = (
            journey.schedule_relationship
        )
        # Vehicle
        entity["vehicle"]["vehicle"] = {}
        entity["vehicle"]["vehicle"]["id"] = vehicle.id
        entity["vehicle"]["vehicle"]["label"] = vehicle.label
        entity["vehicle"]["vehicle"]["license_plate"] = vehicle.license_plate
        # Position
        if position:
            entity["vehicle"]["position"] = {}
            entity["vehicle"]["position"]["latitude"] = position.point.y
            entity["vehicle"]["position"]["longitude"] = position.point.x
            entity["vehicle"]["position"]["bearing"] = position.bearing
            entity["vehicle"]["position"]["odometer"] = position.odometer
            entity["vehicle"]["position"]["speed"] = position.speed
        # Progression
        if progression:
            entity["vehicle"]["current_stop_sequence"] = (
                progression.current_stop_sequence
            )
            entity["vehicle"]["stop_id"] = progression.stop_id
            entity["vehicle"]["current_status"] = progression.current_status
            entity["vehicle"]["congestion_level"] = progression.congestion_level
        # Occupancy
        if occupancy:
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

    return "FeedMessage VehiclePosition built successfully"


@shared_task
def build_trip_updates():
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
        entity["trip_update"]["trip"]["schedule_relationship"] = (
            journey.schedule_relationship
        )
        # Vehicle
        entity["trip_update"]["vehicle"] = {}
        entity["trip_update"]["vehicle"]["id"] = vehicle.id
        entity["trip_update"]["vehicle"]["label"] = vehicle.label
        entity["trip_update"]["vehicle"]["license_plate"] = vehicle.license_plate
        # Stop time update
        entity["trip_update"]["stop_time_update"] = fake_stop_times(
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

    # Send status update to WebSocket
    message = {}
    message["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message["journeys"] = len(journeys)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "status",
        {
            "type": "status_message",
            "message": message,
        },
    )

    return f"Feed TripUpdate built."


@shared_task
def build_alerts():
    print("Building feed Alert...")
    return "Feed ServiceAlert built"


@shared_task
def update_journey_status():
    """
    Actualiza el estado de los viajes según criterios de terminación.
    
    Criterios:
    - Si last_update > TTL (5 minutos sin actualización) -> journey_status = 'STALE'
    - Si está en parada final > 2 minutos -> journey_status = 'COMPLETED'
    - Si journey_status = 'STALE' y no hay updates en 30 min -> journey_status = 'INTERRUPTED'
    """
    from django.utils import timezone
    from datetime import timedelta
    from gtfs.models import StopTime
    
    now = timezone.now()
    updated_count = 0
    
    # Obtener viajes en progreso
    journeys = Journey.objects.filter(journey_status='IN_PROGRESS')
    
    for journey in journeys:
        # Obtener última posición
        last_position = Position.objects.filter(journey=journey).order_by('-timestamp').first()
        
        if not last_position:
            continue
        
        time_since_update = now - last_position.timestamp
        
        # Criterio 1: Sin actualización por más de 5 minutos -> STALE
        if time_since_update > timedelta(minutes=5):
            journey.journey_status = 'STALE'
            journey.save()
            updated_count += 1
            continue
        
        # Criterio 2: Verificar si está en parada final
        last_progression = Progression.objects.filter(journey=journey).order_by('-timestamp').first()
        
        if last_progression:
            # Obtener última parada del trip
            final_stop = StopTime.objects.filter(
                trip__trip_id=journey.trip_id
            ).order_by('-stop_sequence').first()
            
            if final_stop and last_progression.stop_id == final_stop.stop_id:
                # Si lleva más de 2 minutos en parada final -> COMPLETED
                time_at_final = now - last_progression.timestamp
                if time_at_final > timedelta(minutes=2):
                    journey.journey_status = 'COMPLETED'
                    journey.save()
                    updated_count += 1
    
    # Criterio 3: Viajes STALE sin updates en 30 min -> INTERRUPTED
    stale_journeys = Journey.objects.filter(journey_status='STALE')
    
    for journey in stale_journeys:
        last_position = Position.objects.filter(journey=journey).order_by('-timestamp').first()
        if last_position:
            time_since_update = now - last_position.timestamp
            if time_since_update > timedelta(minutes=30):
                journey.journey_status = 'INTERRUPTED'
                journey.save()
                updated_count += 1
    
    return {
        'success': True,
        'updated_count': updated_count,
        'timestamp': now.isoformat()
    }


@shared_task
def update_conn_status():
    """
    Actualiza el estado de conexión de los equipos activos.
    
    Estados:
    - 'CONNECTED': Actualización reciente (< 30 segundos)
    - 'INACTIVE': Sin actualización por 30-300 segundos
    - 'LOST': Sin actualización por > 300 segundos (5 minutos)
    """
    from django.utils import timezone
    from datetime import timedelta
    from feed.models import Equipment
    
    now = timezone.now()
    updated_count = 0
    
    # Obtener todos los equipos
    equipments = Equipment.objects.all()
    
    for equipment in equipments:
        # Buscar última posición del vehículo asociado
        if not equipment.vehicle:
            continue
            
        last_position = Position.objects.filter(
            vehicle=equipment.vehicle
        ).order_by('-timestamp').first()
        
        if not last_position:
            # Sin posiciones registradas
            if equipment.conn_status != 'LOST':
                equipment.conn_status = 'LOST'
                equipment.save()
                updated_count += 1
            continue
        
        time_since_update = now - last_position.timestamp
        
        # Determinar estado de conexión
        new_status = None
        
        if time_since_update < timedelta(seconds=30):
            new_status = 'CONNECTED'
        elif time_since_update < timedelta(seconds=300):
            new_status = 'INACTIVE'
        else:
            new_status = 'LOST'
        
        # Actualizar si cambió el estado
        if equipment.conn_status != new_status:
            equipment.conn_status = new_status
            equipment.save()
            updated_count += 1
    
    return {
        'success': True,
        'updated_count': updated_count,
        'timestamp': now.isoformat()
    }


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
