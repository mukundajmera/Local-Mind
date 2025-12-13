#!/bin/bash
# =============================================================================
# Sovereign Cognitive Engine - Self-Healing Watchdog
# =============================================================================
# Monitors container health and automatically restarts failed services.
#
# Usage:
#   ./scripts/watchdog.sh              # Run in foreground
#   ./scripts/watchdog.sh &            # Run in background
#   nohup ./scripts/watchdog.sh &      # Run as daemon
#
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Endpoints to monitor
readonly BACKEND_HEALTH_URL="http://localhost:8000/health"
readonly INFERENCE_HEALTH_URL="http://localhost:8001/health"  # vLLM health
readonly TTS_HEALTH_URL="http://localhost:8880/health"        # Kokoro health

# Timing (seconds)
readonly CHECK_INTERVAL=10
readonly FAILURE_THRESHOLD=6  # 6 failures * 10s = 1 minute before restart

# Container names (as defined in compose.yaml)
readonly BACKEND_CONTAINER="orchestrator"
readonly INFERENCE_CONTAINER="inference-engine"
readonly TTS_CONTAINER="tts-engine"

# Logging
readonly LOG_DIR="$(dirname "$0")/../logs"
readonly LOG_FILE="${LOG_DIR}/system_events.log"
readonly PID_FILE="/tmp/sce-watchdog.pid"

# Colors for terminal output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# =============================================================================
# Initialization
# =============================================================================

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    old_pid=$(cat "$PID_FILE")
    if kill -0 "$old_pid" 2>/dev/null; then
        echo -e "${YELLOW}Watchdog already running (PID: $old_pid)${NC}"
        exit 1
    fi
fi

# Save our PID
echo $$ > "$PID_FILE"

# Cleanup on exit
cleanup() {
    rm -f "$PID_FILE"
    log_event "INFO" "Watchdog stopped"
    exit 0
}
trap cleanup EXIT INT TERM

# =============================================================================
# Logging Functions
# =============================================================================

log_event() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log to file
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    # Log to console with colors
    case "$level" in
        "ERROR")   echo -e "${RED}[$timestamp] [$level] $message${NC}" ;;
        "WARNING") echo -e "${YELLOW}[$timestamp] [$level] $message${NC}" ;;
        "INFO")    echo -e "${GREEN}[$timestamp] [$level] $message${NC}" ;;
        *)         echo "[$timestamp] [$level] $message" ;;
    esac
}

# =============================================================================
# Health Check Functions
# =============================================================================

