#!/bin/bash

# Create Django superuser

set -e

echo "Creating Django superuser..."
python manage.py createsuperuser

echo "Superuser created successfully!"
