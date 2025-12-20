"""
Integration Test: Async Upload with Race Condition Prevention
==============================================================
Tests the Write-Ahead Log pattern for document upload.

Verifies:
1. Immediate 202 response
2. DB record exists immediately (no race condition)
3. Status transitions: PENDING → PROCESSING → READY
4. Error handling with FAILED status
"""

import asyncio
import io
import os
import pytest
import tempfile
from pathlib import Path
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "apps" / "backend"))

from database.models import DocumentModel, DocumentStatus
from models.project import Base, Project
from main import app


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def test_db():
    """Create a test database with schema."""
    # Use in-memory SQLite for testing
    db_url = "sqlite+aiosqlite:///:memory:"
    
    engine = create_async_engine(db_url, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    yield session_factory
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_project(test_db):
    """Create a test project in the database."""
    async with test_db() as session:
        project = Project(
            project_id=uuid4(),
            name="Test Project",
            description="Integration test project"
        )
        session.add(project)
        await session.commit()
        
        # Refresh to get server defaults
        await session.refresh(project)
        
        project_id = project.project_id
    
    return str(project_id)


@pytest.fixture
def test_pdf_file():
    """Create a minimal test PDF file."""
    # Minimal valid PDF content
    pdf_content = b"""%PDF-1.4
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
    
    return io.BytesIO(pdf_content)


# =============================================================================
# Tests
# =============================================================================

@pytest.mark.asyncio
async def test_upload_returns_202_immediately(test_project, test_pdf_file):
    """
    VERIFIER: Upload endpoint returns 202 Accepted.
    
    This test verifies that the upload endpoint returns immediately
    with a 202 status code, not blocking on processing.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sources/upload",
            files={"file": ("test.pdf", test_pdf_file, "application/pdf")},
            data={"project_id": test_project}
        )
    
    # ASSERT: Response is 202 Accepted
    assert response.status_code == 202, f"Expected 202, got {response.status_code}"
    
    # ASSERT: Response contains document ID
    data = response.json()
    assert "id" in data, "Response missing 'id' field"
    assert "status" in data, "Response missing 'status' field"
    assert data["status"] == "pending", f"Expected status 'pending', got {data['status']}"
    
    print(f"✓ Upload returned 202 with doc_id={data['id']}")


@pytest.mark.asyncio
async def test_no_race_condition(test_project, test_pdf_file, test_db):
    """
    VERIFIER: DB record exists immediately after upload (no race condition).
    
    This test verifies the Write-Ahead Log pattern: the database record
    is created BEFORE the response is returned, preventing race conditions
    where a status query might fail.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload file
        response = await client.post(
            "/api/v1/sources/upload",
            files={"file": ("test.pdf", test_pdf_file, "application/pdf")},
            data={"project_id": test_project}
        )
    
    assert response.status_code == 202
    doc_id = response.json()["id"]
    
    # IMMEDIATE query (no sleep) - this is the race condition test
    async with test_db() as session:
        stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
    
    # ASSERT: Document exists in DB immediately
    assert doc is not None, f"Document {doc_id} not found in DB immediately after upload"
    assert doc.status in [DocumentStatus.PENDING, DocumentStatus.PROCESSING], \
        f"Expected PENDING or PROCESSING, got {doc.status}"
    
    print(f"✓ No race condition: DB record exists immediately with status={doc.status.value}")


@pytest.mark.asyncio
async def test_status_transitions(test_project, test_pdf_file):
    """
    VERIFIER: Status transitions from PENDING → PROCESSING → READY.
    
    This test polls the status endpoint and verifies that the document
    status transitions through the expected states.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload file
        upload_response = await client.post(
            "/api/v1/sources/upload",
            files={"file": ("test.pdf", test_pdf_file, "application/pdf")},
            data={"project_id": test_project}
        )
    
    assert upload_response.status_code == 202
    doc_id = upload_response.json()["id"]
    
    # Poll status every 100ms for up to 10 seconds
    statuses_seen = []
    final_status = None
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        for i in range(100):  # Max 10 seconds
            status_response = await client.get(f"/api/v1/sources/{doc_id}/status")
            
            assert status_response.status_code == 200, \
                f"Status endpoint returned {status_response.status_code}"
            
            status_data = status_response.json()
            current_status = status_data["status"]
            
            if current_status not in statuses_seen:
                statuses_seen.append(current_status)
                print(f"  Status transition: {current_status}")
            
            if current_status == "ready":
                final_status = "ready"
                break
            elif current_status == "failed":
                error_msg = status_data.get("error_message", "Unknown error")
                pytest.fail(f"Upload failed: {error_msg}")
            
            await asyncio.sleep(0.1)
    
    # ASSERT: Final status is READY
    assert final_status == "ready", \
        f"Expected final status 'ready', got {final_status}. Seen: {statuses_seen}"
    
    # ASSERT: Status transitions are valid
    # Valid transitions: PENDING → PROCESSING → READY
    # or PENDING → READY (if processing is very fast)
    assert "pending" in statuses_seen, "Never saw PENDING status"
    
    print(f"✓ Status transitions complete: {' → '.join(statuses_seen)}")


