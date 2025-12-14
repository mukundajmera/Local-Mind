#!/bin/bash
# ==============================================================================
# Local Mind - Backend Startup Script
# ==============================================================================
# Runs the FastAPI backend with uvicorn on port 8000
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../apps/backend"

cd "$BACKEND_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run setup first."
    echo "   python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Load environment variables
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
fi

echo "🚀 Starting Local Mind Backend on http://0.0.0.0:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
