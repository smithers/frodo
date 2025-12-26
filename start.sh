#!/bin/sh
set -e

# Run migrations
python manage.py migrate --noinput

# Collect static files (allow failure)
python manage.py collectstatic --noinput || true

# Start Gunicorn
# Railway sets PORT automatically, default to 8000 if not set
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120

