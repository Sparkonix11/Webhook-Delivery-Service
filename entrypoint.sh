#!/bin/bash

set -x  # Enable debug mode
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
except psycopg2.OperationalError as e:
    print(f"PostgreSQL connection error: {e}", file=sys.stderr)
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
cd /app
alembic upgrade head
if [ $? -ne 0 ]; then
    echo "$(date) - Migration failed!"
    exit 1
fi
echo "$(date) - Database migrations completed!"

# Start the application
echo "$(date) - Starting the FastAPI application..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload 