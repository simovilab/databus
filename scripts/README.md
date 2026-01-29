# Test Scripts for GTFS-RT Feed Publisher

This directory contains test scripts for the GTFS-RT feed publisher system.

## Overview

The publisher system consists of:
- **Publisher Container**: Celery worker that builds GTFS-RT feeds (VehiclePositions and TripUpdates)
- **Scheduler Container**: Celery Beat that triggers the feed builders every 15 seconds
- **Redis (state)**: Stores real-time vehicle position and trip progression data
- **RabbitMQ (message-broker)**: Message broker for Celery tasks

## Test Scripts

### 1. `continuous_simulator.py` (NEW - RECOMMENDED)

**Continuously publishes vehicle position updates to Redis**, simulating real-time telemetry data. This runs independently of the Celery tasks and updates Redis every N seconds (default: 15s).

**Usage:**

Initialize and start simulation:
```bash
python scripts/continuous_simulator.py --init
```

Run with custom interval (10s):
```bash
python scripts/continuous_simulator.py --interval 10
```

Just start simulation (assumes data already in Redis):
```bash
python scripts/continuous_simulator.py
```

**What it does:**
- Updates vehicle positions every 15s (configurable)
- Simulates realistic movement (speed, bearing, GPS coordinates)
- Advances vehicles through stops with progression states
- Updates occupancy levels dynamically
- Runs indefinitely until stopped (Ctrl+C)
- **Does NOT delete data** - publisher tasks just read the latest values

**Why use this:**
- No need to re-seed Redis manually
- Simulates production-like continuous data flow
- Independent from Celery scheduler (not in phase)
- Each update provides new, realistic position data

### 2. `redis_seed_data.py`

One-time seeding of Redis with initial test data.

**Usage:**
```bash
python scripts/redis_seed_data.py
```

**What it does:**
- Creates 2 test runs with sample vehicle data
- Populates Redis with:
  - `runs:in_progress` set
  - `run:{run_id}` hashes
  - `vehicle:{vehicle_id}:data` hashes
  - `vehicle:{vehicle_id}:position` hashes
  - `vehicle:{vehicle_id}:progression` hashes
  - `vehicle:{vehicle_id}:occupancy` hashes

**Note:** Use `continuous_simulator.py --init` instead for a complete workflow.

### 2. `test_publisher_tasks.py` (NEW)

Tests the publisher tasks and simulates continuous position updates.

**Usage:**

Test VehiclePosition builder:
```bash
python scripts/test_publisher_tasks.py --task vp
```

Test TripUpdate builder:
```bash
python scripts/test_publisher_tasks.py --task tu
```

Test both tasks:
```bash
python scripts/test_publisher_tasks.py --task both
```

Simulate continuous position updates (updates Redis every 5 seconds):
```bash
python scripts/test_publisher_tasks.py --simulate --interval 5
```

Simulate 10 updates then stop:
```bash
python scripts/test_publisher_tasks.py --simulate --max-iterations 10
```

Test via Celery (requires publisher worker running):
```bash
python scripts/test_publisher_tasks.py --task vp --celery
```

**What it does:**
- **Direct Testing**: Imports and runs the publisher tasks directly (bypasses Celery)
- **Celery Testing**: Sends tasks to the Celery worker via RabbitMQ
- **Simulation Mode**: Continuously updates vehicle positions in Redis to simulate live data

### 4. `test_feed_builder.py` (LEGACY - NOT RECOMMENDED)

Original test script that **consumes and deletes** Redis data after testing.

**Usage:**
```bash
python scripts/test_feed_builder.py --type vp
python scripts/test_feed_builder.py --type tu
```

**⚠️ Warning:** This script **deletes data from Redis** after reading (consume-and-delete pattern). You must re-seed Redis after each run. Use `continuous_simulator.py` or `test_publisher_tasks.py` instead.

## Complete Testing Workflow

### Option 1: Continuous Simulation (Recommended - Production-like)

This simulates a real production environment with continuous data updates.

1. **Start the Docker Compose stack:**
   ```bash
   docker compose -f compose.dev.yml up
   ```

2. **In another terminal, start the continuous simulator:**
   ```bash
   # Initialize Redis and start simulation
   python scripts/continuous_simulator.py --init

   # Or with custom interval (10s)
   python scripts/continuous_simulator.py --init --interval 10
   ```

3. **Monitor the system (in another terminal):**
   ```bash
   # Watch publisher logs
   docker compose -f compose.dev.yml logs -f publisher scheduler

   # Watch simulator output
   # (already running in terminal from step 2)
   ```

4. **Check the output files (in another terminal):**
   ```bash
   # Watch feed updates in real-time
   watch -n 2 'docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq ".header.timestamp"'

   # Or check manually
   docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq
   docker compose -f compose.dev.yml exec publisher cat feed/files/trip_updates.json | jq
   ```

