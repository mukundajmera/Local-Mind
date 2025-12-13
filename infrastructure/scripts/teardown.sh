#!/usr/bin/env bash
# ============================================================
# Sovereign Cognitive Engine - Teardown Script
# ============================================================
# Cleanly stops and removes the SCE stack.
#
# Usage:
#   ./teardown.sh          # Stop services, keep data
#   ./teardown.sh --purge  # Stop services AND delete data
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="sovereign-ai"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
COMPOSE_DIR="$PROJECT_ROOT/infrastructure/nerdctl"

PURGE=false

# Parse arguments
if [[ "${1:-}" == "--purge" ]]; then
    PURGE=true
fi

echo ""
echo "=============================================="
echo "  Sovereign Cognitive Engine - Teardown"
echo "=============================================="
echo ""

# Stop compose stack
echo -e "${BLUE}[INFO]${NC} Stopping services..."
cd "$COMPOSE_DIR"
nerdctl --namespace "$NAMESPACE" compose down --remove-orphans || true

echo -e "${GREEN}[SUCCESS]${NC} Services stopped"

# Purge data if requested
if [ "$PURGE" = true ]; then
    echo ""
    echo -e "${YELLOW}[WARN]${NC} Purge mode enabled - this will delete ALL data!"
    read -p "Are you sure? (type 'yes' to confirm): " -r
    echo ""
    
    if [[ "$REPLY" == "yes" ]]; then
        echo -e "${BLUE}[INFO]${NC} Removing data directories..."
        rm -rf "$PROJECT_ROOT/data/neo4j"
        rm -rf "$PROJECT_ROOT/data/milvus"
        rm -rf "$PROJECT_ROOT/data/redis"
        rm -rf "$PROJECT_ROOT/data/models"
        
        echo -e "${BLUE}[INFO]${NC} Removing volumes..."
        nerdctl --namespace "$NAMESPACE" volume prune -f || true
        
        echo -e "${GREEN}[SUCCESS]${NC} All data purged"
    else
        echo -e "${BLUE}[INFO]${NC} Purge cancelled"
    fi
fi

echo ""
echo -e "${GREEN}[SUCCESS]${NC} Teardown complete!"
