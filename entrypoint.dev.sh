#!/bin/sh
set -e

# Optional: show environment summary (useful for debugging)
echo "Starting entrypoint..."
echo "DB_HOST=${DB_HOST:-unset} DB_PORT=${DB_PORT:-unset} DB_NAME=${DB_NAME:-unset} DB_USER=${DB_USER:-unset}"

# Run database migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Load initial data (specific to development)
echo "Loading initial data..."
python manage.py loaddata initial_data.json

# Create superuser if not exists (specific to development)
echo "Creating superuser if not exists..."
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"

echo "Launching: $@"
exec "$@"
