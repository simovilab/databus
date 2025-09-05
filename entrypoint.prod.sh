#!/bin/sh
set -e

# Optional: show environment summary (useful for debugging)
echo "Starting entrypoint..."
echo "DB_HOST=${DB_HOST:-unset} DB_PORT=${DB_PORT:-unset} DB_NAME=${DB_NAME:-unset} DB_USER=${DB_USER:-unset}"

# Run database migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Collect static files (safe to run for all services)
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Launching: $@"
exec "$@"
