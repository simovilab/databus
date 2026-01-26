#!/bin/bash
set -euo pipefail

# Ensure virtualenv bin is on PATH if present
if [ -d "/app/.venv/bin" ]; then
    export PATH="/app/.venv/bin:$PATH"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log(){ echo -e "${GREEN}[entrypoint]${NC} $*"; }
warn(){ echo -e "${YELLOW}[entrypoint][warn]${NC} $*"; }
err(){ echo -e "${RED}[entrypoint][error]${NC} $*"; }

# Detect if this is a Celery service based on the command arguments
IS_CELERY=false
if [[ "${*:-}" == *"celery"* ]]; then
        IS_CELERY=true
fi

# Build DATABASE_URL if missing (fallback)
if [ -z "${DATABASE_URL:-}" ]; then
    if [[ -n "${DB_USER:-}" && -n "${DB_HOST:-}" && -n "${DB_NAME:-}" ]]; then
        if [ -n "${DB_PASSWORD:-}" ]; then
            export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        else
            export DATABASE_URL="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        fi
        warn "DATABASE_URL not set; constructed: ${DATABASE_URL}"
    else
        warn "DATABASE_URL not set and insufficient components to construct it."
    fi
fi

if [ "$IS_CELERY" = true ]; then
    log "Starting Celery service..."
    
    # Ensure virtual environment exists (install if not present)
    if [ ! -d "/app/.venv" ]; then
    warn "Setting up virtual environment (uv sync)..."
        uv sync --frozen
    else
    log "Virtual environment already exists"
    fi
    
    # Wait for database to be ready (Celery needs DB for django-celery-beat)
    log "Waiting for database connection..."
    until uv run python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
    warn "Database is unavailable - sleeping"
        sleep 2
    done
    
        log "Database is ready!"

        # Optionally run migrations for beat/worker to ensure django_celery_beat tables exist
        # Default DISABLED to prevent concurrent migrations from multiple services
        if [[ "${MIGRATE_ON_CELERY:-0}" == "1" || "${MIGRATE_ON_CELERY:-false}" == "true" ]]; then
            log "Applying pending migrations (Celery service)..."
            uv run python manage.py migrate --noinput || warn "Celery migration step failed (continuing)"
        else
            log "Skipping migrations in Celery service (MIGRATE_ON_CELERY=${MIGRATE_ON_CELERY})"
        fi

        # If this is the beat process, ensure beat tables are present before starting
        if [[ "${*:-}" == *" beat "* || "${*:-}" == *" beat" || "${*:-}" == *"beat "* ]]; then
            log "Ensuring django_celery_beat tables exist before starting beat..."
            until uv run python - <<'PY'
import os, psycopg2
dsn=os.environ['DATABASE_URL']
with psycopg2.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.django_celery_beat_periodictask') IS NOT NULL;")
        ok = cur.fetchone()[0]
import sys
print("OK" if ok else "WAIT")
sys.exit(0 if ok else 1)
PY
            do
                warn "django_celery_beat tables not ready - waiting"
                sleep 2
            done
            log "django_celery_beat tables ready."
        fi

        log "Starting Celery process..."
else
    log "Starting Django application..."

    # Ensure virtual environment exists (install if not present)
    if [ ! -d "/app/.venv" ]; then
    warn "Setting up virtual environment (uv sync)..."
        uv sync --frozen
    else
    log "Virtual environment already exists"
    fi
    
    # Wait for database to be ready
    log "Waiting for database connection..."
    until uv run python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
    warn "Database is unavailable - sleeping"
        sleep 2
    done

    log "Database is ready!"

    # Make migrations
    APPS_TO_MIGRATE=("website" "gtfs" "feed" "api")
    log "RUN_MAKEMIGRATIONS enabled. Creating migrations for: ${APPS_TO_MIGRATE[*]}"
    uv run python manage.py makemigrations "${APPS_TO_MIGRATE[@]}" || warn "No changes detected for migrations"

    # Run database migrations
    log "Running database migrations..."
    uv run python manage.py migrate --noinput

    # Create superuser if it doesn't exist using defaults in development mode
    if [[ "${CREATE_SUPERUSER:-1}" == "1" && ( "${DEBUG:-}" == "True" || "${DEBUG:-}" == "1" ) ]]; then
        # Provide defaults if not set for development
        export DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
        export DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-admin}"
        export DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
        log "Ensuring development superuser '${DJANGO_SUPERUSER_USERNAME}' exists (DEBUG mode)"
        # Run createsuperuser non-interactively, it will fail if user exists but the error is handled
        set +e
        uv run python manage.py createsuperuser --noinput
        csu_exit=$?
        set -e
        if [ $csu_exit -eq 0 ]; then
            log "Superuser created: ${DJANGO_SUPERUSER_USERNAME}/${DJANGO_SUPERUSER_PASSWORD}"
        else
            warn "Superuser creation skipped (maybe already exists)"
        fi
    else
        log "Skipping auto superuser creation (CREATE_SUPERUSER=${CREATE_SUPERUSER:-0} DEBUG=${DEBUG:-})"
    fi

    # Collect static files
    log "Collecting static files..."
    uv run python manage.py collectstatic --noinput || warn "Static files collection skipped"

    # Load initial data (if needed) -> This should probably be looked at, there is no data when the container starts
        if [ -f gtfs.json ]; then
            log "Loading initial data fixture gtfs.json"
            uv run python manage.py loaddata gtfs.json || warn "Initial data load failed"
        else
            log "No optional initial data fixture gtfs.json present"
        fi

    log "Django application setup complete!"
fi

# Execute the main command
log "Launching: $*"
exec "$@"