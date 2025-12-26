#!/bin/sh
set -e

echo "Starting application..."
echo "PORT: ${PORT:-8000}"

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput
echo "Migrations complete."

# Collect static files (allow failure)
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "Static files collection failed, continuing..."
echo "Static files collection complete."

# Start Gunicorn
echo "Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --error-logfile -

