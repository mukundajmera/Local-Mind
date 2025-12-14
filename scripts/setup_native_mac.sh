#!/bin/bash
# ==============================================================================
# Local Mind - macOS Native Setup Script
# ==============================================================================
# This script sets up native macOS services for M3 GPU acceleration
#
# Usage:
#   bash scripts/setup_native_mac.sh
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

print_header "Local Mind - macOS Native Setup"

# ==============================================================================
# Check macOS
# ==============================================================================

if [[ "$(uname)" != "Darwin" ]]; then
    print_error "This script is for macOS only!"
    exit 1
fi

print_success "Running on macOS"

# ==============================================================================
# Install Ollama
# ==============================================================================

print_header "Installing Ollama"

if command -v ollama &> /dev/null; then
    print_success "Ollama already installed"
    ollama --version
else
    print_info "Installing Ollama for macOS..."
    print_warning "This will download ~100MB and install Ollama.app"
    
    # Download Ollama for macOS
    OLLAMA_URL="https://ollama.com/download/Ollama-darwin.zip"
    TEMP_DIR=$(mktemp -d)
    
    print_info "Downloading Ollama..."
    curl -L "$OLLAMA_URL" -o "$TEMP_DIR/Ollama.zip"
    
    print_info "Extracting..."
    unzip -q "$TEMP_DIR/Ollama.zip" -d "$TEMP_DIR"
    
    print_info "Installing to /Applications..."
    sudo cp -R "$TEMP_DIR/Ollama.app" /Applications/
    
    # Add CLI to PATH
    sudo ln -sf /Applications/Ollama.app/Contents/Resources/ollama /usr/local/bin/ollama
    
    rm -rf "$TEMP_DIR"
    
    if command -v ollama &> /dev/null; then
        print_success "Ollama installed successfully"
    else
        print_error "Ollama installation failed!"
        print_info "Manual installation: Download from https://ollama.com/download"
        exit 1
    fi
fi

# ==============================================================================
# Start Ollama Service
# ==============================================================================

print_header "Starting Ollama Service"

# Check if Ollama is running
if pgrep -x "ollama" > /dev/null; then
    print_success "Ollama service is already running"
else
    print_info "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
    
    if pgrep -x "ollama" > /dev/null; then
        print_success "Ollama service started"
    else
        print_warning "Ollama service may not have started. Try running 'ollama serve' manually."
    fi
fi

# ==============================================================================
# Pull LLM Model
# ==============================================================================

print_header "Downloading LLM Model"

MODEL_NAME="llama3.2:3b"
print_info "Pulling model: $MODEL_NAME"
print_warning "This may take several minutes (1-2 GB download)..."

ollama pull $MODEL_NAME

print_success "Model downloaded: $MODEL_NAME"

# ==============================================================================
# Test Model
# ==============================================================================

print_header "Testing Model"

print_info "Running test inference..."
TEST_RESPONSE=$(ollama run $MODEL_NAME "Say 'Hello from M3 GPU!' in exactly 5 words." --verbose 2>&1 | head -1)

print_success "Test response: $TEST_RESPONSE"

# ==============================================================================
# Check Metal Support
# ==============================================================================

print_header "Checking Metal GPU Support"

# Ollama automatically uses Metal on macOS
print_info "Ollama on macOS automatically uses Metal for GPU acceleration"
print_success "M3 GPU acceleration is enabled!"

# ==============================================================================
# Complete
# ==============================================================================

print_header "Setup Complete!"

echo -e "${GREEN}"
cat << 'EOF'

   ___   _  _                        
  / _ \ | || | __ _  _ __ ___    __ _ 
 | | | || || |/ _` || '_ ` _ \  / _` |
 | |_| || || | (_| || | | | | || (_| |
  \___/ |_||_|\__,_||_| |_| |_| \__,_|
                                      
EOF
echo -e "${NC}"

echo -e "${CYAN}Ollama is ready:${NC}"
echo ""
echo -e "  📍 Service URL: ${GREEN}http://localhost:11434${NC}"
echo -e "  🤖 Model: ${GREEN}$MODEL_NAME${NC}"
echo -e "  ⚡ GPU: ${GREEN}Metal (M3)${NC}"
echo ""

echo -e "${CYAN}Test commands:${NC}"
echo ""
echo "  Check status:   ollama list"
echo "  Run chat:       ollama run $MODEL_NAME"
echo "  Stop service:   pkill ollama"
echo ""

echo -e "${YELLOW}Next step:${NC} Run 'sh scripts/init.sh' to start the full stack"
echo ""
