# scripts

## `cleanup_runs.py`

Wipes run state from PostgreSQL and/or Redis so you can start fresh without
restarting any services.

```bash
docker compose -f compose.dev.yml exec -it orchestrator uv run scripts/cleanup_runs.py [options]
```

### PostgreSQL tables touched

- `runs_run` — Run records.
- `runs_runlifecycletransition`, `runs_run_vehicle`, `runs_run_operator` —
  cascade-deleted with the run (Django's `on_delete=CASCADE` is ORM-level
  only, so the script deletes these child tables explicitly before
  `runs_run`).
- With `--telemetry`: `runs_position`, `runs_progression`, `runs_occupancy`
  (`runs_progression` is decommissioned — no longer written, but old rows
  may still exist and are still cleaned up here).

### Redis keys touched

- `runs:tracking`, `runs:in_progress` (set membership).
- `run:<id>` (flat hash), `run:<id>:trip`, `run:<id>:vehicle_stop_status`,
  `run:<id>:congestion_level`, `runs:last_seen:<id>`.
- `vehicle:<id>:position`, `vehicle:<id>:occupancy`, `vehicle:<id>:metadata`.
- `vehicle|operator|trip:<id>:current_run` assignment keys.
- `vehicle:<id>:progression` is decommissioned and intentionally not touched.

### Modes (mutually exclusive)

| Flag | Effect |
|---|---|
| *(default)* | Delete all runs from DB + purge all run state from Redis. |
| `--run <id>` | Delete one run by ID (DB + Redis). |
| `--vehicle <id>` | Delete all runs for a vehicle (DB + Redis); also frees the vehicle's `current_run` key if it has no matching run. |
| `--db-only` | Only clean PostgreSQL, skip Redis. |
| `--redis-only` | Only clean Redis, skip PostgreSQL. |

### Options

| Flag | Effect |
|---|---|
| `--telemetry` | Also wipe `runs_position` / `runs_progression` / `runs_occupancy` rows. |
| `--dry-run` | Preview only (counts what *would* be deleted/removed); touches nothing. |
| `--yes` | Skip the confirmation prompt (only prompted for the bulk default mode, not `--run`/`--vehicle`). |
| `--db-host`, `--db-port`, `--db-name`, `--db-user`, `--db-pass` | PostgreSQL connection overrides (default from `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` env vars, else `localhost`). |
| `--redis-host`, `--redis-port`, `--redis-db` | Redis connection overrides (default from `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB` env vars, else `localhost`). |

### Examples

```bash
# Preview only
uv run scripts/cleanup_runs.py --dry-run

# Full reset: wipe all runs from DB + Redis
uv run scripts/cleanup_runs.py --yes

# Also wipe position/occupancy telemetry rows
uv run scripts/cleanup_runs.py --yes --telemetry

# Clear one specific run
uv run scripts/cleanup_runs.py --run <uuid>

# Clear all runs for one vehicle
uv run scripts/cleanup_runs.py --vehicle <vehicle_id>

# DB only / Redis only
uv run scripts/cleanup_runs.py --yes --db-only
uv run scripts/cleanup_runs.py --redis-only
```

The script auto-loads a `.env` file (walking up from `scripts/` to the
project root) before resolving connection defaults; shell env vars take
precedence over `.env` values.
