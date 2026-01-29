# Quick Start Guide - GTFS-RT Publisher Testing

Get the GTFS-RT publisher system running in 3 steps.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.14+ with required packages

## Step 1: Start the Stack

```bash
docker compose -f compose.dev.yml up
```

This starts:
- PostgreSQL (store)
- Redis (state)
- RabbitMQ (message-broker)
- Django backend
- Publisher (Celery worker)
- Scheduler (Celery beat)
- And other services...

## Step 2: Start the Continuous Simulator

In a **new terminal**:

```bash
python scripts/continuous_simulator.py --init
```

This will:
1. Initialize Redis with test vehicle data
2. Start updating vehicle positions every 15 seconds
3. Keep running until you press Ctrl+C

You should see output like:
```
[Cycle 1] 2026-01-28 18:45:00
--------------------------------------------------------------------------------
  ✓ unit-10: (9.936512, -84.051089) @ 12.3m/s | Stop 4 IN_TRANSIT_TO | 45% full
  ✓ unit-22: (9.935089, -84.055612) @ 0.0m/s | Stop 6 STOPPED_AT | 76% full
--------------------------------------------------------------------------------
Updated 2 vehicles
```

## Step 3: Monitor the System

In **another terminal**, watch the publisher logs:

```bash
docker compose -f compose.dev.yml logs -f publisher scheduler
```

You should see messages like:
```
publisher_1   | [2026-01-28 18:45:15] Task publisher.build_vehicle_positions succeeded
publisher_1   | [2026-01-28 18:45:15] Task publisher.build_trip_updates succeeded
```

## Step 4: Check the Output

View the generated GTFS-RT feeds:

```bash
# List output files
docker compose -f compose.dev.yml exec publisher ls -lh feed/files/

# View VehiclePosition feed
docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq

# View TripUpdate feed
docker compose -f compose.dev.yml exec publisher cat feed/files/trip_updates.json | jq

# Watch feed timestamps update in real-time
watch -n 2 'docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq ".header.timestamp"'
```

## What's Happening?

```
Simulator (Terminal 2)         Scheduler (Docker)         Publisher (Docker)
      │                               │                          │
      │ Updates Redis                 │                          │
      │ every 15s                     │                          │
      ├──────────────────────────────►│                          │
      │                               │ Triggers tasks           │
      │                               │ every 15s                │
      │                               ├─────────────────────────►│
      │                               │                          │
      │                               │                          │ Reads Redis
      │                               │                          │ Builds feeds
      │                               │                          │ Saves files
      │                               │                          │
      └───────────────────────────────┴──────────────────────────┘
           (Independent timing - not synchronized)
```

## Stopping the System

1. Press **Ctrl+C** in the simulator terminal to stop the simulator
2. Press **Ctrl+C** in the Docker Compose terminal to stop all containers

Or run:
```bash
docker compose -f compose.dev.yml down
```

## Common Issues

### "Cannot connect to Redis"
```bash
# Make sure Redis is running
docker compose -f compose.dev.yml ps state
docker compose -f compose.dev.yml up state
```

### "No data in Redis"
```bash
# Re-run with --init flag
python scripts/continuous_simulator.py --init
```

### "Tasks not being picked up"
```bash
# Check if publisher and scheduler are running
docker compose -f compose.dev.yml ps publisher scheduler

# Check logs for errors
docker compose -f compose.dev.yml logs publisher scheduler
```

## Next Steps

- Adjust simulator interval: `python scripts/continuous_simulator.py --interval 10`
- Test tasks directly: `python scripts/test_publisher_tasks.py --task both`
- Read full documentation: `scripts/README.md`
- Customize vehicle routes and stops in `scripts/redis_seed_data.py`

## Production Deployment

In production, replace:
- `continuous_simulator.py` → Real vehicle telemetry system
- Mock stop time updates → Actual GTFS database queries
- File outputs → HTTP API endpoints with authentication

See `scripts/README.md` for more details.
