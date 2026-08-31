#!/bin/sh
set -e

echo "Starting Kondooit server..."
exec uvicorn kondooit.app:app --host 0.0.0.0 --port 8000
