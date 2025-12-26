#!/bin/bash
set -x  # Enable debug mode to see all commands

# Force output to be unbuffered
export PYTHONUNBUFFERED=1

echo "=== STARTING APPLICATION ==="
echo "PORT variable: ${PORT}"
echo "Working directory: $(pwd)"
echo "Python path: $(which python)"

# Check if migrations are needed (Railway might run them separately)
echo "=== Checking database connection ==="
python manage.py check --database default || echo "Database check failed, continuing..."

# Run migrations (idempotent, safe to run multiple times)
echo "=== Running migrations ==="
python manage.py migrate --noinput || {
    echo "=== Migration failed, but continuing ==="
}

echo "=== Migrations step complete ==="

# Collect static files
echo "=== Collecting static files ==="
python manage.py collectstatic --noinput || {
    echo "=== Static files collection failed, continuing ==="
}

echo "=== Starting Gunicorn ==="
echo "Command: gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}"

# Start Gunicorn - use exec to replace shell process
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output

