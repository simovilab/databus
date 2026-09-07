---
icon: lucide/wrench
---

# Troubleshooting & debugging

A reference for diagnosing the most common failure modes in Databús, with concrete commands and known solutions.

## Service logs

All troubleshooting starts with logs. The most relevant services for real-time issues are `realtime-engine`, `orchestrator`, and `scheduler`.

```bash
# All services
docker compose -f compose.dev.yml logs -f

# Specific services
docker compose -f compose.dev.yml logs -f realtime-engine
docker compose -f compose.dev.yml logs -f orchestrator
docker compose -f compose.dev.yml logs -f scheduler
docker compose -f compose.dev.yml logs -f schedule-engine

# Last N lines
docker compose -f compose.dev.yml logs --tail=100 realtime-engine
```

## RabbitMQ management UI

The RabbitMQ management interface at http://localhost:15672 (dev) or `https://${RABBITMQ_DOMAIN}` (prod) is the most efficient way to trace message flow issues:

- **Queues tab** — check `realtime_engine` and `schedule_engine` queue depths. A growing `realtime_engine` queue means the worker is falling behind MQTT throughput.
- **Connections tab** — verify Celery workers are connected.
- **Exchanges tab** — inspect the `databus.events` direct exchange (stub, currently unpopulated).

## Flower (Celery monitoring)

Flower at http://localhost:5555 (dev) or `https://${FLOWER_DOMAIN}` (prod) shows:

- Active, scheduled, and reserved tasks per worker.
- Failed tasks with their exception and traceback.
- Worker status and uptime.

Use Flower to confirm that the `realtime-engine` and `schedule-engine` workers are online and consuming their respective queues.

## Duplicate MQTT consumer symptom

**Symptom:** MQTT messages are processed twice; you see two sets of Redis writes for the same vehicle in rapid succession. Logs show repeated connect/disconnect cycles in the `realtime-engine` service.

**Cause:** More than one worker process has `MQTT_CONSUMER_ENABLED=true`. When a second consumer connects to NanoMQ with the same client ID, the broker treats it as a session takeover and disconnects the first client, which then reconnects, causing an endless loop.

**Fix introduced in commit 452d4f4:** Each consumer now builds a unique client ID from hostname and PID:

```python
client_id = f"databus-mqtt-consumer-{socket.gethostname()}-{os.getpid()}"
```

This prevents the reconnect war if a duplicate consumer appears. But the root fix is correct compose configuration: only the `realtime-engine` service should have `MQTT_CONSUMER_ENABLED=true`.

**Diagnosis:**

```bash
# Check which services have MQTT_CONSUMER_ENABLED set
docker compose -f compose.dev.yml config | grep -A2 MQTT_CONSUMER

# Check realtime-engine logs for repeated connect messages
docker compose -f compose.dev.yml logs realtime-engine | grep "MQTT conn"
```

## Telemetry not reaching Redis

**Symptom:** Vehicles are publishing but no `vehicle:<id>:position` keys appear in Redis.

Check in order:

1. **Is the MQTT consumer enabled?**
   ```bash
   docker compose -f compose.dev.yml logs realtime-engine | grep -i "mqtt consumer"
   ```
   Look for `"Starting MQTT consumer bootstep"`. If you see `"MQTT consumer bootstep disabled"`, `MQTT_CONSUMER_ENABLED` is not set.

2. **Is the vehicle assigned an active run?**
   The consumer drops all telemetry for vehicles without an active run:
   ```bash
   docker compose -f compose.dev.yml logs realtime-engine | grep "No active run"
   ```
   Create a run via the REST API or Django admin and confirm the vehicle is assigned.

3. **Is NanoMQ reachable?**
   ```bash
   docker compose -f compose.dev.yml logs telemetry-broker
   ```

4. **Is the topic format correct?**
   The expected format is `transit/vehicle/<id>/position`. Check the publisher's topic string.

## Redis inspection

Two scripts are provided in `scripts/` for inspecting and cleaning Redis state:

### Inspect current state

