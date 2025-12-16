#!/bin/bash
# ==============================================================================
# Local Mind - Unified Environment Setup
# ==============================================================================
# This script consolidates all Python dependencies into a single virtual
# environment at the project root for easier management.
# ==============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        🧠 LOCAL MIND - Environment Setup                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}[1/5]${NC} Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "      Found Python $PYTHON_VERSION"

# Create unified virtual environment
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[2/5]${NC} Virtual environment already exists at ./venv"
    read -p "      Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "      Removing old venv..."
        rm -rf "$VENV_DIR"
        echo "      Creating new virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
else
    echo -e "${YELLOW}[2/5]${NC} Creating virtual environment at ./venv..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo -e "${YELLOW}[3/5]${NC} Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${YELLOW}[4/5]${NC} Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install backend dependencies
echo -e "${YELLOW}[5/5]${NC} Installing backend dependencies..."
if [ -f "$PROJECT_ROOT/apps/backend/requirements.txt" ]; then
    pip install -r "$PROJECT_ROOT/apps/backend/requirements.txt"
    echo -e "${GREEN}✓${NC} Backend dependencies installed"
else
    echo -e "${RED}✗${NC} Backend requirements.txt not found!"
    exit 1
fi

# Install device manager dependencies (optional)
if [ -f "$PROJECT_ROOT/apps/backend/requirements_device_manager.txt" ]; then
    echo "      Installing device manager dependencies (optional)..."
    pip install -r "$PROJECT_ROOT/apps/backend/requirements_device_manager.txt" || echo "      (Some optional dependencies skipped)"
fi

# Install test dependencies (optional)
if [ -f "$PROJECT_ROOT/tests/requirements-test.txt" ]; then
    echo "      Installing test dependencies..."
    pip install -r "$PROJECT_ROOT/tests/requirements-test.txt" || echo "      (Test dependencies skipped)"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ SETUP COMPLETE                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Unified virtual environment created at: ./venv"
echo ""
echo "To activate the environment manually:"
echo -e "  ${YELLOW}source venv/bin/activate${NC}"
echo ""
echo "To start the application:"
echo -e "  ${YELLOW}./start.sh${NC}"
echo ""
