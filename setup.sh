#!/bin/bash
# ==============================================================================
# Local Mind - Universal Setup Script
# ==============================================================================
#
# One-command setup for macOS and Linux
#
# Usage:
#   ./setup.sh           # Full setup
#   ./setup.sh --check   # Only check prerequisites
#   ./setup.sh --dev     # Development mode with extra tools
#
# This script:
#   1. Detects OS and architecture (macOS/Linux, Intel/ARM)
#   2. Checks all prerequisites (Python, Docker, Node.js, RAM)
#   3. Generates secure .env configuration if not present
#   4. Creates Python virtual environment
#   5. Installs all dependencies
#   6. Starts infrastructure services (Milvus, Redis)
#   7. Verifies everything is working
#
# ==============================================================================

set -e

# ==============================================================================
# Configuration
# ==============================================================================

SCRIPT_VERSION="1.0.0"
MIN_PYTHON_VERSION="3.11"
MIN_NODE_VERSION="18"
MIN_RAM_GB=8
RECOMMENDED_RAM_GB=16

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Directory setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/apps/backend"
FRONTEND_DIR="$PROJECT_ROOT/apps/frontend"
DATA_DIR="$PROJECT_ROOT/data"
LOGS_DIR="$PROJECT_ROOT/logs"
VENV_DIR="$PROJECT_ROOT/venv"

# ==============================================================================
# Helper Functions
# ==============================================================================

print_banner() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║              🧠 LOCAL MIND - Universal Setup                   ║${NC}"
    echo -e "${CYAN}║                   Version ${SCRIPT_VERSION}                               ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  📋 $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
log_error()   { echo -e "${RED}[✗]${NC} $1"; }
log_step()    { echo -e "${CYAN}[→]${NC} $1"; }

# Compare version strings (returns 0 if $1 >= $2)
version_gte() {
    [ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Generate secure random string
generate_secret() {
    local length=${1:-32}
    if command -v openssl &> /dev/null; then
        openssl rand -base64 "$length" | tr -dc 'a-zA-Z0-9' | head -c "$length"
    else
        cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c "$length"
    fi
}

# ==============================================================================
# System Detection
# ==============================================================================

detect_system() {
    print_header "System Detection"
    
    # Detect OS
    OS_TYPE="unknown"
    case "$(uname -s)" in
        Darwin*)  OS_TYPE="macos" ;;
        Linux*)   OS_TYPE="linux" ;;
        *)        OS_TYPE="unsupported" ;;
    esac
    
    # Detect Architecture
    ARCH_TYPE="unknown"
    case "$(uname -m)" in
        x86_64|amd64) ARCH_TYPE="x64" ;;
        arm64|aarch64) ARCH_TYPE="arm64" ;;
        *)            ARCH_TYPE="unsupported" ;;
    esac
    
    # Detect Linux distro
    DISTRO="unknown"
    if [ "$OS_TYPE" = "linux" ]; then
        if [ -f /etc/os-release ]; then
            DISTRO=$(grep ^ID= /etc/os-release | cut -d= -f2 | tr -d '"')
        fi
    fi
    
    # Detect available RAM
    RAM_GB=0
    if [ "$OS_TYPE" = "macos" ]; then
        RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
        RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
    elif [ "$OS_TYPE" = "linux" ]; then
        RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
        RAM_GB=$((RAM_KB / 1024 / 1024))
    fi
    
    # Report detection
    log_success "Operating System: $OS_TYPE"
    log_success "Architecture: $ARCH_TYPE"
    [ "$DISTRO" != "unknown" ] && log_success "Distribution: $DISTRO"
    log_success "Available RAM: ${RAM_GB}GB"
    
    # Check RAM
    if [ "$RAM_GB" -lt "$MIN_RAM_GB" ]; then
        log_warn "RAM (${RAM_GB}GB) is below minimum (${MIN_RAM_GB}GB). Performance may be limited."
    elif [ "$RAM_GB" -lt "$RECOMMENDED_RAM_GB" ]; then
        log_info "RAM (${RAM_GB}GB) is adequate. Recommended: ${RECOMMENDED_RAM_GB}GB for best performance."
    else
        log_success "RAM (${RAM_GB}GB) is excellent!"
    fi
    
    # Check if system is supported
    if [ "$OS_TYPE" = "unsupported" ] || [ "$ARCH_TYPE" = "unsupported" ]; then
        log_error "Unsupported system configuration: $OS_TYPE / $ARCH_TYPE"
        log_error "Local Mind supports macOS (Intel/Apple Silicon) and Linux (x64/ARM64)"
        exit 1
    fi
    
    # Detect GPU
    GPU_TYPE="none"
    if [ "$OS_TYPE" = "macos" ]; then
        if [ "$ARCH_TYPE" = "arm64" ]; then
            GPU_TYPE="mps"
            log_success "Apple Silicon GPU (MPS) detected"
        fi
    elif [ "$OS_TYPE" = "linux" ]; then
        if command -v nvidia-smi &> /dev/null; then
            GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
            if [ -n "$GPU_INFO" ]; then
                GPU_TYPE="cuda"
                log_success "NVIDIA GPU detected: $GPU_INFO"
            fi
        fi
    fi
    
    if [ "$GPU_TYPE" = "none" ]; then
        log_info "No GPU detected. LLM will run on CPU (slower but functional)."
    fi
    
    export OS_TYPE ARCH_TYPE DISTRO RAM_GB GPU_TYPE
}

# ==============================================================================
# Prerequisites Check
# ==============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local all_passed=true
    
    # Check Python
    log_step "Checking Python..."
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if version_gte "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            log_success "Python $PYTHON_VERSION (>= $MIN_PYTHON_VERSION required)"
        else
            log_error "Python $PYTHON_VERSION is too old. Need >= $MIN_PYTHON_VERSION"
            all_passed=false
        fi
    else
        log_error "Python 3 not found. Install Python $MIN_PYTHON_VERSION or later."
        all_passed=false
    fi
    
    # Check pip
    if command -v pip3 &> /dev/null; then
        log_success "pip3 available"
    else
        log_warn "pip3 not found, will use python -m pip"
    fi
    
    # Check Node.js
    log_step "Checking Node.js..."
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version | sed 's/v//')
        NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
        if [ "$NODE_MAJOR" -ge "$MIN_NODE_VERSION" ]; then
            log_success "Node.js $NODE_VERSION (>= $MIN_NODE_VERSION required)"
        else
            log_error "Node.js $NODE_VERSION is too old. Need >= $MIN_NODE_VERSION"
            all_passed=false
        fi
    else
        log_error "Node.js not found. Install Node.js $MIN_NODE_VERSION or later."
        log_info "Install via: https://nodejs.org/ or 'brew install node' (macOS)"
        all_passed=false
    fi
    
    # Check npm
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        log_success "npm $NPM_VERSION"
    else
        log_error "npm not found. Should be installed with Node.js"
        all_passed=false
    fi
    
    # Check container runtime (Docker or alternatives)
    log_step "Checking container runtime..."
    CONTAINER_CMD=""
    COMPOSE_CMD=""
    
    if command -v docker &> /dev/null; then
        CONTAINER_CMD="docker"
        if docker compose version &> /dev/null 2>&1; then
            COMPOSE_CMD="docker compose"
            DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            log_success "Docker $DOCKER_VERSION with compose plugin"
        elif command -v docker-compose &> /dev/null; then
            COMPOSE_CMD="docker-compose"
            log_success "Docker with docker-compose"
        else
            log_warn "Docker found but no compose. Install docker-compose-plugin."
            all_passed=false
        fi
    elif command -v podman &> /dev/null; then
        CONTAINER_CMD="podman"
        if command -v podman-compose &> /dev/null; then
            COMPOSE_CMD="podman-compose"
            log_success "Podman with podman-compose"
        elif podman compose version &> /dev/null 2>&1; then
            COMPOSE_CMD="podman compose"
            log_success "Podman with compose"
        else
            log_warn "Podman found but no compose available"
            all_passed=false
        fi
    elif command -v nerdctl &> /dev/null; then
        CONTAINER_CMD="nerdctl"
        COMPOSE_CMD="nerdctl compose"
        log_success "nerdctl"
    else
        log_error "No container runtime found (Docker, Podman, or nerdctl)"
        log_info "Install Docker Desktop: https://docker.com/products/docker-desktop"
        all_passed=false
    fi
    
    export CONTAINER_CMD COMPOSE_CMD
    
    # Check if Docker daemon is running
    if [ -n "$CONTAINER_CMD" ]; then
        if $CONTAINER_CMD info &> /dev/null; then
            log_success "Container daemon is running"
        else
            log_error "Container daemon is not running. Start Docker/Podman first."
            all_passed=false
        fi
    fi
    
    # Check git
    log_step "Checking git..."
    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_success "git $GIT_VERSION"
    else
        log_warn "git not found. Some features may not work."
    fi
    
    # Check curl
    log_step "Checking curl..."
    if command -v curl &> /dev/null; then
        log_success "curl available"
    else
        log_warn "curl not found. Installing..."
        if [ "$OS_TYPE" = "linux" ]; then
            sudo apt-get install -y curl || sudo yum install -y curl
        fi
    fi
    
    # Summary
    echo ""
    if $all_passed; then
        log_success "All prerequisites passed!"
    else
        log_error "Some prerequisites failed. Please fix the issues above."
        exit 1
    fi
}

