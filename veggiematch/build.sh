#!/usr/bin/env bash
# Exit on error
set -o errexit

# Create media directory for user uploads
mkdir -p media
mkdir -p staticfiles

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate
