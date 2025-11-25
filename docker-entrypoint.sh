#!/bin/bash
set -euo pipefail

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
        export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD:-}${DB_PASSWORD:+@}${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        warn "DATABASE_URL not set; constructed: ${DATABASE_URL}"
    else
        warn "DATABASE_URL not set and insufficient components to construct it."
    fi
fi

if [ "$IS_CELERY" = true ]; then
    log "Starting Celery service..."
    
    # Wait for database to be ready (Celery needs DB for django-celery-beat)
    log "Waiting for database connection..."
    until python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
    warn "Database is unavailable - sleeping"
        sleep 2
    done
    
        log "Database is ready!"

        # Optionally run migrations for beat/worker to ensure django_celery_beat tables exist
        if [[ "${MIGRATE_ON_CELERY:-1}" == "1" || "${MIGRATE_ON_CELERY:-true}" == "true" ]]; then
            log "Applying pending migrations (Celery service)..."
            python manage.py migrate --noinput || warn "Celery migration step failed (continuing)"
        else
            log "Skipping migrations in Celery service (MIGRATE_ON_CELERY=${MIGRATE_ON_CELERY})"
        fi

        log "Starting Celery process..."
else
    log "Starting Django application..."
    
    # Wait for database to be ready
    log "Waiting for database connection..."
    until python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
    warn "Database is unavailable - sleeping"
        sleep 2
    done

    log "Database is ready!"

    # List of apps to make migrations for
    #APPS_TO_MIGRATE=("website" "gtfs" "feed" "alerts" "api")
    APPS_TO_MIGRATE=("website" "gtfs" "feed" "api")

    # Make migrations for the registered apps
    log "Making migrations for apps: ${APPS_TO_MIGRATE[*]}"
    python manage.py makemigrations "${APPS_TO_MIGRATE[@]}" || warn "No changes detected for migrations"

    # Run database migrations
    log "Running database migrations..."
    python manage.py migrate --noinput

    # Create superuser if it doesn't exist
        if [[ "${DEBUG:-}" == "True" || "${DEBUG:-}" == "1" ]]; then
            log "Ensuring development superuser 'admin' exists (DEBUG mode)"
            python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model();\nimport os;\nusername=os.environ.get('DJANGO_SUPERUSER_USERNAME','admin');\npassword=os.environ.get('DJANGO_SUPERUSER_PASSWORD','admin');\nemail=os.environ.get('DJANGO_SUPERUSER_EMAIL','admin@example.com');\nU.objects.filter(username=username).exists() or (U.objects.create_superuser(username, email, password) and print(f'Superuser created: {username}/{password}')) or print('Superuser already exists')" || warn "Superuser creation skipped"
        else
            log "DEBUG not true; skipping automatic superuser creation"
        fi

    # Collect static files
    log "Collecting static files..."
    python manage.py collectstatic --noinput || warn "Static files collection skipped"

    # Load initial data (if needed)
        if [ -f bucr.json ]; then
            log "Loading initial data fixture bucr.json"
            python manage.py loaddata bucr.json || warn "Initial data load failed"
        else
            log "No optional initial data fixture bucr.json present"
        fi

    log "Django application setup complete!"
fi

# Execute the main command
log "Launching: $*"
exec "$@"