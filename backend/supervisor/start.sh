#!/bin/bash

# Ensure log directories exist and have proper permissions
mkdir -p /app/logs/supervisor /app/logs/celery
touch /app/logs/supervisor/supervisord.log
touch /app/logs/celery/worker.log /app/logs/celery/worker_error.log
touch /app/logs/celery/beat.log /app/logs/celery/beat_error.log

# Wait for Redis to be ready
echo "Waiting for Redis to be available..."
until celery -A app.celery_app -b $CELERY_BROKER_URL inspect ping; do
  echo "Redis not available yet - waiting..."
  sleep 5
done
echo "Redis is available - starting services"

# Start supervisord
exec supervisord -c /etc/supervisor/conf.d/celery.conf 