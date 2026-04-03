# backend/Dockerfile
FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered stdout for Docker logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required by mysqlclient and argon2-cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files (no-input for non-interactive)
# Runs at build time; comment out until STATIC_ROOT is configured in settings
# RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Default: run Gunicorn (overridden in docker-compose for worker/beat services)
# Worker count: 2x CPU + 1 (adjust via GUNICORN_WORKERS env var)
CMD ["sh", "-c", "python manage.py migrate --noinput && \
     python manage.py seed_users && \
     gunicorn config.wsgi:application \
       --bind 0.0.0.0:8000 \
       --workers ${GUNICORN_WORKERS:-4} \
       --timeout 120 \
       --access-logfile - \
       --error-logfile -"]
