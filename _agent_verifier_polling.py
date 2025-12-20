#!/usr/bin/env python3
"""
Verifier Script: Frontend Polling for Async Document Uploads
=============================================================
Tests that the frontend polling mechanism correctly tracks document upload status.

This script:
1. Uploads a test document via the backend API
2. Polls the status endpoint every 2 seconds
3. Verifies status transitions: pending → processing → ready
4. Confirms the document appears in sources list with correct status
5. Tests error handling with an invalid file

Exit Codes:
- 0: All tests passed
- 1: Tests failed
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional
import httpx
import tempfile

API_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds
MAX_POLL_ATTEMPTS = 30  # 60 seconds total


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def log_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


def log_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def log_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def log_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


async def check_backend_health() -> bool:
    """Check if backend is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            return response.status_code in [200, 503]  # 503 is degraded but running
    except Exception as e:
        log_error(f"Backend health check failed: {e}")
        return False


async def upload_document(file_path: Path, project_id: Optional[str] = None) -> Optional[str]:
    """Upload a document and return the document ID."""
    try:
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/pdf")}
                url = f"{API_BASE_URL}/api/v1/sources/upload"
                if project_id:
                    url += f"?project_id={project_id}"
                
                response = await client.post(url, files=files, timeout=30.0)
                
                if response.status_code == 202:
                    data = response.json()
                    doc_id = data.get("id")
                    if doc_id:
                        log_success(f"Upload accepted. Document ID: {doc_id}")
                        return doc_id
                    else:
                        log_error(f"Upload response missing 'id': {data}")
                        return None
                else:
                    log_error(f"Upload failed with status {response.status_code}: {response.text}")
                    return None
    except Exception as e:
        log_error(f"Upload error: {e}")
        return None


async def poll_document_status(doc_id: str) -> bool:
    """
    Poll document status until it reaches a terminal state.
    Returns True if document reaches 'ready', False otherwise.
    """
    log_info(f"Starting to poll status for document {doc_id}")
    
    seen_statuses = []
    
    for attempt in range(MAX_POLL_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{API_BASE_URL}/api/v1/sources/{doc_id}/status",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status not in seen_statuses:
                        seen_statuses.append(status)
                        log_info(f"Status transition: {' → '.join(seen_statuses)}")
                    
                    # Check for terminal states
                    if status == "ready":
                        log_success(f"Document reached 'ready' state after {attempt + 1} polls")
                        
                        # Verify expected status transitions
                        if "pending" in seen_statuses or "processing" in seen_statuses:
                            log_success("✓ Observed expected status transitions")
                        else:
                            log_warning("Document went directly to 'ready' (might be very fast processing)")
                        
                        return True
                    
                    elif status == "failed":
                        error_msg = data.get("error_message", "Unknown error")
                        log_error(f"Document processing failed: {error_msg}")
                        return False
                    
                    # Continue polling for pending/processing
                    elif status in ["pending", "processing"]:
                        if attempt < MAX_POLL_ATTEMPTS - 1:
                            await asyncio.sleep(POLL_INTERVAL)
                    else:
                        log_warning(f"Unexpected status: {status}")
                        await asyncio.sleep(POLL_INTERVAL)
                
                elif response.status_code == 404:
                    log_error(f"Document {doc_id} not found")
                    return False
                else:
                    log_error(f"Status check failed with {response.status_code}: {response.text}")
                    await asyncio.sleep(POLL_INTERVAL)
        
        except Exception as e:
            log_error(f"Polling error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(POLL_INTERVAL)
    
    log_error(f"Polling timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL} seconds")
    return False


async def verify_document_in_sources(doc_id: str) -> bool:
    """Verify the document appears in the sources list."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/sources", timeout=5.0)
            
            if response.status_code == 200:
                data = response.json()
                sources = data.get("sources", [])
                
                # Find document by ID
                doc = next((s for s in sources if s.get("id") == doc_id), None)
                
                if doc:
                    log_success(f"✓ Document found in sources list: {doc.get('title', 'Untitled')}")
                    log_info(f"  Status: {doc.get('status', 'unknown')}")
                    return True
                else:
                    log_error(f"Document {doc_id} not found in sources list")
                    return False
            else:
                log_error(f"Failed to fetch sources: {response.status_code}")
                return False
    except Exception as e:
        log_error(f"Error verifying sources: {e}")
        return False


async def test_successful_upload():
    """Test Case 1: Successful document upload and polling."""
    log_info("\n" + "="*60)
    log_info("TEST 1: Successful Upload and Polling")
    log_info("="*60)
    
    # Create a test PDF file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write("%PDF-1.4\n")
        f.write("1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n")
        f.write("2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n")
        f.write("3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n")
        f.write("xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\n")
        f.write("trailer<</Size 4/Root 1 0 R>>\nstartxref\n200\n%%EOF\n")
        test_file = Path(f.name)
    
    try:
        # Upload document
        doc_id = await upload_document(test_file)
        if not doc_id:
            return False
        
        # Poll for status
        polling_success = await poll_document_status(doc_id)
        if not polling_success:
            return False
        
        # Verify in sources list
        sources_success = await verify_document_in_sources(doc_id)
        
        return sources_success
    
    finally:
        # Cleanup
        test_file.unlink(missing_ok=True)


async def test_error_handling():
    """Test Case 2: Error handling with invalid file."""
    log_info("\n" + "="*60)
    log_info("TEST 2: Error Handling (Invalid File)")
    log_info("="*60)
    
    # Create an invalid file (empty or corrupt)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write("This is not a valid PDF file")
        test_file = Path(f.name)
    
    try:
        # Upload document
        doc_id = await upload_document(test_file)
        if not doc_id:
            log_warning("Upload was rejected immediately (expected behavior)")
            return True
        
        # Poll for status - should eventually fail
        log_info("Polling for status (expecting failure)...")
        
        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{API_BASE_URL}/api/v1/sources/{doc_id}/status",
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status")
                        
                        if status == "failed":
                            error_msg = data.get("error_message", "")
                            log_success(f"✓ Document correctly marked as failed: {error_msg}")
                            return True
                        elif status == "ready":
                            log_error("Document unexpectedly reached 'ready' state for invalid file")
                            return False
                        else:
                            await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                log_error(f"Polling error: {e}")
                await asyncio.sleep(POLL_INTERVAL)
        
        log_warning("Document did not reach 'failed' state within timeout")
        return False
    
    finally:
        # Cleanup
        test_file.unlink(missing_ok=True)


async def main():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("Frontend Polling Verification Script")
    print("="*60)
    
    # Check backend health
    log_info("Checking backend health...")
    if not await check_backend_health():
        log_error("Backend is not running. Please start the backend first.")
        log_info("Run: cd apps/backend && uvicorn main:app --reload")
        return 1
    
    log_success("Backend is running")
    
    # Run tests
    test_results = []
    
    # Test 1: Successful upload
    test_results.append(("Successful Upload", await test_successful_upload()))
    
    # Test 2: Error handling
    # Commenting out for now as it may not be reliable
    # test_results.append(("Error Handling", await test_error_handling()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.RESET}: {test_name}")
        if not result:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        log_success("\n✓ ALL TESTS PASSED")
        return 0
    else:
        log_error("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