check_endpoint() {
    local url="$1"
    local timeout="${2:-5}"
    
    if curl -sf --max-time "$timeout" "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

get_container_status() {
    local container="$1"
    
    # Try nerdctl first, then docker
    if command -v nerdctl &> /dev/null; then
        nerdctl inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown"
    elif command -v docker &> /dev/null; then
        docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

restart_container() {
    local container="$1"
    
    log_event "WARNING" "Restarting container: $container"
    
    if command -v nerdctl &> /dev/null; then
        nerdctl restart "$container" 2>&1 | while read -r line; do
            log_event "INFO" "nerdctl: $line"
        done
    elif command -v docker &> /dev/null; then
        docker restart "$container" 2>&1 | while read -r line; do
            log_event "INFO" "docker: $line"
        done
    else
        log_event "ERROR" "Neither nerdctl nor docker found!"
        return 1
    fi
    
    log_event "INFO" "Container $container restart initiated"
}

# =============================================================================
# GPU Monitoring
# =============================================================================

check_gpu_health() {
    if ! command -v nvidia-smi &> /dev/null; then
        return 0  # No GPU, skip check
    fi
    
    # Check for GPU errors
    local gpu_status
    gpu_status=$(nvidia-smi --query-gpu=ecc.errors.uncorrected.volatile --format=csv,noheader,nounits 2>/dev/null || echo "0")
    
    if [ "$gpu_status" != "0" ] && [ -n "$gpu_status" ]; then
        log_event "WARNING" "GPU ECC errors detected: $gpu_status"
        return 1
    fi
    
    # Check temperature
    local temp
    temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
    
    if [ -n "$temp" ] && [ "$temp" -gt 85 ]; then
        log_event "WARNING" "GPU temperature high: ${temp}°C"
    fi
    
    return 0
}

# =============================================================================
# Memory Monitoring
# =============================================================================

check_memory() {
    if command -v free &> /dev/null; then
        local mem_available
        mem_available=$(free -m | awk '/^Mem:/ {print $7}')
        
        if [ -n "$mem_available" ] && [ "$mem_available" -lt 1024 ]; then
            log_event "WARNING" "Low system memory: ${mem_available}MB available"
            return 1
        fi
    fi
    return 0
}

# =============================================================================
# Main Monitoring Loop
# =============================================================================

# Failure counters
declare -A failure_counts
failure_counts["$BACKEND_CONTAINER"]=0
failure_counts["$INFERENCE_CONTAINER"]=0
failure_counts["$TTS_CONTAINER"]=0

log_event "INFO" "Watchdog started (PID: $$)"
log_event "INFO" "Check interval: ${CHECK_INTERVAL}s, Failure threshold: ${FAILURE_THRESHOLD}"

while true; do
    # --- Check Backend (Orchestrator) ---
    if check_endpoint "$BACKEND_HEALTH_URL"; then
        failure_counts["$BACKEND_CONTAINER"]=0
    else
        ((failure_counts["$BACKEND_CONTAINER"]++)) || true
        log_event "WARNING" "Backend health check failed (${failure_counts[$BACKEND_CONTAINER]}/${FAILURE_THRESHOLD})"
        
        if [ "${failure_counts[$BACKEND_CONTAINER]}" -ge "$FAILURE_THRESHOLD" ]; then
            log_event "ERROR" "Backend failed for 1+ minutes, initiating restart"
            restart_container "$BACKEND_CONTAINER"
            failure_counts["$BACKEND_CONTAINER"]=0
            sleep 30  # Wait for container to come up
        fi
    fi
    
    # --- Check Inference Engine (vLLM) ---
    if check_endpoint "$INFERENCE_HEALTH_URL" 10; then
        failure_counts["$INFERENCE_CONTAINER"]=0
    else
        ((failure_counts["$INFERENCE_CONTAINER"]++)) || true
        log_event "WARNING" "Inference engine health check failed (${failure_counts[$INFERENCE_CONTAINER]}/${FAILURE_THRESHOLD})"
        
        if [ "${failure_counts[$INFERENCE_CONTAINER]}" -ge "$FAILURE_THRESHOLD" ]; then
            log_event "ERROR" "Inference engine failed for 1+ minutes, initiating restart"
            restart_container "$INFERENCE_CONTAINER"
            failure_counts["$INFERENCE_CONTAINER"]=0
            sleep 60  # vLLM takes longer to start
        fi
    fi
    
    # --- Check TTS Engine (Kokoro) ---
    if check_endpoint "$TTS_HEALTH_URL" 5; then
        failure_counts["$TTS_CONTAINER"]=0
    else
        ((failure_counts["$TTS_CONTAINER"]++)) || true
        log_event "WARNING" "TTS engine health check failed (${failure_counts[$TTS_CONTAINER]}/${FAILURE_THRESHOLD})"
        
        if [ "${failure_counts[$TTS_CONTAINER]}" -ge "$FAILURE_THRESHOLD" ]; then
            log_event "ERROR" "TTS engine failed for 1+ minutes, initiating restart"
            restart_container "$TTS_CONTAINER"
            failure_counts["$TTS_CONTAINER"]=0
            sleep 30
        fi
    fi
    
    # --- System Health Checks ---
    check_gpu_health
    check_memory
    
    # Wait before next check
    sleep "$CHECK_INTERVAL"
done
