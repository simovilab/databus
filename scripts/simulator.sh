#!/bin/bash

# Telemetry Simulator Management Script
# Usage: ./scripts/simulator.sh [start|stop|status] [--all | --vehicle PLATE]

set -e

ACTION=$1
shift

if [ -z "$ACTION" ]; then
    echo "Usage: $0 [start|stop|status] [--all | --vehicle PLATE]"
    exit 1
fi

case "$ACTION" in
    start)
        echo "Starting simulation..."
        docker-compose exec web python manage.py start_simulation "$@"
        ;;
    stop)
        echo "Stopping simulation..."
        docker-compose exec web python manage.py stop_simulation "$@"
        ;;
    status)
        echo "Simulation status:"
        docker-compose exec web python manage.py shell -c "
from simulator.models import SimulatedVehicle
sims = SimulatedVehicle.objects.filter(is_active=True)
print(f'Active simulations: {sims.count()}')
for sim in sims:
    journey_info = f'Journey {sim.current_journey_id}' if sim.current_journey else 'No journey'
    print(f'  - {sim.vehicle.license_plate}: {journey_info}, Stop {sim.current_stop_index}')
"
        ;;
    logs)
        echo "Recent simulation logs:"
        docker-compose exec web python manage.py shell -c "
from simulator.models import SimulationLog
logs = SimulationLog.objects.order_by('-timestamp')[:20]
for log in logs:
    print(f'{log.timestamp.strftime(\"%Y-%m-%d %H:%M:%S\")} [{log.event_type}] {log.simulated_vehicle.vehicle.license_plate}: {log.message}')
"
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Available actions: start, stop, status, logs"
        exit 1
        ;;
esac
