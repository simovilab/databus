# GTFS-RT Data Simulator and Testing Scripts

This directory contains scripts for simulating real-time vehicle telemetry data, monitoring Redis state, and maintaining data freshness for the GTFS-RT feed publisher system.

## Overview

The publisher system consists of:
- **Publisher Container**: Celery worker that builds GTFS-RT feeds (VehiclePositions and TripUpdates)
- **Scheduler Container**: Celery Beat that triggers feed builders every 15 seconds
- **Redis (state)**: Stores real-time vehicle position and trip progression data
- **RabbitMQ (message-broker)**: Message broker for Celery tasks

## Scripts

### 1. `continuous_simulator.py` - Real-time Data Simulator

Continuously publishes vehicle position updates to Redis, simulating real-time telemetry data from vehicles. Runs independently of Celery tasks and updates Redis every N seconds (default: 15s).

**Basic Usage:**

```bash
# Initialize Redis and start simulation
uv run scripts/continuous_simulator.py --init

# Run with custom interval (10s)
uv run scripts/continuous_simulator.py --interval 10

# Start simulation (assumes data already in Redis)
uv run scripts/continuous_simulator.py
```

**Edge Case Testing:**

Simulate various failure scenarios for testing:

```bash
# Stop updating a specific vehicle (simulate data loss)
uv run scripts/continuous_simulator.py --stop-vehicle unit-10

# Stop multiple vehicles
uv run scripts/continuous_simulator.py --stop-vehicle unit-10 --stop-vehicle unit-22

# Only update specific vehicle(s) - all others stop
uv run scripts/continuous_simulator.py --only-vehicle unit-10

# Random drop rate (30% chance to skip each vehicle each cycle)
uv run scripts/continuous_simulator.py --random-drop-rate 30

# Stop all updates after 5 cycles (simulate complete system failure)
uv run scripts/continuous_simulator.py --stop-all-after 5
```

**What it does:**
- Updates vehicle positions, progression, and occupancy every 15s (configurable)
- Simulates realistic movement (speed, bearing, GPS coordinates)
- Advances vehicles through stops with progression states
- Runs indefinitely until stopped (Ctrl+C)
- Data persists in Redis (not deleted)

### 2. `inspect_redis.py` - Redis State Inspector

Inspect the current state of Redis database, showing all vehicles, runs, and data freshness.

**Usage:**

```bash
# Show all data
uv run scripts/inspect_redis.py

# Show only vehicles with data age
uv run scripts/inspect_redis.py --vehicles --show-age

# Show only runs
uv run scripts/inspect_redis.py --runs

# Watch mode - refresh every 5 seconds
uv run scripts/inspect_redis.py --watch 5

# Show all Redis keys (debug mode)
uv run scripts/inspect_redis.py --all-keys
```

**What it does:**
- Displays vehicle position, progression, and occupancy data
- Shows run information
- Calculates and displays data age (how stale the data is)
- Categorizes data freshness: recent (<2m), stale (2-5m), very stale (>5m)
- Watch mode for real-time monitoring

### 3. `cleanup_redis.py` - Stale Data Cleanup

Removes stale vehicle data from Redis based on configurable age thresholds. Uses hybrid approach: publisher marks when feeds were built, cleanup script removes old data.

**Usage:**

```bash
# Dry run (see what would be deleted)
uv run scripts/cleanup_redis.py --dry-run

# Clean data older than 3 minutes (default)
uv run scripts/cleanup_redis.py

# Clean data older than 5 minutes
uv run scripts/cleanup_redis.py --max-age 300

# Run continuously (clean every 60 seconds)
uv run scripts/cleanup_redis.py --continuous 60

# Force clean all vehicle data
uv run scripts/cleanup_redis.py --force-all --dry-run
```

**What it does:**
- Finds vehicles with stale position data
- Removes data older than threshold (default: 3 minutes / 180 seconds)
- Can run as one-time cleanup or continuous daemon
- Dry-run mode to preview deletions
- Detailed reporting of cleaned data

### 4. `redis_seed_data.py` - Initial Data Seeder

One-time seeding of Redis with initial test data. **Typically used via `continuous_simulator.py --init`**.

**Usage:**

```bash
uv run scripts/redis_seed_data.py
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

**Note:** Prefer using `continuous_simulator.py --init` for complete workflow.

## Complete Testing Workflow

### Recommended: Continuous Simulation with Monitoring

This simulates a production environment with continuous data updates and real-time monitoring.

**Terminal 1 - Start Docker Stack:**
```bash
docker compose -f compose.dev.yml up
```

**Terminal 2 - Start Simulator:**
```bash
# Initialize Redis and start simulation
uv run scripts/continuous_simulator.py --init

# Or test edge cases
uv run scripts/continuous_simulator.py --init --stop-vehicle unit-10
```

**Terminal 3 - Monitor Redis State:**
```bash
# Watch Redis in real-time
uv run scripts/inspect_redis.py --watch 5 --show-age
```

**Terminal 4 - Check Feed Output:**
```bash
# Watch feed updates
docker compose -f compose.dev.yml logs -f publisher scheduler

