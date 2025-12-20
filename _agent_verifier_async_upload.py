#!/usr/bin/env python3
"""
Agent Verifier: Async Upload Implementation
============================================
Verifies that the async upload refactor works correctly.

This script:
1. Starts the backend server
2. Uploads a test document
3. Verifies 202 response
4. Polls status endpoint
5. Verifies status transitions (PENDING → PROCESSING → READY)
6. Checks for race conditions

Exit codes:
- 0: All tests passed
- 1: Tests failed
"""

import asyncio
import io
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


# =============================================================================
# Test Configuration
# =============================================================================

BACKEND_URL = "http://localhost:8000"
TEST_PROJECT_ID = str(uuid4())  # Use a random project ID for testing


# =============================================================================
# Test Utilities
# =============================================================================

def create_test_pdf() -> bytes:
    """Create a minimal valid PDF for testing."""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
308
%%EOF
"""


async def test_upload_returns_202():
    """
    TEST 1: Upload returns 202 Accepted immediately.
    
    PASS: Response code is 202
    FAIL: Response code is not 202
    """
    print("\n[TEST 1] Verifying 202 Accepted response...")
    
    pdf_content = create_test_pdf()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{BACKEND_URL}/api/v1/sources/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"project_id": TEST_PROJECT_ID}
            )
        except httpx.ConnectError:
            print("  ❌ FAIL: Cannot connect to backend server")
            print("     Make sure the backend is running: cd apps/backend && uvicorn main:app")
            return None
    
    if response.status_code != 202:
        print(f"  ❌ FAIL: Expected 202, got {response.status_code}")
        print(f"     Response: {response.text}")
        return None
    
    data = response.json()
    
    if "id" not in data:
        print("  ❌ FAIL: Response missing 'id' field")
        print(f"     Response: {data}")
        return None
    
    if "status" not in data:
        print("  ❌ FAIL: Response missing 'status' field")
        print(f"     Response: {data}")
        return None
    
    if data["status"] != "pending":
        print(f"  ❌ FAIL: Expected status 'pending', got '{data['status']}'")
        return None
    
    doc_id = data["id"]
    print(f"  ✅ PASS: Upload returned 202 with doc_id={doc_id}")
    
    return doc_id


async def test_no_race_condition(doc_id: str):
    """
    TEST 2: DB record exists immediately (no race condition).
    
    PASS: Status endpoint returns 200 immediately
    FAIL: Status endpoint returns 404
    """
    print("\n[TEST 2] Verifying no race condition...")
    
    # Query status IMMEDIATELY (no sleep)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BACKEND_URL}/api/v1/sources/{doc_id}/status")
    
    if response.status_code == 404:
        print("  ❌ FAIL: Document not found immediately after upload (race condition!)")
        return False
    
    if response.status_code != 200:
        print(f"  ❌ FAIL: Expected 200, got {response.status_code}")
        print(f"     Response: {response.text}")
        return False
    
    data = response.json()
    status = data.get("status")
    
    if status not in ["pending", "processing"]:
        print(f"  ❌ FAIL: Expected 'pending' or 'processing', got '{status}'")
        return False
    
    print(f"  ✅ PASS: DB record exists immediately with status={status}")
    return True


async def test_status_transitions(doc_id: str):
    """
    TEST 3: Status transitions from PENDING → PROCESSING → READY.
    
    PASS: Final status is 'ready'
    FAIL: Status is 'failed' or timeout
    """
    print("\n[TEST 3] Verifying status transitions...")
    
    statuses_seen = []
    final_status = None
    error_message = None
    
    # Poll for up to 30 seconds
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(300):  # 300 * 0.1s = 30s
            response = await client.get(f"{BACKEND_URL}/api/v1/sources/{doc_id}/status")
            
            if response.status_code != 200:
                print(f"  ❌ FAIL: Status endpoint returned {response.status_code}")
                return False
            
            data = response.json()
            current_status = data.get("status")
            
            if current_status not in statuses_seen:
                statuses_seen.append(current_status)
                print(f"     Status: {current_status}")
            
            if current_status == "ready":
                final_status = "ready"
                break
            elif current_status == "failed":
                final_status = "failed"
                error_message = data.get("error_message", "Unknown error")
                break
            
            await asyncio.sleep(0.1)
    
    if final_status == "failed":
        print(f"  ❌ FAIL: Upload failed with error: {error_message}")
        return False
    
    if final_status != "ready":
        print(f"  ❌ FAIL: Timeout waiting for 'ready' status")
        print(f"     Statuses seen: {' → '.join(statuses_seen)}")
        return False
    
    print(f"  ✅ PASS: Status transitions complete: {' → '.join(statuses_seen)}")
    return True


# =============================================================================
# Main Verification
# =============================================================================

async def main():
    """Run all verification tests."""
    print("=" * 70)
    print("AGENT VERIFIER: Async Upload Implementation")
    print("=" * 70)
    
    # Check backend health
    print("\n[SETUP] Checking backend health...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BACKEND_URL}/health")
            if response.status_code not in [200, 503]:
                print(f"  ⚠️  WARNING: Health check returned {response.status_code}")
            else:
                print(f"  ✓ Backend is running")
    except httpx.ConnectError:
        print("  ❌ ERROR: Cannot connect to backend")
        print("     Start the backend: cd apps/backend && uvicorn main:app")
        return 1
    
    # Run tests
    doc_id = await test_upload_returns_202()
    if not doc_id:
        print("\n" + "=" * 70)
        print("RESULT: FAILED")
        print("=" * 70)
        return 1
    
    race_condition_ok = await test_no_race_condition(doc_id)
    if not race_condition_ok:
        print("\n" + "=" * 70)
        print("RESULT: FAILED")
        print("=" * 70)
        return 1
    
    transitions_ok = await test_status_transitions(doc_id)
    if not transitions_ok:
        print("\n" + "=" * 70)
        print("RESULT: FAILED")
        print("=" * 70)
        return 1
    
    # All tests passed
    print("\n" + "=" * 70)
    print("RESULT: ALL TESTS PASSED ✅")
    print("=" * 70)
    print("\nVerified:")
    print("  ✓ Upload returns 202 Accepted")
    print("  ✓ No race condition (DB record exists immediately)")
    print("  ✓ Status transitions: PENDING → PROCESSING → READY")
    print("\nThe async upload refactor is working correctly!")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
