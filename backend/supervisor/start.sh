#!/bin/bash

# Wait for Redis to be ready
echo "Waiting for Redis to be available..."
until celery -A app.celery_app inspect ping; do
  echo "Redis not available yet - waiting..."
  sleep 5
done
echo "Redis is available - starting services"

# Start supervisord
exec supervisord -c /etc/supervisor/conf.d/celery.conf 