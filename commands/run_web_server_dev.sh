#!/bin/bash
set -e

echo "🚀 Starting FastAPI development server..."

export PYTHONPATH=/usr/src/src

exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir /usr/src/src
