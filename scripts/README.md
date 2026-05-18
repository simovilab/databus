# scripts/

Operator utilities for the running databus stack. All scripts require only
`redis-py`; run them via `docker compose exec` or a host `pip install redis`.

## dev.sh

Starts the full development stack:

```bash
./scripts/dev.sh
```

Equivalent to `docker compose -f compose.dev.yml up --build`. Use this as the
standard entry point for local development.

## prod.sh

Starts the production stack:

```bash
./scripts/prod.sh
```

## inspect_redis.py

Read-only inspection of the live Redis state — vehicles, runs, position data,
and data age. Useful for verifying that the simulator or a real vehicle is
publishing telemetry.

```bash
docker compose -f compose.dev.yml exec state \
  redis-cli keys '*'

# Or against a host Redis:
python scripts/inspect_redis.py
```

## cleanup_redis.py

Removes stale vehicle data from Redis based on configurable age thresholds.
Run ad-hoc or as a periodic operator task; it does not modify any PostgreSQL
state.

```bash
# Dry-run (preview only)
python scripts/cleanup_redis.py --dry-run

# Remove data older than 3 minutes (default)
python scripts/cleanup_redis.py

# Custom threshold
python scripts/cleanup_redis.py --max-age 300
```

## Telemetry source

The canonical telemetry source is the external **simulator** repo at
`../simulator/`. It publishes vehicle positions over MQTT to the
`telemetry-broker` service (NanoMQ, port 1883). Use the simulator repo instead
of any local scripts for telemetry generation.
