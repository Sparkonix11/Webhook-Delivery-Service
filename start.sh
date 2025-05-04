#!/bin/bash

echo "Starting initialization process..."

# Function to test if postgres is ready
postgres_ready() {
    python << END
import sys
import psycopg2
try:
    psycopg2.connect(
        dbname="${POSTGRES_DB}",
        user="${POSTGRES_USER}",
        password="${POSTGRES_PASSWORD}",
        host="${POSTGRES_SERVER}"
    )
except psycopg2.OperationalError:
    sys.exit(-1)
sys.exit(0)
END
}

echo "Checking PostgreSQL connection..."
# Wait for PostgreSQL to be ready
until postgres_ready; do
  echo "$(date) - Waiting for PostgreSQL to be ready..."
  sleep 2
done
echo "$(date) - PostgreSQL is ready!"

# Run migrations
echo "$(date) - Running database migrations..."
alembic upgrade head
echo "$(date) - Database migrations completed!"

# Start the application
echo "$(date) - Starting the FastAPI application..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload 