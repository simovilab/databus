#!/usr/bin/env python
"""
Run State Cleanup Script

Run inside the container:

  docker compose -f compose.dev.yml exec -it orchestrator uv run scripts/cleanup_runs.py

Wipes run state from both PostgreSQL and Redis so you can start fresh
without restarting any services.

PostgreSQL tables:
  runs_run                      Run records
  runs_runlifecycletransition   (CASCADE deleted with run)
  runs_runprogressevent         (CASCADE deleted with run)

With --telemetry:
  runs_position, runs_occupancy
  (runs_progression table is decommissioned; no longer written)

Redis keys (same scope as cleanup_redis.py --purge-runs):
  runs:tracking, runs:in_progress
  run:<id> (flat hash), run:<id>:trip, run:<id>:vehicle_stop_status,
  run:<id>:congestion_level, runs:last_seen:<id>
  vehicle:<id>:position, vehicle:<id>:occupancy, vehicle:<id>:metadata
  vehicle/operator/trip :current_run assignment keys
  (vehicle:<id>:progression is decommissioned — no longer written)

Modes (mutually exclusive):
  (default)         Delete all runs from DB + purge all run state from Redis
  --run <id>        Delete one run by ID (DB + Redis)
  --vehicle <id>    Delete all runs for a vehicle (DB + Redis)
  --db-only         Only clean PostgreSQL, skip Redis
  --redis-only      Only clean Redis, skip PostgreSQL

Options:
  --telemetry       Also wipe runs_position/runs_occupancy rows (runs_progression is decommissioned)
  --dry-run         Preview only; touch nothing
  --yes             Skip the confirmation prompt
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import redis

# Make the backend package importable when running this script directly.
# keys.py has zero imports (no Django, no Redis) so this is safe.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runs.domain.telemetry import keys as _keys  # noqa: E402

# ---------------------------------------------------------------------------
# Auto-load .env from the project root (two levels up from scripts/)
# Shell env vars take precedence over .env values.
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Walk up from this file's directory looking for a .env file."""
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent):
        env_file = candidate / ".env"
        if env_file.is_file():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file, override=False)
            except ImportError:
                # Fallback: parse the file manually (no external deps needed)
                with open(env_file) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ.setdefault(key, val)
            break

_load_dotenv()

SEP = "=" * 80


# ---------------------------------------------------------------------------
# Connections — params resolved at runtime from CLI args + env vars
# ---------------------------------------------------------------------------


def get_db(host: str, port: int, name: str, user: str, password: str):
    return psycopg2.connect(
        host=host, port=port, dbname=name, user=user, password=password,
    )


def get_redis(host: str, port: int, db: int) -> redis.Redis:
    return redis.Redis(host=host, port=port, db=db, decode_responses=True)


# ---------------------------------------------------------------------------
# PostgreSQL helpers
# ---------------------------------------------------------------------------