# ==============================================================================
# Environment Configuration
# ==============================================================================

setup_environment() {
    print_header "Environment Configuration"
    
    # Create .env if it doesn't exist
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_step "Creating .env with secure defaults..."
        
        # Generate secure passwords
        NEO4J_PWD=$(generate_secret 24)
        MINIO_SECRET=$(generate_secret 24)
        SECRET_KEY=$(generate_secret 32)
        
        cat > "$PROJECT_ROOT/.env" << EOF
# ==============================================================================
# Local Mind - Environment Configuration
# ==============================================================================
# Auto-generated by setup.sh on $(date)
# ==============================================================================

# Core Application
APP_NAME=LocalMind
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# ==============================================================================
# Neo4j - Knowledge Graph Database
# ==============================================================================
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=${NEO4J_PWD}

# ==============================================================================
# Milvus - Vector Database
# ==============================================================================
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=document_chunks

# Embedding settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# MinIO (Milvus storage)
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=${MINIO_SECRET}

# ==============================================================================
# Redis - Task Queue & Cache
# ==============================================================================
REDIS_URL=redis://localhost:6379/0

# ==============================================================================
# LLM Configuration (Ollama recommended for local)
# ==============================================================================
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_BASE_URL=http://localhost:11434
LLM_API_KEY=EMPTY

# ==============================================================================
# Document Processing
# ==============================================================================
CHUNK_SIZE_TOKENS=500
CHUNK_OVERLAP_TOKENS=50
UPLOAD_DIR=./data/uploads

# ==============================================================================
# Security
# ==============================================================================
SECRET_KEY=${SECRET_KEY}
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# ==============================================================================
# Storage Paths
# ==============================================================================
DATA_DIR=./data
UPLOADS_DIR=./data/uploads
CACHE_DIR=./data/cache
EOF

        chmod 600 "$PROJECT_ROOT/.env"
        log_success ".env created with secure random passwords"
    else
        log_success ".env already exists"
    fi
    
    # Also create infrastructure .env
    INFRA_DIR="$PROJECT_ROOT/infrastructure/nerdctl"
    if [ -d "$INFRA_DIR" ] && [ ! -f "$INFRA_DIR/.env" ]; then
        log_step "Creating infrastructure .env..."
        cp "$PROJECT_ROOT/.env" "$INFRA_DIR/.env"
        log_success "Infrastructure .env created"
    fi
    
    # Create data directories
    log_step "Creating data directories..."
    mkdir -p "$DATA_DIR"/{uploads,cache,milvus/etcd,milvus/minio,neo4j/data,neo4j/logs,redis,models}
    mkdir -p "$LOGS_DIR"
    log_success "Data directories created"
}

# ==============================================================================
# Python Environment Setup
# ==============================================================================

setup_python_env() {
    print_header "Python Environment Setup"
    
    # Create virtual environment
    if [ -d "$VENV_DIR" ]; then
        log_info "Virtual environment already exists at $VENV_DIR"
    else
        log_step "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    fi
    
    # Activate virtual environment
    log_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    log_success "Virtual environment activated"
    
    # Upgrade pip
    log_step "Upgrading pip..."
    pip install --upgrade pip > /dev/null 2>&1
    log_success "pip upgraded"
    
    # Install backend dependencies
    log_step "Installing backend dependencies..."
    if [ -f "$BACKEND_DIR/requirements.txt" ]; then
        pip install -r "$BACKEND_DIR/requirements.txt"
        log_success "Backend dependencies installed"
    else
        log_error "Backend requirements.txt not found!"
        exit 1
    fi
    
    # Install test dependencies (optional)
    if [ -f "$PROJECT_ROOT/tests/requirements-test.txt" ]; then
        log_step "Installing test dependencies..."
        pip install -r "$PROJECT_ROOT/tests/requirements-test.txt" 2>/dev/null || true
        log_success "Test dependencies installed"
    fi
}

# ==============================================================================
# Frontend Setup
# ==============================================================================

setup_frontend() {
    print_header "Frontend Setup"
    
    if [ ! -d "$FRONTEND_DIR" ]; then
        log_error "Frontend directory not found: $FRONTEND_DIR"
        return 1
    fi
    
    cd "$FRONTEND_DIR"
    
    # Install Node.js dependencies
    if [ -f "package.json" ]; then
        log_step "Installing frontend dependencies..."
        npm install 2>/dev/null
        log_success "Frontend dependencies installed"
    else
        log_error "package.json not found in frontend"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
}

# ==============================================================================
# Infrastructure Setup
# ==============================================================================

