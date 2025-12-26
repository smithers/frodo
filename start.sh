#!/bin/sh
set -e

# Force output to be unbuffered
export PYTHONUNBUFFERED=1

echo "=== Starting application ===" >&2
echo "PORT: ${PORT:-8000}" >&2

# Run migrations
echo "=== Running migrations ===" >&2
python manage.py migrate --noinput
echo "=== Migrations complete ===" >&2

# Skip collectstatic for now (WhiteNoise will serve from STATICFILES_DIRS if needed)
# Uncomment the line below if you want to collect static files
# python manage.py collectstatic --noinput || true
echo "=== Skipping static files collection (using WhiteNoise) ===" >&2

# Start Gunicorn
echo "=== Starting Gunicorn on port ${PORT:-8000} ===" >&2
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --error-logfile - --log-level info

