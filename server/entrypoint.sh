#!/bin/sh

# Database tables and migrations are handled by the server at startup.
echo "Starting Kondooit server..."
exec uvicorn kondooit.app:app --host 0.0.0.0 --port 8000