def _count(cur, table: str, where: str = "", params: tuple = ()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _delete(cur, table: str, where: str = "", params: tuple = (), dry_run: bool = False) -> int:
    n = _count(cur, table, where, params)
    if n and not dry_run:
        sql = f"DELETE FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cur.execute(sql, params)
    return n


# ---------------------------------------------------------------------------
# Redis helpers (lifted from cleanup_redis.py logic)
# ---------------------------------------------------------------------------


def _rdel(r: redis.Redis, keys: list[str], dry_run: bool) -> int:
    targets = [k for k in keys if r.exists(k)]
    if targets and not dry_run:
        r.delete(*targets)
    return len(targets)


def _rsrem(r: redis.Redis, set_key: str, members: list[str], dry_run: bool) -> int:
    if not members:
        return 0
    if dry_run:
        return sum(1 for m in members if r.sismember(set_key, m))
    return int(r.srem(set_key, *members))


def _purge_redis_run(r: redis.Redis, run_id: str, dry_run: bool) -> dict[str, int]:
    hash_data = r.hgetall(_keys.run_key(run_id))
    vehicle_id = hash_data.get("vehicle")
    operator_id = hash_data.get("operator")
    trip_id = hash_data.get("trip_id")

    # Run-keyed server-computed entity hashes (see runs/domain/telemetry/keys.py).
    direct = [
        _keys.run_key(run_id),
        _keys.trip_key(run_id),
        _keys.stop_status_key(run_id),
        _keys.congestion_key(run_id),
        _keys.last_seen_key(run_id),
    ]

    # Vehicle edge-data hashes (vehicle-keyed; only present when assigned).
    # vehicle:<id>:progression is decommissioned — omitted intentionally.
    if vehicle_id:
        direct.extend([
            _keys.position_key(vehicle_id),
            _keys.occupancy_key(vehicle_id),
            _keys.metadata_key(vehicle_id),
        ])

    assignments: list[str] = []
    if vehicle_id:
        assignments.append(_keys.current_run_key(vehicle_id))
    if operator_id:
        assignments.append(f"operator:{operator_id}:current_run")
    if trip_id:
        assignments.append(f"trip:{trip_id}:current_run")

    deleted = _rdel(r, direct, dry_run) + _rdel(r, assignments, dry_run)
    removed = _rsrem(r, "runs:tracking", [run_id], dry_run)
    removed += _rsrem(r, "runs:in_progress", [run_id], dry_run)
    return {"keys": deleted, "set_removals": removed}


def purge_redis_all_runs(r: redis.Redis, dry_run: bool) -> dict[str, Any]:
    actions: list[str] = []
    keys_removed = 0
    set_removals = 0

    all_run_ids: set[str] = set()
    all_run_ids.update(r.smembers("runs:tracking"))
    all_run_ids.update(r.smembers("runs:in_progress"))
    for key in r.keys("run:*"):
        all_run_ids.add(key.split(":", 1)[1])
    for key in r.keys("runs:last_seen:*"):
        all_run_ids.add(key.split(":", 2)[2])

    for run_id in sorted(all_run_ids):
        result = _purge_redis_run(r, run_id, dry_run)
        keys_removed += result["keys"]
        set_removals += result["set_removals"]
        actions.append(f"purge run {run_id} ({result['keys']} keys)")

    # Sweep stragglers
    for pattern in (
        "vehicle:*:current_run",
        "operator:*:current_run",
        "trip:*:current_run",
        "runs:last_seen:*",
        "run:*",
    ):
        for key in r.keys(pattern):
            n = _rdel(r, [key], dry_run)
            if n:
                keys_removed += n
                actions.append(f"del stray {key}")

    for set_key in ("runs:tracking", "runs:in_progress"):
        if r.exists(set_key):
            members = list(r.smembers(set_key))
            if members:
                if not dry_run:
                    r.delete(set_key)
                set_removals += len(members)
                actions.append(f"del {set_key} ({len(members)} members)")

    return {"keys_removed": keys_removed, "set_removals": set_removals, "actions": actions}


def purge_redis_one_run(r: redis.Redis, run_id: str, dry_run: bool) -> dict[str, Any]:
    result = _purge_redis_run(r, run_id, dry_run)
    return {
        "keys_removed": result["keys"],
        "set_removals": result["set_removals"],
        "actions": [f"purge run {run_id}"],
    }


def purge_redis_vehicle(r: redis.Redis, vehicle_id: str, dry_run: bool) -> dict[str, Any]:
    """Free the Redis assignment for one vehicle and cascade-purge its run."""
    current_run_key = f"vehicle:{vehicle_id}:current_run"
    run_id = r.get(current_run_key)
    if run_id:
        return purge_redis_one_run(r, run_id, dry_run)
    n = _rdel(r, [current_run_key], dry_run)
    return {"keys_removed": n, "set_removals": 0, "actions": [f"del {current_run_key}"]}


# ---------------------------------------------------------------------------
# DB cleanup modes
# ---------------------------------------------------------------------------

# All tables that reference runs_run and must be cleared before it.
# Django's on_delete=CASCADE is ORM-level only — no DB-level CASCADE exists.
_RUN_CHILD_TABLES = (
    "runs_runlifecycletransition",
    "runs_runprogressevent",
    "runs_run_vehicle",
    "runs_run_operator",
)


def db_purge_all_runs(conn, include_telemetry: bool, dry_run: bool) -> dict[str, Any]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        if include_telemetry:
            for table in ("runs_position", "runs_progression", "runs_occupancy"):
                counts[table] = _delete(cur, table, dry_run=dry_run)
        for child in _RUN_CHILD_TABLES:
            _delete(cur, child, dry_run=dry_run)
        counts["runs_run"] = _delete(cur, "runs_run", dry_run=dry_run)
    if not dry_run:
        conn.commit()
    return counts


def db_purge_one_run(conn, run_id: str, include_telemetry: bool, dry_run: bool) -> dict[str, Any]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        if include_telemetry:
            cur.execute(
                "SELECT vehicle_id FROM runs_run_vehicle WHERE run_id = %s", (run_id,)
            )
            vehicle_ids = [row[0] for row in cur.fetchall()]
            if vehicle_ids:
                fmt = ",".join(["%s"] * len(vehicle_ids))
                for table in ("runs_position", "runs_progression", "runs_occupancy"):
                    counts[table] = _delete(
                        cur, table, f"vehicle_id IN ({fmt})", tuple(vehicle_ids), dry_run
                    )
        for child in _RUN_CHILD_TABLES:
            _delete(cur, child, "run_id = %s", (run_id,), dry_run)
        counts["runs_run"] = _delete(cur, "runs_run", "id = %s", (run_id,), dry_run)
    if not dry_run:
        conn.commit()
    return counts


def db_purge_vehicle_runs(conn, vehicle_id: str, include_telemetry: bool, dry_run: bool) -> dict[str, Any]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        if include_telemetry:
            for table in ("runs_position", "runs_progression", "runs_occupancy"):
                counts[table] = _delete(
                    cur, table, "vehicle_id = %s", (vehicle_id,), dry_run
                )
        # Collect run IDs for this vehicle before touching M2M tables
        cur.execute("SELECT run_id FROM runs_run_vehicle WHERE vehicle_id = %s", (vehicle_id,))
        run_ids = [row[0] for row in cur.fetchall()]
        if run_ids:
            fmt = ",".join(["%s"] * len(run_ids))
            for child in _RUN_CHILD_TABLES:
                _delete(cur, child, f"run_id IN ({fmt})", tuple(run_ids), dry_run)
            counts["runs_run"] = _delete(
                cur, "runs_run", f"id IN ({fmt})", tuple(run_ids), dry_run
            )
        else:
            counts["runs_run"] = 0
    if not dry_run:
        conn.commit()
    return counts


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_db_section(counts: dict[str, int], dry_run: bool) -> None:
    verb = "would delete" if dry_run else "deleted"
    total = sum(counts.values())
    if total == 0:
        print("  DB: nothing to delete.\n")
        return
    print(f"  DB: {verb} {total} row(s):")
    for table, n in counts.items():
        if n:
            print(f"    • {table}: {n}")
    print()


def _print_redis_section(result: dict[str, Any], dry_run: bool) -> None:
    verb = "would remove" if dry_run else "removed"
    actions = result.get("actions", [])
    if not actions:
        print("  Redis: nothing to clean.\n")
        return
    print(
        f"  Redis: {verb} {result['keys_removed']} key(s), "
        f"{result['set_removals']} set membership(s):"
    )
    for line in actions:
        print(f"    • {line}")
    print()


def print_report(
    db_counts: dict[str, int] | None,
    redis_result: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    label = "DRY RUN" if dry_run else "EXECUTED"
    print(f"\n{SEP}\n{label}\n{SEP}\n")
    if db_counts is not None:
        _print_db_section(db_counts, dry_run)
    if redis_result is not None:
        _print_redis_section(redis_result, dry_run)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean run state from PostgreSQL and Redis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script lives in backend/scripts/ and runs inside the container:

  EXEC="docker compose exec backend python scripts/cleanup_runs.py"

Common recipes:

  # See what would be cleaned (touch nothing)
  $EXEC --dry-run

  # Full reset: wipe all runs from DB + Redis
  $EXEC --yes

  # Also wipe position/occupancy telemetry rows (progression is decommissioned)
  $EXEC --yes --telemetry

  # Clear one specific run
  $EXEC --run <uuid>

  # Clear all runs for one vehicle
  $EXEC --vehicle <vehicle_id>

  # DB only (leave Redis alone)
  $EXEC --yes --db-only

  # Redis only (leave DB alone)
  $EXEC --redis-only
""",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", metavar="RUN_ID", help="Delete one run by ID")
    mode.add_argument("--vehicle", metavar="VEHICLE_ID", help="Delete all runs for a vehicle")
    mode.add_argument("--db-only", action="store_true", help="Only clean PostgreSQL")
    mode.add_argument("--redis-only", action="store_true", help="Only clean Redis")

    parser.add_argument(
        "--telemetry",
        action="store_true",
        help="Also delete runs_position / runs_occupancy rows (runs_progression is decommissioned)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only; touch nothing")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    # Connection overrides — CLI > env var > localhost default
    parser.add_argument("--db-host",    default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--db-port",    default=int(os.getenv("DB_PORT", "5432")), type=int)
    parser.add_argument("--db-name",    default=os.getenv("DB_NAME", "databus"))
    parser.add_argument("--db-user",    default=os.getenv("DB_USER", "postgres"))
    parser.add_argument("--db-pass",    default=os.getenv("DB_PASSWORD", "postgres"))
    parser.add_argument("--redis-host", default=os.getenv("REDIS_HOST", "localhost"))
    parser.add_argument("--redis-port", default=int(os.getenv("REDIS_PORT", "6379")), type=int)
    parser.add_argument("--redis-db",   default=int(os.getenv("REDIS_DB", "0")), type=int)

    args = parser.parse_args()

    # --- Connect ---
    conn = None
    r = None

    need_db = not args.redis_only
    need_redis = not args.db_only

    if need_db:
        try:
            conn = get_db(args.db_host, args.db_port, args.db_name, args.db_user, args.db_pass)
        except Exception as e:
            print(f"\n⚠️  Cannot connect to PostgreSQL at {args.db_host}:{args.db_port}/{args.db_name}")
            print(f"Error: {e}")
            print(f"\nTip: if running on the host, pass --db-host localhost\n")
            sys.exit(1)

    if need_redis:
        try:
            r = get_redis(args.redis_host, args.redis_port, args.redis_db)
            r.ping()
        except Exception as e:
            print(f"\n⚠️  Cannot connect to Redis at {args.redis_host}:{args.redis_port}")
            print(f"Error: {e}")
            print(f"\nTip: if running on the host, pass --redis-host localhost\n")
            sys.exit(1)

    # --- Confirmation ---
    is_bulk = not args.run and not args.vehicle
    if is_bulk and not args.dry_run and not args.yes:
        scope = "DB + Redis" if (need_db and need_redis) else ("DB" if need_db else "Redis")
        print(f"\n⚠️  This will delete ALL run state from {scope}.")
        confirm = input("    Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.\n")
            sys.exit(0)

    print(f"\nRun Cleanup @ DB={args.db_host}:{args.db_port}/{args.db_name}  Redis={args.redis_host}:{args.redis_port}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Dry run: {args.dry_run}")
    print()

    # --- Dispatch ---
    db_counts: dict[str, int] | None = None
    redis_result: dict[str, Any] | None = None

    if need_db:
        if args.run:
            db_counts = db_purge_one_run(conn, args.run, args.telemetry, args.dry_run)
        elif args.vehicle:
            db_counts = db_purge_vehicle_runs(conn, args.vehicle, args.telemetry, args.dry_run)
        else:
            db_counts = db_purge_all_runs(conn, args.telemetry, args.dry_run)

    if need_redis:
        if args.run:
            redis_result = purge_redis_one_run(r, args.run, args.dry_run)
        elif args.vehicle:
            redis_result = purge_redis_vehicle(r, args.vehicle, args.dry_run)
        else:
            redis_result = purge_redis_all_runs(r, args.dry_run)

    if conn:
        conn.close()

    print_report(db_counts, redis_result, args.dry_run)


if __name__ == "__main__":
    main()