**What's happening:**
- **Simulator** updates Redis every 15s with new vehicle positions
- **Scheduler** triggers feed builders every 15s (independent timing)
- **Publisher** reads from Redis and builds GTFS-RT feeds
- **No re-seeding needed** - data flows continuously

### Option 2: One-time Testing (Quick validation)

For quick testing without continuous simulation.

1. **Start the stack:**
   ```bash
   docker compose -f compose.dev.yml up
   ```

2. **Seed Redis with test data:**
   ```bash
   python scripts/redis_seed_data.py
   ```

3. **Monitor the feed builder logs:**
   ```bash
   docker compose -f compose.dev.yml logs -f publisher scheduler
   ```

4. **Check the output files:**
   ```bash
   # Inside the publisher container
   docker compose -f compose.dev.yml exec publisher ls -lh feed/files/

   # View JSON output
   docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json
   docker compose -f compose.dev.yml exec publisher cat feed/files/trip_updates.json
   ```

**Note:** Data won't change unless you manually update Redis or restart the simulator.

### Option 3: Direct Task Testing (Development/Debugging)

Test tasks directly without Docker or Celery.

1. **Start Redis:**
   ```bash
   docker compose -f compose.dev.yml up state
   ```

2. **Seed Redis:**
   ```bash
   python scripts/redis_seed_data.py
   ```

3. **Test the tasks directly:**
   ```bash
   python scripts/test_publisher_tasks.py --task both
   ```

4. **View output:**
   ```bash
   cat feed/files/vehicle_positions.json
   cat feed/files/trip_updates.json
   ```

**Note:** This bypasses Celery and runs tasks synchronously for debugging.

## Data Flow

```
┌──────────────────────┐
│ continuous_simulator │  Publishes updates every 15s (independent)
│   (Python script)    │
└──────────┬───────────┘
           │
           ▼
┌─────────────────┐
│  Redis (state)  │  ← Vehicle position/progression data stored here
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   Scheduler     │────→│   RabbitMQ       │
│  (Celery Beat)  │     │ (message-broker) │
└─────────────────┘     └────────┬─────────┘
  Triggers every 15s             │
  (not in phase with             ▼
   simulator)           ┌─────────────────┐
                        │   Publisher     │  ← Reads latest data from Redis
                        │ (Celery Worker) │  ← Builds GTFS-RT feeds
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   feed/files/   │
                        │  - vehicle_positions.json
                        │  - vehicle_positions.pb
                        │  - trip_updates.json
                        │  - trip_updates.pb
                        └─────────────────┘
```

**Key Points:**
- Simulator and Scheduler run **independently** (not synchronized)
- Simulator **updates** Redis data in place (no deletion)
- Publisher **reads** from Redis (no deletion)
- Data flows continuously without needing manual re-seeding

## Output Files

The publisher tasks generate these files:

- `feed/files/vehicle_positions.json` - VehiclePosition feed in JSON format
- `feed/files/vehicle_positions.pb` - VehiclePosition feed in Protobuf format
- `feed/files/trip_updates.json` - TripUpdate feed in JSON format
- `feed/files/trip_updates.pb` - TripUpdate feed in Protobuf format

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `RABBITMQ_USER` | `guest` | RabbitMQ username |
| `RABBITMQ_PASS` | `guest` | RabbitMQ password |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ hostname |
| `RABBITMQ_PORT` | `5672` | RabbitMQ port |

When running in Docker Compose, these are set automatically via `.env` and `.env.dev` files.

## Troubleshooting

### Cannot connect to Redis
```bash
# Check if Redis is running
docker compose -f compose.dev.yml ps state

# Check Redis logs
docker compose -f compose.dev.yml logs state

# Test Redis connection
redis-cli -h localhost -p 6379 ping
```

### Cannot connect to RabbitMQ
```bash
# Check if RabbitMQ is running
docker compose -f compose.dev.yml ps message-broker

# Check RabbitMQ management UI
open http://localhost:15672  # Default: guest/guest
```

### No data in Redis
```bash
# Re-seed the data
python scripts/redis_seed_data.py

# Check Redis data
redis-cli -h localhost -p 6379 SMEMBERS runs:in_progress
```

### Tasks not being picked up
```bash
# Check if publisher worker is running
docker compose -f compose.dev.yml ps publisher

# Check publisher logs
docker compose -f compose.dev.yml logs -f publisher

# Check scheduler logs
docker compose -f compose.dev.yml logs -f scheduler
```

## Next Steps

In production, the system will:
1. Replace `redis_seed_data.py` with real telemetry data from vehicles
2. Replace `build_stop_time_updates()` mock function with actual GTFS database queries
3. Add error handling and monitoring
4. Implement feed versioning and incremental updates
5. Add authentication and access control for feed endpoints
