#!/bin/bash
# ==============================================================================
# Local Mind - macOS Startup Script
# ==============================================================================
# Usage: ./start.sh [backend|frontend|infrastructure|all|stop]
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/apps/backend"
FRONTEND_DIR="$PROJECT_ROOT/apps/frontend"
LOGS_DIR="$PROJECT_ROOT/logs"
COMPOSE_FILE="$PROJECT_ROOT/infrastructure/nerdctl/compose.yaml"
NAMESPACE="sovereign-ai"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# ==============================================================================
# Helper Functions
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

check_port() {
    local port=$1
    if lsof -i ":$port" >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

kill_port() {
    local port=$1
    local pids=$(lsof -ti ":$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null
        log_info "Killed process(es) on port $port"
    fi
}

wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "docker command not found!"
        exit 1
    fi
}

# ==============================================================================
# Service Management
# ==============================================================================

start_infrastructure() {
    log_info "Starting Infrastructure (Milvus, Redis)..."
    check_docker
    
    # Check if .env exists for compose
    if [ ! -f "$(dirname "$COMPOSE_FILE")/.env" ]; then
        if [ -f "$(dirname "$COMPOSE_FILE")/.env.example" ]; then
             log_warn "Creating .env from example..."
             cp "$(dirname "$COMPOSE_FILE")/.env.example" "$(dirname "$COMPOSE_FILE")/.env"
        fi
    fi

    docker compose -f "$COMPOSE_FILE" -p "$NAMESPACE" up -d
    
    log_info "Waiting for infrastructure to assert readiness..."
    # A simple sleep for now, could be improved with health checks
    sleep 5 
    log_success "Infrastructure containers started."
}

stop_infrastructure() {
    log_info "Stopping Infrastructure..."
    check_docker
    docker compose -f "$COMPOSE_FILE" -p "$NAMESPACE" down
    log_success "Infrastructure stopped."
}

start_backend() {
    log_info "Starting Backend (FastAPI + Uvicorn)..."
    
    if check_port 8000; then
        log_warn "Port 8000 already in use. Killing existing process..."
        kill_port 8000
        sleep 1
    fi
    
    # Use root-level venv
    if [ ! -d "$PROJECT_ROOT/venv" ]; then
        log_error "Python venv not found! Run: ./setup_env.sh"
        exit 1
    fi
    
    source "$PROJECT_ROOT/venv/bin/activate"
    
    cd "$BACKEND_DIR"
    
    # Start in background, log to file
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
        > "$LOGS_DIR/backend.log" 2>&1 &
    
    BACKEND_PID=$!
    echo $BACKEND_PID > "$LOGS_DIR/backend.pid"
    
    log_info "Waiting for backend to be ready..."
    if wait_for_service "http://127.0.0.1:8000/health" "backend"; then
        log_success "Backend running at http://localhost:8000 (PID: $BACKEND_PID)"
    else
        log_error "Backend failed to start. Check $LOGS_DIR/backend.log"
        exit 1
    fi
}

start_frontend() {
    log_info "Starting Frontend (Next.js 15)..."
    
    if check_port 3000; then
        log_warn "Port 3000 already in use. Killing existing process..."
        kill_port 3000
        sleep 1
    fi
    
    cd "$FRONTEND_DIR"
    
    if [ ! -d "node_modules" ]; then
        log_warn "node_modules not found. Installing dependencies..."
        npm install
    fi
    
    # macOS Sonoma requires polling for file watchers
    export WATCHPACK_POLLING=true
    export CHOKIDAR_USEPOLLING=1
    
    # Start in background, log to file
    nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
    
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$LOGS_DIR/frontend.pid"
    
    log_info "Waiting for frontend to be ready..."
    if wait_for_service "http://127.0.0.1:3000" "frontend"; then
        log_success "Frontend running at http://localhost:3000 (PID: $FRONTEND_PID)"
    else
        log_error "Frontend failed to start. Check $LOGS_DIR/frontend.log"
        exit 1
    fi
}

stop_services() {
    log_info "Stopping all services..."
    
    stop_infrastructure

    if [ -f "$LOGS_DIR/backend.pid" ]; then
        kill -9 $(cat "$LOGS_DIR/backend.pid") 2>/dev/null && log_success "Backend stopped"
        rm -f "$LOGS_DIR/backend.pid"
    fi
    
    if [ -f "$LOGS_DIR/frontend.pid" ]; then
        kill -9 $(cat "$LOGS_DIR/frontend.pid") 2>/dev/null && log_success "Frontend stopped"
        rm -f "$LOGS_DIR/frontend.pid"
    fi
    
    # Also kill any remaining processes on the ports
    kill_port 8000
    kill_port 3000
    
    log_success "All services stopped"
}

show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    LOCAL MIND STATUS                       ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Docker Infrastructure Status
    echo -e "${BLUE}--- Infrastructure (Docker) ---${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "sce-" || echo "No 'sce-' containers running"
    echo ""

    # Backend status
    echo -e "${BLUE}--- Backend (Port 8000) ---${NC}"
    if check_port 8000; then
        local health=$(curl -s http://127.0.0.1:8000/health 2>/dev/null)
        if [ -n "$health" ]; then
            log_success "Backend is responding (200 OK)"
            log_info "API Docs: http://localhost:8000/docs"
        else
            log_warn "Port 8000 occupied but NOT responding"
        fi
    else
        log_error "Not running"
    fi
    echo ""
    
    # Frontend status
    echo -e "${BLUE}--- Frontend (Port 3000) ---${NC}"
    if check_port 3000; then
        if curl -s http://127.0.0.1:3000 >/dev/null 2>&1; then
            log_success "Frontend is responding (200 OK)"
        else
            log_warn "Port 3000 occupied but NOT responding"
        fi
    else
        log_error "Not running"
    fi
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

show_help() {
    echo ""
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  all            Start EVERYTHING (Infrastructure + Backend + Frontend) [Default]"
    echo "  infrastructure Start only Docker containers (Milvus, Redis)"
    echo "  backend        Start only the backend"
    echo "  frontend       Start only the frontend"
    echo "  stop           Stop ALL services"
    echo "  status         Show status of all services"
    echo "  logs           Tail logs from both backend and frontend"
    echo "  help           Show this help message"
    echo ""
}

show_logs() {
    log_info "Tailing logs (Ctrl+C to exit)..."
    tail -f "$LOGS_DIR/backend.log" "$LOGS_DIR/frontend.log"
}

# ==============================================================================
# Main
# ==============================================================================

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🧠 LOCAL MIND - macOS Launcher               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

case "${1:-all}" in
    infrastructure)
        start_infrastructure
        show_status
        ;;
    backend)
        start_backend
        show_status
        ;;
    frontend)
        start_frontend
        show_status
        ;;
    all)
        start_infrastructure
        start_backend
        start_frontend
        show_status
        log_success "All services started! Open http://localhost:3000"
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
