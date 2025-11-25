#!/bin/bash

# Run Django migrations

set -e

echo "Running database migrations..."
python manage.py migrate

echo "Migrations completed successfully!"
