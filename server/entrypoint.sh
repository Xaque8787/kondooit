#!/bin/sh

echo "Running database migrations..."
if alembic upgrade head; then
    echo "Migrations applied successfully."
else
    echo "Alembic migration failed — server will rely on create_all fallback."
fi

echo "Starting Kondooit server..."
exec uvicorn kondooit.app:app --host 0.0.0.0 --port 8000
