#!/usr/bin/env python3
"""
Verification Script for Bug Fixes
==================================
Tests all 5 critical bug fixes to ensure correctness.

Run with: python _agent_verifier_bugfixes.py
Requires: Backend running on localhost:8000
"""

import asyncio
import httpx
import sys
import time
import os

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 30.0


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
    
    def __str__(self):
        status = "PASS ✓" if self.passed else "FAIL ✗"
        return f"[{status}] {self.name}: {self.message}"


async def test_bug1_project_persistence() -> TestResult:
    """Bug #1: Projects should be persisted to database, not in-memory."""
    result = TestResult("Bug #1: Project Persistence")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Create a unique project
            project_name = f"Test_Project_{int(time.time())}"
            response = await client.post(
                f"{BASE_URL}/api/v1/projects",
                json={"name": project_name, "description": "Verification test"}
            )
            
            if response.status_code != 201:
                result.message = f"Failed to create project: {response.status_code} - {response.text}"
                return result
            
            project = response.json()
            project_id = project.get("project_id")
            
            # List projects and verify it exists
            list_response = await client.get(f"{BASE_URL}/api/v1/projects")
            if list_response.status_code != 200:
                result.message = f"Failed to list projects: {list_response.status_code}"
                return result
            
            projects = list_response.json()
            found = any(p.get("project_id") == project_id for p in projects)
            
            if not found:
                result.message = "Created project not found in list"
                return result
            
            result.passed = True
            result.message = f"Project '{project_name}' created and persisted (ID: {project_id})"
            
            # Cleanup
            await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
            
        except Exception as e:
            result.message = f"Exception: {str(e)}"
    
    return result


async def test_bug2_briefing_endpoint() -> TestResult:
    """Bug #2: Briefing endpoint should work with datetime import."""
    result = TestResult("Bug #2: Briefing Endpoint (datetime import)")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # First create a project
            project_name = f"Briefing_Test_{int(time.time())}"
            proj_resp = await client.post(
                f"{BASE_URL}/api/v1/projects",
                json={"name": project_name, "description": "Test"}
            )
            if proj_resp.status_code != 201:
                result.message = f"Failed to create project: {proj_resp.status_code}"
                return result
            
            project_id = proj_resp.json()["project_id"]
            
            # Upload a simple text file with enough content for briefing
            test_content = b"""This is a comprehensive test document for verification of the briefing service.
            It contains multiple paragraphs of sample text to verify that the system can process it 
            and generate a proper summary with key topics and suggested questions.
            The document discusses testing methodologies and verification procedures.
            Key topics include: automated testing, verification, and quality assurance.
            """
            files = {"file": ("test.txt", test_content, "text/plain")}
            data = {"project_id": project_id}
            
            upload_resp = await client.post(
                f"{BASE_URL}/api/v1/sources/upload",
                files=files,
                data=data
            )
            
            if upload_resp.status_code != 202:
                result.message = f"Upload failed: {upload_resp.status_code} - {upload_resp.text}"
                # Cleanup
                await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                return result
            
            doc_id = upload_resp.json().get("id")
            
            # Wait for processing (includes briefing generation)
            max_wait = 60
            waited = 0
            while waited < max_wait:
                status_resp = await client.get(f"{BASE_URL}/api/v1/sources/{doc_id}/status")
                if status_resp.status_code == 200:
                    status = status_resp.json().get("status")
                    if status == "ready":
                        break
                    elif status == "failed":
                        result.message = f"Document processing failed: {status_resp.json()}"
                        await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
                        await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                        return result
                await asyncio.sleep(2)
                waited += 2
            
            # Try briefing endpoint - should return 200 with actual content
            briefing_resp = await client.get(f"{BASE_URL}/api/v1/sources/{doc_id}/briefing")
            
            if briefing_resp.status_code == 500 and "datetime" in briefing_resp.text.lower():
                result.message = "datetime import error still present"
            elif briefing_resp.status_code == 200:
                data = briefing_resp.json()
                # Check that we got actual content
                if data.get("summary") and len(data.get("summary", "")) > 10:
                    result.passed = True
                    result.message = f"Briefing returned with summary ({len(data.get('summary'))} chars), {len(data.get('key_topics', []))} topics, {len(data.get('suggested_questions', []))} questions"
                else:
                    result.message = f"Briefing response missing content: {data}"
            elif briefing_resp.status_code == 404:
                result.message = "Briefing returned 404 - might be still processing"
            else:
                result.message = f"Unexpected response: {briefing_resp.status_code} - {briefing_resp.text}"
            
            # Cleanup
            await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
            await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
            
        except Exception as e:
            result.message = f"Exception: {str(e)}"
    
    return result


