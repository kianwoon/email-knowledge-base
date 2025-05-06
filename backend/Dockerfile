# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV CELERY_BROKER_URL="redis://redis-queue.email-knowledge-base-2.internal:6379/0"
ENV CELERY_RESULT_BACKEND="redis://redis-queue.email-knowledge-base-2.internal:6379/0"

# Set work directory
WORKDIR /app

# Install dependencies and build tools, install python packages, then clean up
COPY backend/requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the backend application code specifically
COPY backend/ /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the Uvicorn server
# Assumes your main FastAPI app instance is named 'app' in 'app/main.py'
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
