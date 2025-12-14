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

export WATCHPACK_POLLING="${WATCHPACK_POLLING:-true}"
export WATCHPACK_POLLING_INTERVAL="${WATCHPACK_POLLING_INTERVAL:-1000}"

echo "🚀 Starting Local Mind Frontend on http://localhost:3000"
echo "📡 WATCHPACK_POLLING=$WATCHPACK_POLLING (interval ${WATCHPACK_POLLING_INTERVAL}ms)"
echo ""

exec npm run dev