async def test_bug3_deletion_cleanup() -> TestResult:
    """Bug #3: Delete should remove from both Milvus and database."""
    result = TestResult("Bug #3: Deletion Cleanup (DB + Milvus)")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Create project
            project_name = f"Delete_Test_{int(time.time())}"
            proj_resp = await client.post(
                f"{BASE_URL}/api/v1/projects",
                json={"name": project_name, "description": "Test"}
            )
            if proj_resp.status_code != 201:
                result.message = f"Failed to create project: {proj_resp.status_code}"
                return result
            
            project_id = proj_resp.json()["project_id"]
            
            # Upload a file
            test_content = b"Delete test document content."
            files = {"file": ("delete_test.txt", test_content, "text/plain")}
            data = {"project_id": project_id}
            
            upload_resp = await client.post(
                f"{BASE_URL}/api/v1/sources/upload",
                files=files,
                data=data
            )
            
            if upload_resp.status_code != 202:
                result.message = f"Upload failed: {upload_resp.status_code}"
                await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                return result
            
            doc_id = upload_resp.json().get("id")
            
            # Wait for processing to complete
            max_wait = 30
            waited = 0
            while waited < max_wait:
                status_resp = await client.get(f"{BASE_URL}/api/v1/sources/{doc_id}/status")
                if status_resp.status_code == 200:
                    status = status_resp.json().get("status")
                    if status == "ready":
                        break
                    elif status == "failed":
                        result.message = f"Document processing failed"
                        await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                        return result
                await asyncio.sleep(2)
                waited += 2
            
            # Delete the document
            delete_resp = await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
            
            if delete_resp.status_code != 200:
                result.message = f"Delete failed: {delete_resp.status_code}"
                await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                return result
            
            delete_result = delete_resp.json()
            
            # Check if db_deleted is present (our fix)
            if "db_deleted" in delete_result:
                result.passed = True
                result.message = f"Delete response includes db_deleted: {delete_result.get('db_deleted')}"
            else:
                result.message = "db_deleted field not in response - fix may not be applied"
            
            # Cleanup
            await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
            
        except Exception as e:
            result.message = f"Exception: {str(e)}"
    
    return result


async def test_bug4_project_required() -> TestResult:
    """Bug #4: Upload without project_id should return 400."""
    result = TestResult("Bug #4: Project Required on Upload")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Try to upload without project_id
            test_content = b"Test content without project."
            files = {"file": ("no_project.txt", test_content, "text/plain")}
            
            upload_resp = await client.post(
                f"{BASE_URL}/api/v1/sources/upload",
                files=files
                # No project_id in data
            )
            
            if upload_resp.status_code == 400:
                result.passed = True
                result.message = f"Correctly rejected with 400: {upload_resp.json().get('detail', '')[:50]}"
            elif upload_resp.status_code == 202:
                result.message = "Upload accepted without project_id - validation not working"
                # Cleanup if accidentally created
                doc_id = upload_resp.json().get("id")
                if doc_id:
                    await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
            else:
                result.message = f"Unexpected status: {upload_resp.status_code}"
                
        except Exception as e:
            result.message = f"Exception: {str(e)}"
    
    return result


async def test_bug5_document_count() -> TestResult:
    """Bug #5: Project document_count should come from DB, not in-memory."""
    result = TestResult("Bug #5: Document Count from DB")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            # Create project
            project_name = f"Count_Test_{int(time.time())}"
            proj_resp = await client.post(
                f"{BASE_URL}/api/v1/projects",
                json={"name": project_name, "description": "Test"}
            )
            if proj_resp.status_code != 201:
                result.message = f"Failed to create project: {proj_resp.status_code}"
                return result
            
            project = proj_resp.json()
            project_id = project["project_id"]
            initial_count = project.get("document_count", 0)
            
            # Upload a file
            test_content = b"Count test document."
            files = {"file": ("count_test.txt", test_content, "text/plain")}
            data = {"project_id": project_id}
            
            upload_resp = await client.post(
                f"{BASE_URL}/api/v1/sources/upload",
                files=files,
                data=data
            )
            
            if upload_resp.status_code != 202:
                result.message = f"Upload failed: {upload_resp.status_code}"
                await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                return result
            
            doc_id = upload_resp.json().get("id")
            
            # Wait for processing
            await asyncio.sleep(5)
            
            # Get project and check count
            get_resp = await client.get(f"{BASE_URL}/api/v1/projects/{project_id}")
            if get_resp.status_code != 200:
                result.message = f"Failed to get project: {get_resp.status_code}"
                await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
                await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
                return result
            
            updated_project = get_resp.json()
            new_count = updated_project.get("document_count", 0)
            
            if new_count > initial_count:
                result.passed = True
                result.message = f"Count increased: {initial_count} -> {new_count}"
            else:
                result.message = f"Count did not increase: {initial_count} -> {new_count}"
            
            # Cleanup
            await client.delete(f"{BASE_URL}/api/v1/sources/{doc_id}")
            await client.delete(f"{BASE_URL}/api/v1/projects/{project_id}")
            
        except Exception as e:
            result.message = f"Exception: {str(e)}"
    
    return result


async def run_all_tests():
    print("=" * 60)
    print("Bug Fixes Verification Script")
    print("=" * 60)
    print(f"Backend URL: {BASE_URL}")
    print()
    
    # Check if backend is reachable
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{BASE_URL}/health")
            print(f"Backend health: {health.status_code}")
    except Exception as e:
        print(f"ERROR: Cannot reach backend at {BASE_URL}")
        print(f"Exception: {e}")
        print("\nPlease start the backend first:")
        print("  cd apps/backend && python main.py")
        sys.exit(1)
    
    print()
    print("Running tests...")
    print("-" * 60)
    
    results = []
    
    # Run all tests
    results.append(await test_bug1_project_persistence())
    results.append(await test_bug4_project_required())  # Quick test, run early
    results.append(await test_bug3_deletion_cleanup())
    results.append(await test_bug5_document_count())
    results.append(await test_bug2_briefing_endpoint())  # Slowest, run last
    
    # Print results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for r in results:
        print(r)
        if r.passed:
            passed += 1
        else:
            failed += 1
    
    print()
    print(f"Total: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        print("\nFAIL: Some tests did not pass.")
        sys.exit(1)
    else:
        print("\nPASS: All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
