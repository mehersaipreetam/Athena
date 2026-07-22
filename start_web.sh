#!/bin/bash
# Athena Web Server Startup Script

set -e

echo "🟣 Starting Athena Web Server..."

# Activate virtual environment if it exists
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
    echo "✓ Virtual environment activated"
fi

# Check if uvicorn is available
if ! command -v uvicorn &> /dev/null; then
    echo "✗ uvicorn not found. Installing dependencies..."
    pip install -r requirements-lean.txt
fi

# Default settings
HOST=${ATHENA_HOST:-0.0.0.0}
PORT=${ATHENA_PORT:-8080}
WORKERS=${ATHENA_WORKERS:-1}

echo "🌐 Starting server on http://$HOST:$PORT"
echo "📱 Open this URL in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start server
exec python3 -m uvicorn web.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level info