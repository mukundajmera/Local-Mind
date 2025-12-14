#!/bin/bash
# ==============================================================================
# Local Mind - Frontend Startup Script
# ==============================================================================
# Runs the Next.js frontend on port 3000
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../apps/frontend"

cd "$FRONTEND_DIR"

# Check for node_modules
if [ ! -d "node_modules" ]; then
    echo "❌ Dependencies not installed. Running npm install..."
    npm install
fi

# Load environment variables
if [ -f "$SCRIPT_DIR/../.env" ]; then
    set -a
    source "$SCRIPT_DIR/../.env"
    set +a
fi

echo "🚀 Starting Local Mind Frontend on http://localhost:3000"
echo ""

exec npm run dev
