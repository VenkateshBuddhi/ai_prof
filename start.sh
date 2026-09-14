#!/bin/bash
set -e

echo "Starting LiveKit Voice Worker in background..."
python -m src.voice.livekit_worker start &

echo "Starting FastAPI backend server on port ${PORT:-8000}..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
