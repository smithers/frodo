#!/bin/bash
# This script is kept for compatibility but Heroku uses Procfile release phase
# For Heroku, migrations and collectstatic run in the release phase
# This script can be used for local development or other platforms

set -x
export PYTHONUNBUFFERED=1

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

# Create or reset superuser (only if env vars are set)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "=== Creating/updating superuser ==="
    python manage.py reset_superuser_password || {
        echo "=== Superuser creation/update failed, continuing ==="
    }
fi

echo "=== Starting Gunicorn ==="
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -

