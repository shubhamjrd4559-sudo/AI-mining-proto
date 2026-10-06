#!/usr/bin/env bash
# build.sh — Render build script
# Executed inside the backend/ directory before gunicorn starts.
# Render sets DJANGO_SETTINGS_MODULE automatically via envVars.

set -o errexit

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static files..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Build complete."
