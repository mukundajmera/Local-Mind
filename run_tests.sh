#!/bin/bash
# =============================================================================
# Sovereign Cognitive Engine - Test Execution Script
# =============================================================================
# Runs all tests, generates coverage, produces HTML report, and zips evidence.
#
# Usage:
#   ./run_tests.sh              # Run unit + integration tests
#   ./run_tests.sh --all        # Include E2E tests (requires containers)
#   ./run_tests.sh --unit       # Unit tests only
#   ./run_tests.sh --e2e        # E2E tests only
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TESTS_DIR="$PROJECT_ROOT/tests"
EVIDENCE_DIR="$PROJECT_ROOT/evidence"
REPORTS_DIR="$PROJECT_ROOT/reports"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_NAME="test_report_${TIMESTAMP}.html"

# =============================================================================
# Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed."
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
    
    # Check pytest
    if ! python3 -c "import pytest" 2>/dev/null; then
        print_warning "pytest not found. Installing test dependencies..."
        pip install pytest pytest-asyncio pytest-html pytest-cov httpx
    fi
    print_success "pytest installed"
    
    # Check pytest-html
    if ! python3 -c "import pytest_html" 2>/dev/null; then
        pip install pytest-html
    fi
    print_success "pytest-html installed"
}

setup_directories() {
    print_header "Setting Up Directories"
    
    mkdir -p "$EVIDENCE_DIR"
    mkdir -p "$REPORTS_DIR"
    
    print_success "Evidence directory: $EVIDENCE_DIR"
    print_success "Reports directory: $REPORTS_DIR"
}

run_unit_tests() {
    print_header "Running Unit Tests"
    
    cd "$PROJECT_ROOT"
    
    python3 -m pytest tests/unit \
        -m "unit" \
        -v \
        --tb=short \
        --html="$REPORTS_DIR/unit_${TIMESTAMP}.html" \
        --self-contained-html \
        --cov=apps/backend \
        --cov-report=term-missing \
        --cov-report=html:"$REPORTS_DIR/coverage_unit" \
        || true
    
    print_success "Unit tests completed"
}

run_integration_tests() {
    print_header "Running Integration Tests"
    
    cd "$PROJECT_ROOT"
    
    python3 -m pytest tests/integration \
        -m "integration" \
        -v \
        --tb=short \
        --html="$REPORTS_DIR/integration_${TIMESTAMP}.html" \
        --self-contained-html \
        --cov=apps/backend \
        --cov-append \
        --cov-report=term-missing \
        --cov-report=html:"$REPORTS_DIR/coverage_integration" \
        || true
    
    print_success "Integration tests completed"
}

run_e2e_tests() {
    print_header "Running E2E Tests"
    
    # Check if containers are running
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        print_warning "Backend not reachable. Skipping E2E tests."
        print_warning "Start containers with: nerdctl compose up -d"
        return
    fi
    
    cd "$PROJECT_ROOT"
    
    E2E_ACTIVE=1 python3 -m pytest tests/e2e \
        -m "e2e" \
        -v \
        --tb=long \
        --html="$REPORTS_DIR/e2e_${TIMESTAMP}.html" \
        --self-contained-html \
        || true
    
    print_success "E2E tests completed"
}

run_all_tests() {
    print_header "Running All Tests"
    
    cd "$PROJECT_ROOT"
    
    # Determine if E2E should be included
    E2E_FLAG=""
    if [[ "$1" == "--all" ]] || [[ "$1" == "--e2e" ]]; then
        E2E_FLAG="E2E_ACTIVE=1"
    fi
    
    $E2E_FLAG python3 -m pytest tests \
        -v \
        --tb=short \
        --html="$REPORTS_DIR/$REPORT_NAME" \
        --self-contained-html \
        --cov=apps/backend \
        --cov-report=term-missing \
        --cov-report=html:"$REPORTS_DIR/coverage_full" \
        --cov-report=xml:"$REPORTS_DIR/coverage.xml" \
        || true
    
    print_success "All tests completed"
}

generate_summary() {
    print_header "Generating Summary"
    
    # Find the latest evidence directory
    LATEST_EVIDENCE=$(ls -td "$EVIDENCE_DIR"/*/ 2>/dev/null | head -1)
    
    if [ -n "$LATEST_EVIDENCE" ]; then
        print_success "Evidence collected in: $LATEST_EVIDENCE"
        
        # List evidence files
        echo ""
        echo "Evidence files:"
        ls -la "$LATEST_EVIDENCE" 2>/dev/null | tail -n +2
    fi
    
    # List reports
    echo ""
    echo "Reports generated:"
    ls -la "$REPORTS_DIR"/*.html 2>/dev/null | tail -n +2 || echo "  (no reports yet)"
}

zip_evidence() {
    print_header "Packaging Evidence"
    
    # Find the latest evidence directory
    LATEST_EVIDENCE=$(ls -td "$EVIDENCE_DIR"/*/ 2>/dev/null | head -1)
    
    if [ -n "$LATEST_EVIDENCE" ] && [ -d "$LATEST_EVIDENCE" ]; then
        EVIDENCE_NAME=$(basename "$LATEST_EVIDENCE")
        ZIP_NAME="evidence_${EVIDENCE_NAME}.zip"
        
        cd "$EVIDENCE_DIR"
        zip -r "$REPORTS_DIR/$ZIP_NAME" "$EVIDENCE_NAME"
        
        print_success "Evidence packaged: $REPORTS_DIR/$ZIP_NAME"
    else
        print_warning "No evidence to package"
    fi
}

show_results() {
    print_header "Test Results"
    
    echo ""
    echo -e "📊 ${GREEN}Reports saved to:${NC} $REPORTS_DIR"
    echo ""
    echo "   HTML Report:  $REPORTS_DIR/$REPORT_NAME"
    echo "   Coverage:     $REPORTS_DIR/coverage_full/index.html"
    echo ""
    
    if [ -f "$REPORTS_DIR/evidence_*.zip" ]; then
        echo -e "📦 ${GREEN}Evidence package:${NC} $(ls "$REPORTS_DIR"/evidence_*.zip | tail -1)"
    fi
    
    echo ""
    echo -e "${BLUE}Open the HTML report in your browser to view detailed results.${NC}"
    echo ""
}

# =============================================================================
# Main Execution
# =============================================================================

print_header "Sovereign Cognitive Engine - Test Suite"
echo "Timestamp: $TIMESTAMP"

check_dependencies
setup_directories

# Parse arguments
case "$1" in
    --unit)
        run_unit_tests
        ;;
    --integration)
        run_integration_tests
        ;;
    --e2e)
        run_e2e_tests
        ;;
    --all)
        run_all_tests --all
        ;;
    *)
        # Default: unit + integration (no E2E)
        run_unit_tests
        run_integration_tests
        ;;
esac

generate_summary
zip_evidence
show_results

print_success "Test execution complete!"