start_infrastructure() {
    print_header "Starting Infrastructure"
    
    if [ -z "$COMPOSE_CMD" ]; then
        log_error "No compose command available"
        exit 1
    fi
    
    COMPOSE_FILE="$PROJECT_ROOT/infrastructure/nerdctl/compose.yaml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    log_step "Starting Milvus, Redis, and supporting services..."
    cd "$PROJECT_ROOT/infrastructure/nerdctl"
    
    # Pull images
    $COMPOSE_CMD pull 2>/dev/null || true
    
    # Start services
    $COMPOSE_CMD up -d
    
    cd "$PROJECT_ROOT"
    
    log_success "Infrastructure containers started"
    
    # Wait for services to be healthy
    log_step "Waiting for services to be healthy..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        # Check Milvus
        if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
            log_success "Milvus is ready"
            break
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_warn "Milvus may still be starting. Check logs with: docker logs sce-memory-bank"
    fi
    
    # Check Redis
    attempt=1
    while [ $attempt -le 15 ]; do
        if $CONTAINER_CMD exec sce-broker redis-cli ping 2>/dev/null | grep -q PONG; then
            log_success "Redis is ready"
            break
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
}

# ==============================================================================
# Verification
# ==============================================================================

verify_setup() {
    print_header "Verifying Setup"
    
    local all_ok=true
    
    # Check Python environment
    log_step "Checking Python environment..."
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        if python -c "import fastapi; import pymilvus" 2>/dev/null; then
            log_success "Python packages verified"
        else
            log_error "Some Python packages missing"
            all_ok=false
        fi
    else
        log_error "Virtual environment not found"
        all_ok=false
    fi
    
    # Check frontend
    log_step "Checking frontend..."
    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        log_success "Frontend node_modules present"
    else
        log_warn "Frontend node_modules not installed"
    fi
    
    # Check infrastructure
    log_step "Checking infrastructure services..."
    
    # Milvus
    if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
        log_success "Milvus: healthy"
    else
        log_warn "Milvus: not responding (may still be starting)"
    fi
    
    # Redis
    if $CONTAINER_CMD exec sce-broker redis-cli ping 2>/dev/null | grep -q PONG; then
        log_success "Redis: healthy"
    else
        log_warn "Redis: not responding"
    fi
    
    # Summary
    echo ""
    if $all_ok; then
        log_success "All verifications passed!"
    else
        log_warn "Some checks failed but setup may still work."
    fi
}

# ==============================================================================
# Print Next Steps
# ==============================================================================

print_success_message() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  🎉 Setup Complete!                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}To start Local Mind:${NC}"
    echo ""
    echo -e "  ${BOLD}./start.sh${NC}         # Start backend and frontend"
    echo ""
    echo -e "${CYAN}Or start services individually:${NC}"
    echo ""
    echo -e "  ${BOLD}source venv/bin/activate${NC}"
    echo -e "  ${BOLD}cd apps/backend && uvicorn main:app --reload${NC}"
    echo ""
    echo -e "  ${BOLD}cd apps/frontend && npm run dev${NC}"
    echo ""
    echo -e "${CYAN}Access:${NC}"
    echo ""
    echo -e "  🌐 Frontend:  ${GREEN}http://localhost:3000${NC}"
    echo -e "  🔌 API:       ${GREEN}http://localhost:8000${NC}"
    echo -e "  📚 API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${CYAN}For LLM support (optional):${NC}"
    echo ""
    echo -e "  1. Install Ollama: ${GREEN}https://ollama.ai${NC}"
    echo -e "  2. Run: ${BOLD}ollama pull llama3.2${NC}"
    echo -e "  3. Start: ${BOLD}ollama serve${NC}"
    echo ""
    echo -e "${CYAN}Documentation:${NC}"
    echo ""
    echo -e "  📖 Quick Start:   ${GREEN}QUICKSTART.md${NC}"
    echo -e "  📖 User Guide:    ${GREEN}USER_GUIDE.md${NC}"
    echo -e "  🔧 Troubleshoot:  ${GREEN}docs/TROUBLESHOOTING.md${NC}"
    echo ""
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    print_banner
    
    # Parse arguments
    CHECK_ONLY=false
    DEV_MODE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                CHECK_ONLY=true
                shift
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  --check    Only check prerequisites"
                echo "  --dev      Development mode with extra tools"
                echo "  --help     Show this help"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run setup steps
    detect_system
    check_prerequisites
    
    if $CHECK_ONLY; then
        log_success "Prerequisites check complete!"
        exit 0
    fi
    
    setup_environment
    setup_python_env
    setup_frontend
    start_infrastructure
    verify_setup
    print_success_message
}

# Run main
main "$@"