```bash
# Connect REDIS_HOST to localhost first (or run inside the container)
REDIS_HOST=localhost python scripts/inspect_redis.py

# Show all data (vehicles + runs)
python scripts/inspect_redis.py

# Show only vehicles with data age
python scripts/inspect_redis.py --vehicles --show-age

# Show only runs in progress
python scripts/inspect_redis.py --runs

# Continuous watch mode (refresh every 5 seconds)
python scripts/inspect_redis.py --watch 5

# Show all raw Redis keys (debug)
python scripts/inspect_redis.py --all-keys
```

Inside the compose network, exec into the `orchestrator` container:

```bash
docker compose -f compose.dev.yml exec orchestrator \
    python /app/scripts/inspect_redis.py --vehicles --show-age
```

### Manual Redis CLI inspection

```bash
# Connect to Redis
docker compose -f compose.dev.yml exec state redis-cli

# Key patterns
SMEMBERS runs:in_progress
SMEMBERS runs:tracking
HGETALL vehicle:<id>:position
HGETALL run:<id>:vehicle_stop_status
GET vehicle:<id>:current_run
GET runs:last_seen:<run_id>
GET run:<id>:stop_time_updates
```

## Stale run cleanup

After stopping the simulator or during testing, Redis (and PostgreSQL) may hold state for runs that are no longer active. Two scripts handle this at different scopes; commit `18f9bde` (`chore(scripts): add run-state cleanup script and refresh Redis utilities`) added `backend/scripts/cleanup_runs.py` and refreshed `scripts/cleanup_redis.py` to the current Redis key schema.

### `scripts/cleanup_redis.py` — Redis-only, age-based

Removes stale vehicle data from Redis based on a data-age threshold. Does not touch PostgreSQL.

```bash
# Dry run — see what would be deleted
python scripts/cleanup_redis.py --dry-run

# Clean vehicle data older than 3 minutes (default)
python scripts/cleanup_redis.py

# Clean vehicle data older than 5 minutes
python scripts/cleanup_redis.py --max-age 300

# Force delete ALL vehicle and run entity data (nuclear option)
python scripts/cleanup_redis.py --force-all --dry-run  # preview first
python scripts/cleanup_redis.py --force-all             # then execute

# Continuous mode (clean every 60 seconds)
python scripts/cleanup_redis.py --continuous 60
```

`--force-all` deletes these key patterns:
```
vehicle:*:metadata
vehicle:*:position
vehicle:*:occupancy
run:*:trip
run:*:vehicle_stop_status
run:*:congestion_level
run:*:stop_time_updates
```

It does **not** delete `run:<id>` (the run hash), `runs:in_progress`, or `runs:tracking` — those are owned by the lifecycle layer and cleaned up by the run completion/cancellation actions.

### `backend/scripts/cleanup_runs.py` — PostgreSQL + Redis, run-scoped

A more complete reset: wipes run state from **both** PostgreSQL (`runs_run` and its cascade-deleted child tables — `runs_runlifecycletransition`, `runs_run_vehicle`, `runs_run_operator`) and Redis (`runs:tracking`/`runs:in_progress` set membership, `run:<id>` and its sub-keys, `vehicle:<id>:*` keys, and the `vehicle|operator|trip:<id>:current_run` assignment keys) so a dev box can start fresh without restarting any service.

```bash
docker compose -f compose.dev.yml exec -it orchestrator uv run scripts/cleanup_runs.py [options]
```

| Mode (mutually exclusive) | Effect |
|---|---|
| *(default)* | Delete all runs from DB + purge all run state from Redis. |
| `--run <id>` | Delete one run by ID (DB + Redis). |
| `--vehicle <id>` | Delete all runs for a vehicle (DB + Redis); also frees the vehicle's `current_run` key if it has no matching run. |
| `--db-only` / `--redis-only` | Restrict to one store. |

Other flags: `--telemetry` (also wipe `runs_position`/`runs_progression`/`runs_occupancy` rows), `--dry-run` (preview, touches nothing), `--yes` (skip the confirmation prompt), plus `--db-*`/`--redis-*` connection overrides. Full flag reference: `backend/scripts/README.md`.

