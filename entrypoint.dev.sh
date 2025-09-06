#!/bin/sh
set -e

# Optional: show environment summary (useful for debugging)
echo "Starting entrypoint..."
echo "DB_HOST=${DB_HOST:-unset} DB_PORT=${DB_PORT:-unset} DB_NAME=${DB_NAME:-unset} DB_USER=${DB_USER:-unset}"

# Run database migrations
echo "Applying migrations..."
python manage.py migrate --noinput

# Load existing fixtures (feed + auth) if they exist
echo "Loading fixtures (feed, auth)..."
FEED_FIX=feed/fixtures/feed.json
AUTH_FIX=website/fixtures/auth.json

LOAD_ARGS=""
[ -f "$FEED_FIX" ] && LOAD_ARGS="$LOAD_ARGS $FEED_FIX" || echo "Fixture not found: $FEED_FIX (skipping)"
[ -f "$AUTH_FIX" ] && LOAD_ARGS="$LOAD_ARGS $AUTH_FIX" || echo "Fixture not found: $AUTH_FIX (skipping)"

if [ -n "$LOAD_ARGS" ]; then
	# shellcheck disable=SC2086
	python manage.py loaddata $LOAD_ARGS
else
	echo "No fixtures to load."
fi

# Create superuser if not exists (specific to development)
echo "Creating superuser if not exists..."
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"

echo "Launching: $@"
exec "$@"
