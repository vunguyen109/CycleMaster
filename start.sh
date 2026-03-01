#!/bin/bash
set -e

# CycleMaster FastAPI Server - Render Deployment Script

# Ensure data directory exists
mkdir -p /data

# Run migrations and initialize database
python -m app.models.db

# Start the application with uvicorn
# PORT is automatically provided by Render
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-log