# Or check files directly
docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq
docker compose -f compose.dev.yml exec publisher cat feed/files/trip_updates.json | jq
```

**Terminal 5 - Run Cleanup (Optional):**
```bash
# Clean stale data continuously
uv run scripts/cleanup_redis.py --continuous 120 --dry-run
```

### Quick Testing: One-time Validation

For quick testing without continuous simulation.

1. **Start the stack:**
   ```bash
   docker compose -f compose.dev.yml up
   ```

2. **Seed Redis with test data:**
   ```bash
   uv run scripts/redis_seed_data.py
   ```

3. **Inspect Redis state:**
   ```bash
   uv run scripts/inspect_redis.py --show-age
   ```

4. **Check the output files:**
   ```bash
   docker compose -f compose.dev.yml exec publisher cat feed/files/vehicle_positions.json | jq
   docker compose -f compose.dev.yml exec publisher cat feed/files/trip_updates.json | jq
   ```

**Note:** Data won't change unless you run the simulator or manually update Redis.

## Data Architecture

### Data Flow
```
┌──────────────────────┐
│ continuous_simulator │  Updates Redis every 15s (independent)
│   (Python script)    │  - Simulates vehicle movement
└──────────┬───────────┘  - Updates position, progression, occupancy
           │
           ▼
┌─────────────────┐
│  Redis (state)  │  ← Current vehicle state stored here
└────────┬────────┘  ← Data persists until cleaned up
         │
         ├─────────────────────────────┐
         │                             │
         ▼                             ▼
┌─────────────────┐          ┌──────────────────┐
│   Scheduler     │          │  cleanup_redis   │  Removes data > 3 min old
│  (Celery Beat)  │          │  (Optional)      │
└────────┬────────┘          └──────────────────┘
         │
         ▼
┌─────────────────┐
│   RabbitMQ      │
│ (message-broker)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Publisher     │  ← Reads latest data from Redis
│ (Celery Worker) │  ← Skips data > 2 minutes old
└────────┬────────┘  ← Builds GTFS-RT feeds
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

### Stale Data Handling

The system implements a graduated staleness approach:

1. **Data < 2 minutes old**: Included in feeds (fresh)
2. **Data > 2 minutes old**: Excluded from feeds (stale, not published)
3. **Data > 3 minutes old**: Removed from Redis by cleanup script (if running)

**Architecture:**
- **Simulator** writes to Redis (data persists)
- **Publisher** reads from Redis and filters stale data
- **Cleanup script** (optional) removes old data from Redis

**Key Points:**
- Simulator and Scheduler run **independently** (not synchronized)
- Simulator **updates** Redis data in place (no deletion)
- Publisher **reads** and **filters** Redis data (skips stale, no deletion)
- Cleanup script **removes** old data (optional, can run as daemon)
- Data flows continuously without manual re-seeding

## Output Files

The publisher tasks generate these files in `publisher/feed/files/`:

- `vehicle_positions.json` - VehiclePosition feed in JSON format (pretty-printed)
- `vehicle_positions.pb` - VehiclePosition feed in Protobuf format
- `trip_updates.json` - TripUpdate feed in JSON format (pretty-printed)
- `trip_updates.pb` - TripUpdate feed in Protobuf format

These files are **excluded from git** (listed in `.gitignore`) as they are generated outputs.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `16379` | Redis port (Docker mapping) |
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

# Test Redis connection (note: Docker maps 6379 to 16379)
redis-cli -h localhost -p 16379 ping
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
# Inspect Redis state
uv run scripts/inspect_redis.py

# Re-seed the data
uv run scripts/redis_seed_data.py

# Or use simulator with --init
uv run scripts/continuous_simulator.py --init
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

### Data is stale or not updating
```bash
# Check data age
uv run scripts/inspect_redis.py --show-age

# Check if simulator is running
# (should see continuous output in simulator terminal)

# Check publisher logs for skipped vehicles
docker compose -f compose.dev.yml logs -f publisher | grep "skipped\|stale"
```

## Using uv

All scripts use `uv` for Python package management. To run scripts:

```bash
# Run a script with uv
uv run scripts/continuous_simulator.py --init

# Install dependencies (if needed)
uv sync
```

The `uv` tool automatically manages dependencies from `pyproject.toml` files.

## Next Steps

In production, the system will:
1. Replace simulator with real telemetry data from vehicles via MQTT/API
2. Replace `build_stop_time_updates()` mock function with actual GTFS database queries
3. Schedule cleanup script as cron job or Celery periodic task
4. Add monitoring and alerting for stale data
5. Implement feed versioning and incremental updates
6. Add authentication and access control for feed endpoints
7. Add run completion logic (currently vehicles stay at last stop indefinitely)
