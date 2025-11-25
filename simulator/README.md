# Telemetry Simulator

This simulator provides a testing platform for the Databus telemetry and tracking system before installing equipment on actual buses.

## Overview

The simulator periodically sends telemetry data to the realtime API server, including:

- Vehicle information
- Equipment data
- Journey/trip information
- GPS position updates
- Stop progression
- Vehicle occupancy

## Features

- Simulates vehicle movement along GTFS routes
- Generates realistic position updates every 10 seconds
- Updates occupancy when arriving at stops
- Logs all simulation events for monitoring
- Configurable simulation speed and parameters
- Multiple vehicles can be simulated simultaneously

## Architecture

The simulator is built using:

- **Django Models**: Store simulation state and configuration
- **Celery Beat**: Schedule periodic position updates
- **Django Admin**: Configure and monitor simulations
- **Management Commands**: Start and stop simulations

## Usage

### Starting a Simulation

Start simulation for all vehicles:
```bash
python manage.py start_simulation --all
```

Start simulation for a specific vehicle:
```bash
python manage.py start_simulation --vehicle SJB9876
```

Start with custom speed (in m/s):
```bash
python manage.py start_simulation --vehicle SJB9876 --speed 15.0
```

### Stopping a Simulation

Stop all simulations:
```bash
python manage.py stop_simulation --all
```

Stop specific vehicle:
```bash
python manage.py stop_simulation --vehicle SJB9876
```

### Monitoring Simulations

Access the Django admin panel to monitor:
- Active simulated vehicles
- Current journey status
- Simulation logs and events

Navigate to:
- `/admin/simulator/simulatedvehicle/` - Configure vehicles
- `/admin/simulator/simulationlog/` - View simulation logs

## Configuration

### Update Intervals

Update intervals are configured in Celery Beat schedule:

- **Position updates**: 10 seconds (configurable per vehicle)
- **Occupancy updates**: When arriving at stops
- **Log cleanup**: Daily

### Simulation Parameters

Each simulated vehicle can be configured with:

- `speed`: Simulation speed in m/s (default: 10.0)
- `update_interval`: Position update frequency in seconds (default: 10)
- `is_active`: Enable/disable simulation

## Data Flow

1. **Journey Start**: Simulator selects a trip and creates a Journey
2. **Position Updates**: Every 10 seconds, update vehicle position along shape
3. **Stop Detection**: Check if vehicle is near a stop
4. **Stop Arrival**: Update progression and occupancy
5. **Journey End**: Mark journey as complete when route finished

## API Endpoints Used

The simulator interacts with these API endpoints:

- `POST /api/journey/` - Create new journey
- `POST /api/position/` - Update vehicle position
- `POST /api/progression/` - Update stop progression
- `POST /api/occupancy/` - Update vehicle occupancy

## Models

### SimulatedVehicle

Stores configuration and state for each simulated vehicle:

- `vehicle`: Link to Vehicle model
- `equipment`: Link to Equipment model
- `is_active`: Whether simulation is running
- `current_journey`: Current simulated journey
- `current_stop_index`: Progress through stops
- `current_shape_index`: Progress through shape points
- `speed`: Simulation speed (m/s)
- `update_interval`: Update frequency (seconds)

### SimulationLog

Logs all simulation events:

- `simulated_vehicle`: Which vehicle
- `event_type`: Type of event (JOURNEY_START, POSITION_UPDATE, etc.)
- `timestamp`: When event occurred
- `message`: Human-readable description
- `data`: Additional event data (JSON)

## Celery Tasks

### update_simulated_positions

Periodic task that updates positions for all active simulations.

Schedule: Every 10 seconds

### cleanup_simulation_logs

Removes old simulation logs to prevent database bloat.

Schedule: Daily
Retention: 7 days

## Testing

The simulator is ideal for:

- Testing GTFS Realtime feed generation
- Validating API endpoints
- Load testing with multiple vehicles
- Demonstrating the system to stakeholders
- Developing client applications

## Limitations

- Does not simulate traffic conditions realistically
- Fixed speed along route (no acceleration/deceleration)
- Simplified occupancy model (random values)
- Does not simulate equipment failures or edge cases

## Future Enhancements

Potential improvements:

- More realistic traffic simulation
- Weather-based speed adjustments
- Rush hour occupancy patterns
- Equipment failure simulation
- Multiple routes per vehicle
- Replay of historical journeys
- Integration with "Proyecto Células TP"

## Troubleshooting

### No vehicles moving

Check:
1. Are any vehicles marked as active?
2. Is Celery Beat running?
3. Are there trips configured in GTFS data?
4. Check simulation logs for errors

### Position not updating

Verify:
1. Shape points exist for the route
2. Equipment is configured for the vehicle
3. Vehicle has an active journey
4. Check Celery task logs

### Journeys not completing

Ensure:
1. Shape points cover the full route
2. Stop times are configured correctly
3. Check simulation logs for errors
4. Verify journey status in database

## Related Documentation

- [GTFS Schedule Documentation](../gtfs/README.md)
- [API Documentation](../docs/api.md)
- [Celery Configuration](../docs/deployment.md)
