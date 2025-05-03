#!/bin/bash

# Ensure log directories exist and have proper permissions
mkdir -p /app/logs/supervisor /app/logs/celery
touch /app/logs/supervisor/supervisord.log
touch /app/logs/celery/worker.log /app/logs/celery/worker_error.log
touch /app/logs/celery/beat.log /app/logs/celery/beat_error.log

# Wait for Redis to be ready using redis-cli ping
echo "Waiting for Redis to be available..."

if [ -z "$CELERY_BROKER_URL" ]; then
  echo "Error: CELERY_BROKER_URL environment variable is not set." >&2
  exit 1
fi

# Parse host and port from CELERY_BROKER_URL (redis://host:port/db)
# Remove prefix
TEMP_URL=${CELERY_BROKER_URL#redis://}
# Extract host
REDIS_HOST=${TEMP_URL%%:*} 
# Extract port (handle case with or without db number)
TEMP_PORT_DB=${TEMP_URL#*:}
REDIS_PORT=${TEMP_PORT_DB%%/*}

if [ -z "$REDIS_HOST" ] || [ -z "$REDIS_PORT" ]; then
  echo "Error: Could not parse REDIS_HOST or REDIS_PORT from CELERY_BROKER_URL: $CELERY_BROKER_URL" >&2
  exit 1
fi

echo "Attempting to ping Redis at $REDIS_HOST:$REDIS_PORT..."

# Loop until redis-cli ping returns PONG
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; do
  echo "Redis ping failed or did not return PONG - waiting..."
  sleep 3 # Shortened sleep time slightly
done

echo "Redis is available (PONG received) - starting services"

# Start supervisord
exec supervisord -c /etc/supervisor/conf.d/celery.conf 