```bash
# Preview only
uv run scripts/cleanup_runs.py --dry-run

# Full reset: wipe all runs from DB + Redis
uv run scripts/cleanup_runs.py --yes

# Clear one specific run / one vehicle's runs
uv run scripts/cleanup_runs.py --run <uuid>
uv run scripts/cleanup_runs.py --vehicle <vehicle_id>
```

## GTFS-RT feeds not updating

**Symptom:** `backend/feed/files/` is empty or files are not refreshing every 15 seconds.

1. **Is the scheduler (Celery beat) running?**
   ```bash
   docker compose -f compose.dev.yml logs scheduler | grep "build-"
   ```
   You should see `"Scheduler: Sending due task build-vehicle-positions-every-15s"` every 15 seconds.

2. **Is the schedule-engine worker consuming tasks?**
   ```bash
   docker compose -f compose.dev.yml logs schedule-engine
   ```

3. **Are there runs in `runs:in_progress`?**
   ```bash
   docker compose -f compose.dev.yml exec state redis-cli SMEMBERS runs:in_progress
   ```
   Feeds build successfully even with zero runs (they produce empty entity lists), so this is not a blocker — but empty files are correct when there are no active runs.

4. **Is the feed directory writable?**
   `backend/feed/files/` is created on first build. Permission issues would appear as exceptions in the `schedule-engine` logs.

## Verify protobuf output

```python
from google.transit import gtfs_realtime_pb2

msg = gtfs_realtime_pb2.FeedMessage()
msg.ParseFromString(
    open("backend/feed/files/vehicle_positions.pb", "rb").read()
)
print(f"Entities: {len(msg.entity)}")
for e in msg.entity:
    print(e)
```

## Run state stuck in wrong lifecycle state

If a run is stuck in `IN_PROGRESS` after the vehicle has stopped reporting (e.g. after a crash mid-demo), the stale-run scanner (`scan_stale_runs`, every 30 s) should eventually fire `run_tracking_lost` (after 60 s) and then `run_tracking_expired` (after 600 s from the last seen timestamp).

To force immediate cleanup:

1. Use the Django admin to manually set the run's lifecycle state to `Cancelled`.
2. Use `scripts/cleanup_redis.py --force-all` to clear the Redis entity hashes.
3. Verify with `inspect_redis.py` that the run is gone from `runs:tracking` and `runs:in_progress`.

For a single known run ID, `docker compose -f compose.dev.yml exec -it orchestrator uv run scripts/cleanup_runs.py --run <run_id>` is a faster alternative to steps 1–3 — it **deletes** the run row and its Redis keys outright (rather than cancelling and leaving the row), so use it only when you don't need to keep the run record. See [Stale run cleanup](#stale-run-cleanup) above.

## Common log messages

| Message | Level | Meaning |
|---|---|---|
| `MQTT consumer bootstep disabled` | INFO | `MQTT_CONSUMER_ENABLED` is not set — expected on non-realtime workers |
| `Starting MQTT consumer bootstep` | INFO | Consumer starting normally |
| `MQTT connected: telemetry-broker:1883` | INFO | Broker connection established |
| `No active run for vehicle X — dropping Y` | DEBUG | Normal — vehicle not assigned a run |
| `Unknown telemetry leaf 'progression'` | DEBUG | Simulator publishing decommissioned leaf — safe to ignore |
| `Invalid position payload for vehicle X` | WARNING | Malformed MQTT payload — check publisher |
| `stop-status production failed` | ERROR | Map-matching exception — check GTFS feed is loaded |
| `scan_stale_runs: checked N runs, fired M events` | INFO | Periodic scan result |

## Related pages

- [Telemetry ingestion](../data-flow/telemetry-ingestion.md) — MQTT consumer architecture.
- [Celery workers, queues & beat](celery.md) — queue health and Flower.
- [Stale-run scanning](../runs/stale-runs.md) — staleness thresholds and detection.
- [Data model: Redis keys](../data-model/redis-keys.md) — canonical key reference.
