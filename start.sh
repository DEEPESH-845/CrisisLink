#!/bin/bash
# CrisisLink — start all four backend microservices
set -e

echo "Starting CrisisLink Backend Services..."
echo ""

cd "$(dirname "$0")/backend"

# Export .env variables into the shell so child processes inherit them
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

echo "Starting services (each on its own port)..."
echo ""

uvicorn speech_ingestion.app:app --host 0.0.0.0 --port 8001 --reload &
PID_SPEECH=$!

uvicorn intelligence.app:app --host 0.0.0.0 --port 8002 --reload &
PID_INTEL=$!

uvicorn dispatch.app:app --host 0.0.0.0 --port 8003 --reload &
PID_DISPATCH=$!

uvicorn tts.app:app --host 0.0.0.0 --port 8004 --reload &
PID_TTS=$!

echo "All services running:"
echo "  Speech Ingestion: http://localhost:8001  (docs: http://localhost:8001/docs)"
echo "  Intelligence:     http://localhost:8002  (docs: http://localhost:8002/docs)"
echo "  Dispatch:         http://localhost:8003  (docs: http://localhost:8003/docs)"
echo "  TTS:              http://localhost:8004  (docs: http://localhost:8004/docs)"
echo ""
echo "Press Ctrl+C to stop all services."

# Stop all background services on exit
trap 'echo ""; echo "Stopping services..."; kill $PID_SPEECH $PID_INTEL $PID_DISPATCH $PID_TTS 2>/dev/null; wait' EXIT INT TERM

wait
