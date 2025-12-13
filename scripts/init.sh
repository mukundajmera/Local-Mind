#!/bin/bash
# ==============================================================================
# Local Mind - Stack Initialization Script
# ==============================================================================
# This script initializes and starts all Local Mind services.
#
# Usage:
#   bash scripts/init.sh
#
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🧠 $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

print_header "Local Mind - Initialization"

# ==============================================================================
# Check Prerequisites
# ==============================================================================

print_info "Checking prerequisites..."

# Check for nerdctl or docker
CONTAINER_CMD=""
COMPOSE_CMD=""

if command -v nerdctl &> /dev/null; then
    CONTAINER_CMD="nerdctl"
    COMPOSE_CMD="nerdctl compose"
    print_success "Found nerdctl"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    # Check for docker compose (plugin) vs docker-compose (standalone)
    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        print_success "Found docker with compose plugin"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        print_success "Found docker with docker-compose"
    else
        print_error "Docker found but no compose available!"
        print_info "Install with: sudo apt install docker-compose-plugin"
        print_info "Or: pip install docker-compose"
        exit 1
    fi
else
    print_error "Neither nerdctl nor docker found!"
    print_error "Please install Docker Desktop or nerdctl first. See SETUP.md"
    exit 1
fi

print_success "Compose command: $COMPOSE_CMD"

# Check for GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        print_success "GPU detected: $GPU_INFO"
    fi
else
    print_warning "nvidia-smi not found. GPU acceleration may not work."
fi

# ==============================================================================
# Environment Setup
# ==============================================================================

print_header "Environment Setup"

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        print_info "Creating .env from .env.example..."
        cp .env.example .env
        print_success ".env file created"
    else
        print_warning "No .env file found. Using defaults."
    fi
else
    print_success ".env file exists"
fi

# Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ==============================================================================
# Create Data Directories
# ==============================================================================

print_header "Creating Data Directories"

DIRS=(
    "data/neo4j/data"
    "data/neo4j/logs"
    "data/milvus"
    "data/redis"
    "data/models"
    "data/uploads"
    "data/cache"
    "logs"
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    print_success "Created $dir"
done

# ==============================================================================
# Start Services
# ==============================================================================

print_header "Starting Services"

COMPOSE_FILE="infrastructure/nerdctl/compose.yaml"

if [ ! -f "$COMPOSE_FILE" ]; then
    print_error "Compose file not found: $COMPOSE_FILE"
    print_info "Creating a basic compose configuration..."
    
    mkdir -p infrastructure/nerdctl
    
    cat > "$COMPOSE_FILE" << 'EOF'
# Local Mind - Docker Compose Configuration
# Run with: nerdctl compose -f infrastructure/nerdctl/compose.yaml up -d

version: "3.8"

services:
  # ==========================================================================
  # Databases
  # ==========================================================================
  
  neo4j:
    image: neo4j:5.15-community
    container_name: localmind-neo4j
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-localmind2024}
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - ./data/neo4j/data:/data
      - ./data/neo4j/logs:/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: localmind-redis
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # ==========================================================================
  # Backend
  # ==========================================================================
  
  backend:
    build:
      context: ../../apps/backend
      dockerfile: Dockerfile
    container_name: localmind-backend
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-localmind2024}
      - REDIS_URL=redis://redis:6379/0
      - LLM_BASE_URL=http://inference:8001/v1
      - TTS_BASE_URL=http://tts:8880
    volumes:
      - ./data/uploads:/app/uploads
    depends_on:
      - neo4j
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==========================================================================
  # Frontend
  # ==========================================================================
  
  frontend:
    build:
      context: ../../apps/frontend
      dockerfile: Dockerfile
    container_name: localmind-frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
EOF

    print_success "Created basic compose.yaml"
fi

print_info "Pulling images (this may take a while on first run)..."
$COMPOSE_CMD -f "$COMPOSE_FILE" pull 2>/dev/null || true

print_info "Starting containers..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

# ==============================================================================
# Wait for Services
# ==============================================================================

print_header "Waiting for Services"

wait_for_service() {
    local name=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            print_success "$name is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_warning "$name not responding (may still be starting)"
    return 1
}

echo -n "Waiting for Neo4j"
wait_for_service "Neo4j" "http://localhost:7474" 30

echo -n "Waiting for Backend"
wait_for_service "Backend" "http://localhost:8000/health" 30

echo -n "Waiting for Frontend"
wait_for_service "Frontend" "http://localhost:3000" 30

# ==============================================================================
# Complete
# ==============================================================================

print_header "Local Mind is Ready!"

echo -e "${GREEN}"
cat << 'EOF'

   _                     _   __  __ _           _ 
  | |    ___   ___ __ _| | |  \/  (_)_ __   __| |
  | |   / _ \ / __/ _` | | | |\/| | | '_ \ / _` |
  | |__| (_) | (_| (_| | | | |  | | | | | | (_| |
  |_____\___/ \___\__,_|_| |_|  |_|_|_| |_|\__,_|
                                                  
EOF
echo -e "${NC}"

echo -e "${CYAN}Access your Local Mind:${NC}"
echo ""
echo -e "  🌐 Frontend:     ${GREEN}http://localhost:3000${NC}"
echo -e "  🔌 API:          ${GREEN}http://localhost:8000${NC}"
echo -e "  🔍 Neo4j Browser: ${GREEN}http://localhost:7474${NC}"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo ""
echo "  View logs:     $COMPOSE_CMD -f $COMPOSE_FILE logs -f"
echo "  Stop:          $COMPOSE_CMD -f $COMPOSE_FILE down"
echo "  Restart:       $COMPOSE_CMD -f $COMPOSE_FILE restart"
echo ""

# Open browser if possible
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:3000" 2>/dev/null &
elif command -v open &> /dev/null; then
    open "http://localhost:3000" 2>/dev/null &
fi
