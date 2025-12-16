#!/bin/bash
# Quick activation helper
# Usage: source activate.sh

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated (./venv)"
    echo "  Python: $(python --version)"
    echo "  Location: $(which python)"
else
    echo "✗ Virtual environment not found!"
    echo "  Run: ./setup_env.sh"
    exit 1
fi
