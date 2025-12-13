#!/usr/bin/env bash
# ============================================================
# Sovereign Cognitive Engine - Initialization Script
# ============================================================
# This script bootstraps the SCE stack using nerdctl/containerd.
# 
# Prerequisites:
#   - nerdctl (containerd CLI)
#   - nvidia-container-toolkit (for GPU passthrough)
#   - WSL2 with CUDA support (on Windows)
#
# Usage:
#   chmod +x init.sh
#   ./init.sh
# ============================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="sovereign-ai"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
COMPOSE_DIR="$PROJECT_ROOT/infrastructure/nerdctl"

# ============================================================
# Helper Functions
# ============================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

# ============================================================
# Prerequisite Checks
# ============================================================

echo ""
echo "=============================================="
echo "  Sovereign Cognitive Engine - Initializer"
echo "=============================================="
echo ""

log_info "Checking prerequisites..."

# Check nerdctl
if ! check_command nerdctl; then
    log_error "nerdctl is not installed!"
    echo ""
    echo "Install nerdctl:"
    echo "  - Linux: https://github.com/containerd/nerdctl/releases"
    echo "  - WSL2: Install via package manager or download binary"
    echo ""
    exit 1
fi
log_success "nerdctl found: $(nerdctl --version)"

# Check nvidia-container-toolkit
if ! check_command nvidia-container-runtime && ! check_command nvidia-ctk; then
    log_warn "nvidia-container-toolkit may not be installed!"
    echo ""
    echo "GPU passthrough requires nvidia-container-toolkit."
    echo "Install it from: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    echo ""
    read -p "Continue without GPU support? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    log_warn "Continuing without verified GPU support..."
else
    log_success "nvidia-container-toolkit found"
fi

# Check for NVIDIA GPU
if check_command nvidia-smi; then
    log_info "Detected NVIDIA GPU:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
else
    log_warn "nvidia-smi not found - GPU features may not work"
fi

# ============================================================
# Create Namespace
# ============================================================

echo ""
log_info "Setting up namespace: $NAMESPACE"

# Check if namespace exists
if nerdctl namespace ls | grep -q "$NAMESPACE"; then
    log_info "Namespace '$NAMESPACE' already exists"
else
    nerdctl namespace create "$NAMESPACE"
    log_success "Created namespace: $NAMESPACE"
fi

# ============================================================
# Create Data Directories
# ============================================================

log_info "Creating data directories..."

DATA_DIRS=(
    "$PROJECT_ROOT/data/neo4j"
    "$PROJECT_ROOT/data/neo4j/logs"
    "$PROJECT_ROOT/data/neo4j/import"
    "$PROJECT_ROOT/data/milvus"
    "$PROJECT_ROOT/data/milvus/etcd"
    "$PROJECT_ROOT/data/milvus/minio"
    "$PROJECT_ROOT/data/redis"
    "$PROJECT_ROOT/data/models"
)

for dir in "${DATA_DIRS[@]}"; do
    mkdir -p "$dir"
    # Set permissive permissions to avoid container UID mismatch issues
    # Container processes may run as different UIDs (e.g., neo4j:7474, minio:1000)
    chmod 777 "$dir"
done
log_success "Data directories created with container-accessible permissions"

# ============================================================
# Start the Stack
# ============================================================

echo ""
log_info "Starting Sovereign Cognitive Engine stack..."

cd "$COMPOSE_DIR"

# Validate .env file exists
if [[ ! -f "$COMPOSE_DIR/.env" ]]; then
    log_error ".env file not found!"
    echo ""
    echo "Setup instructions:"
    echo "  1. Copy the template:  cp $COMPOSE_DIR/.env.example $COMPOSE_DIR/.env"
    echo "  2. Edit .env and set required secrets (NEO4J_PASSWORD, MINIO_SECRET_KEY)"
    echo "  3. Secure the file:    chmod 600 $COMPOSE_DIR/.env"
    echo ""
    exit 1
fi
log_success ".env file found"

# Pull images first
log_info "Pulling container images (this may take a while)..."
nerdctl --namespace "$NAMESPACE" compose pull || true

# Build custom images
log_info "Building custom service images..."
nerdctl --namespace "$NAMESPACE" compose build

# Start in detached mode
log_info "Starting services..."
nerdctl --namespace "$NAMESPACE" compose up -d

# ============================================================
# Health Check
# ============================================================

echo ""
log_info "Waiting for services to become healthy..."
sleep 10

echo ""
log_info "Service Status:"
nerdctl --namespace "$NAMESPACE" compose ps

# ============================================================
# Summary
# ============================================================

echo ""
echo "=============================================="
echo -e "${GREEN}  Sovereign Cognitive Engine is starting!${NC}"
echo "=============================================="
echo ""
echo "Services:"
echo "  - Interface (UI):     http://localhost:3000"
echo "  - API (Internal):     http://orchestrator:8000"
echo "  - Neo4j Browser:      http://localhost:7474 (if exposed)"
echo ""
echo "Useful commands:"
echo "  View logs:    nerdctl --namespace $NAMESPACE compose logs -f"
echo "  Stop stack:   nerdctl --namespace $NAMESPACE compose down"
echo "  Restart:      nerdctl --namespace $NAMESPACE compose restart"
echo ""
log_success "Initialization complete!"