@pytest.mark.asyncio
async def test_error_handling(test_project):
    """
    VERIFIER: Failed uploads result in FAILED status with error message.
    
    This test simulates an upload failure (invalid file) and verifies
    that the status is updated to FAILED with an appropriate error message.
    """
    # Create an invalid file (empty)
    invalid_file = io.BytesIO(b"")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload invalid file
        upload_response = await client.post(
            "/api/v1/sources/upload",
            files={"file": ("invalid.pdf", invalid_file, "application/pdf")},
            data={"project_id": test_project}
        )
    
    # Upload should still return 202 (accepted)
    assert upload_response.status_code == 202
    doc_id = upload_response.json()["id"]
    
    # Poll status until processing completes
    final_status = None
    error_message = None
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        for i in range(100):  # Max 10 seconds
            status_response = await client.get(f"/api/v1/sources/{doc_id}/status")
            status_data = status_response.json()
            current_status = status_data["status"]
            
            if current_status in ["ready", "failed"]:
                final_status = current_status
                error_message = status_data.get("error_message")
                break
            
            await asyncio.sleep(0.1)
    
    # ASSERT: Status is FAILED (empty file should fail parsing)
    assert final_status == "failed", \
        f"Expected status 'failed' for invalid file, got {final_status}"
    
    # ASSERT: Error message is present
    assert error_message is not None, "Expected error_message for FAILED status"
    assert len(error_message) > 0, "Error message should not be empty"
    
    print(f"✓ Error handling works: status=failed, error={error_message[:50]}...")


@pytest.mark.asyncio
async def test_concurrent_uploads(test_project, test_pdf_file):
    """
    VERIFIER: Multiple concurrent uploads don't interfere with each other.
    
    This test uploads multiple files concurrently and verifies that
    each gets its own DB record and processes independently.
    """
    num_uploads = 5
    
    async def upload_file(file_num: int):
        """Upload a single file and return the doc_id."""
        # Create a fresh file buffer for each upload
        pdf_content = test_pdf_file.getvalue()
        file_buffer = io.BytesIO(pdf_content)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sources/upload",
                files={"file": (f"test_{file_num}.pdf", file_buffer, "application/pdf")},
                data={"project_id": test_project}
            )
        
        assert response.status_code == 202
        return response.json()["id"]
    
    # Upload files concurrently
    doc_ids = await asyncio.gather(*[upload_file(i) for i in range(num_uploads)])
    
    # ASSERT: All uploads got unique IDs
    assert len(doc_ids) == num_uploads
    assert len(set(doc_ids)) == num_uploads, "Document IDs are not unique"
    
    # ASSERT: All documents eventually reach READY status
    async def wait_for_ready(doc_id: str):
        """Wait for a document to reach READY status."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            for _ in range(100):
                response = await client.get(f"/api/v1/sources/{doc_id}/status")
                status = response.json()["status"]
                
                if status == "ready":
                    return True
                elif status == "failed":
                    return False
                
                await asyncio.sleep(0.1)
        
        return False
    
    results = await asyncio.gather(*[wait_for_ready(doc_id) for doc_id in doc_ids])
    
    # ASSERT: All uploads succeeded
    assert all(results), f"Some uploads failed: {sum(results)}/{num_uploads} succeeded"
    
    print(f"✓ Concurrent uploads work: {num_uploads} files uploaded and processed")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
