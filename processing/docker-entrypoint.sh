#!/bin/bash
set -euo pipefail

# Ensure virtual environment bin is on PATH if present
VENV_DIR="${UV_PROJECT_ENVIRONMENT:-/home/app/.venv}"
if [ -d "${VENV_DIR}/bin" ]; then
    export PATH="${VENV_DIR}/bin:$PATH"
fi

UV_SYNC_LOCKDIR="/tmp/uv-sync.lockdir"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log(){ echo -e "${GREEN}[entrypoint]${NC} $*"; }
warn(){ echo -e "${YELLOW}[entrypoint][warn]${NC} $*"; }
err(){ echo -e "${RED}[entrypoint][error]${NC} $*"; }

# -----------------------------------------
log "Building DATABASE_URL from components"
# -----------------------------------------

if [ -z "${DATABASE_URL:-}" ]; then
    if [[ -n "${DB_USER:-}" && -n "${DB_HOST:-}" && -n "${DB_NAME:-}" ]]; then
        if [ -n "${DB_PASSWORD:-}" ]; then
            export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        else
            export DATABASE_URL="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        fi
        warn "DATABASE_URL not set; constructed as: ${DATABASE_URL}"
    else
        warn "DATABASE_URL not set and insufficient components to construct it."
    fi
fi

# ----------------------------------
log "Starting Django application..."
# ----------------------------------

# Ensure the shared virtual environment exists (install if not present).
# Multiple containers share /home/app/.venv via a Docker volume, so we
# serialize uv sync with a lock directory to avoid concurrent installs.
setup_virtualenv() {
    if [ -d "${VENV_DIR}/bin" ]; then
        log "Virtual environment already exists"
        return
    fi

    warn "Virtual environment not found; waiting for setup lock"
    while ! mkdir "${UV_SYNC_LOCKDIR}" 2>/dev/null; do
        if [ -d "${VENV_DIR}/bin" ]; then
            log "Virtual environment became available"
            return
        fi
        sleep 1
    done

    cleanup_lock() {
        rmdir "${UV_SYNC_LOCKDIR}" 2>/dev/null || true
    }
    trap cleanup_lock EXIT

    # Another container may have finished setup while we acquired the lock.
    if [ -d "${VENV_DIR}/bin" ]; then
        log "Virtual environment already exists"
        cleanup_lock
        trap - EXIT
        return
    fi

    warn "Setting up virtual environment (uv sync)..."
    attempts=0
    until uv sync --frozen; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 3 ]; then
            err "uv sync failed after ${attempts} attempts"
            exit 1
        fi
        warn "uv sync failed (attempt ${attempts}/3); cleaning partial env and retrying"
        rm -rf "${VENV_DIR}" || true
        sleep 2
    done

    log "Virtual environment ready"
    cleanup_lock
    trap - EXIT
}

setup_virtualenv

if [ -d "${VENV_DIR}/bin" ]; then
    export PATH="${VENV_DIR}/bin:$PATH"
fi

# --------------------------------------
log "Waiting for database connection..."
# --------------------------------------

until uv run python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
warn "Database is unavailable - sleeping"
    sleep 5
done
log "Database is ready!"

# -------------------------------------
log "Making migrations (if enabled)..."
# -------------------------------------

if [[ "${RUN_MIGRATIONS:-False}" == "True" ]]; then
    # Make migrations
    APPS_TO_MIGRATE=("gtfs" "tasks")
    log "Creating migrations for: ${APPS_TO_MIGRATE[*]}"
    uv run python manage.py makemigrations "${APPS_TO_MIGRATE[@]}" || warn "No changes detected for migrations"

    # Run database migrations
    log "Running database migrations..."
    uv run python manage.py migrate --noinput
else
    log "Skipping migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS:-False})"
fi

# --------------------------------------------------------
log "Creating superuser (if enabled and in debug mode)..."
# --------------------------------------------------------

if [[ "${CREATE_SUPERUSER:-False}" == "True" && ( "${DEBUG:-}" == "True" || "${DEBUG:-}" == "1" ) ]]; then
    export DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
    export DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-admin}"
    export DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
    log "Ensuring development superuser '${DJANGO_SUPERUSER_USERNAME}' exists (DEBUG mode)"
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

# ------------------------------
log "Collecting static files..."
# ------------------------------

uv run python manage.py collectstatic --noinput || warn "Static files collection skipped"

# ----------------------------------------
log "Loading initial data (if present)..."
# ----------------------------------------

if [[ "${LOAD_FIXTURES:-False}" == "True" ]]; then
    if [ -f gtfs/fixtures/gtfs.json ]; then
        log "Loading initial data fixture gtfs.json"
        uv run python manage.py loaddata gtfs.json || warn "Initial data load failed"
    else
        log "No optional initial data fixture gtfs.json present"
    fi
else
    log "Skipping fixture loading (LOAD_FIXTURES=${LOAD_FIXTURES:-False})"
fi

# --------------------------------------
log "Django application setup complete!"
# --------------------------------------

# Execute the main command
log "Launching: $*"
exec "$@"
