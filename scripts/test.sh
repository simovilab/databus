#!/bin/bash

# Run Django tests

set -e

echo "Running tests..."
python3 manage.py test

echo "Tests completed!"
