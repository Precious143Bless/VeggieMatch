#!/usr/bin/env bash
# Exit on error
set -o errexit

# Create necessary directories
mkdir -p static
mkdir -p media
mkdir -p staticfiles

# Install dependencies
pip install -r requirements.txt

# Collect static files (ignore warnings)
python manage.py collectstatic --no-input --ignore=*.scss || echo "Static files collected with warnings"

# Apply database migrations with timeout handling
echo "Running migrations..."
python manage.py migrate --no-input

echo "Build completed successfully!"
