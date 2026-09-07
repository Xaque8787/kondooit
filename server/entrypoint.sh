#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head || {
    echo "Initial alembic upgrade failed — stamping current head and retrying..."
    alembic stamp head
}

echo "Starting Kondooit server..."
exec uvicorn kondooit.app:app --host 0.0.0.0 --port 8000
