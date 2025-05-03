#!/bin/bash

# Script to control Celery worker and beat scheduler
# Usage: ./celery_control.sh [start|stop|restart]

BACKEND_DIR="/Users/kianwoonwong/Downloads/knowledge_base_builder/backend"

start_celery() {
    echo "Starting Celery worker and beat scheduler..."
    cd "$BACKEND_DIR" || exit 1
    
    # Start worker in background
    python -m celery -A app.celery_app worker --pool=threads --loglevel=info > worker.log 2>&1 &
    worker_pid=$!
    echo "Worker started with PID: $worker_pid"
    
    # Start beat in background
    python -m celery -A app.celery_app beat -l info > beat.log 2>&1 &
    beat_pid=$!
    echo "Beat scheduler started with PID: $beat_pid"
    
    # Save PIDs for later use
    echo "$worker_pid" > worker.pid
    echo "$beat_pid" > beat.pid
    
    echo "Both processes started. Logs in worker.log and beat.log"
}

stop_celery() {
    echo "Stopping Celery processes..."
    
    # Kill any running Celery processes
    pkill -f "celery -A app.celery_app"
    
    # Also try to kill by saved PIDs if they exist
    if [ -f worker.pid ]; then
        worker_pid=$(cat worker.pid)
        kill "$worker_pid" 2>/dev/null
        rm worker.pid
    fi
    
    if [ -f beat.pid ]; then
        beat_pid=$(cat beat.pid)
        kill "$beat_pid" 2>/dev/null
        rm beat.pid
    fi
    
    # Flush Redis to clear any pending tasks
    docker exec redis-local redis-cli flushall
    
    echo "Celery processes stopped and Redis flushed"
}

case "$1" in
    start)
        start_celery
        ;;
    stop)
        stop_celery
        ;;
    restart)
        stop_celery
        sleep 2
        start_celery
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac

exit 0 