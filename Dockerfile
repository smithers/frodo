FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files (allow failure in case static files don't exist yet)
RUN python manage.py collectstatic --noinput || true

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Run migrations and start the application
# Railway sets PORT environment variable automatically
CMD sh -c "python manage.py migrate && gunicorn core.wsgi:application --bind 0.0.0.0:\${PORT:-8000}"

