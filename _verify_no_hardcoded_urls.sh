#!/bin/bash
# _verify_no_hardcoded_urls.sh

# Search for hardcoded localhost:8000 in frontend source code
# We exclude .env files and this script itself
echo "Running Static Analysis for Hardcoded URLs..."

MATCHES=$(grep -r "http://localhost:8000" apps/frontend/components apps/frontend/hooks)

if [ -n "$MATCHES" ]; then
    echo "FAIL: Hardcoded localhost URLs found:"
    echo "$MATCHES"
    exit 1
else
    echo "PASS: No hardcoded localhost URLs found in checked directories."
    exit 0
fi
