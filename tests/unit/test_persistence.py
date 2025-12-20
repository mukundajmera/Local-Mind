"""
Persistence Layer Unit Tests
=============================
Mutation-Killing Tests: Verify database-filesystem consistency.

These tests follow the Autonomous Engineering Protocol:
1. Create a verifier that reproduces the scenario
2. Assert the correct behavior
3. Exit with code 1 on failure, code 0 on success
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Add backend to path for imports
BACKEND_PATH = Path(__file__).parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(BACKEND_PATH))

pytestmark = pytest.mark.unit


class TestStorageConsistencyCheck:
    """
    Mutation-killing tests for sync_storage_consistency().
    
    These tests verify the self-healing behavior when the database
    and filesystem become inconsistent.
    """

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield f"sqlite+aiosqlite:///{db_path}"

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file that can be deleted during tests."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test document content for consistency check.")
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_sync_marks_missing_files_as_failed(self, temp_db_path, temp_file):
        """
        SCENARIO: DB record exists, physical file is deleted.
        ACTION: Run sync_storage_consistency().
        ASSERTION: Status changes to FAILED, error_message is set.
        
        This is a MUTATION TEST - it verifies that the consistency check
        actually detects and marks missing files, not just checks for errors.
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from database.models import DocumentModel, DocumentStatus
        from models.project import Base, Project
        from services.document_service import DocumentService
        
        # Setup: Create database and tables
        engine = create_async_engine(temp_db_path, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create test data
        project_id = uuid4()
        doc_id = uuid4()
        
        async with session_factory() as session:
            # Create a project first (required for FK constraint)
            project = Project(
                project_id=project_id,
                name=f"Test Project {project_id.hex[:8]}",
                description="Test project for consistency check"
            )
            session.add(project)
            await session.flush()
            
            # Create a document record pointing to our temp file
            doc = DocumentModel(
                id=doc_id,
                project_id=project_id,
                filename=temp_file.name,
                file_path=str(temp_file),
                status=DocumentStatus.READY,  # Simulate a processed document
            )
            session.add(doc)
            await session.commit()
            
            # Verify initial state
            assert doc.status == DocumentStatus.READY
            assert temp_file.exists(), "Test setup failed: file should exist"
        
        # ACTION: Delete the physical file (simulating data corruption)
        temp_file.unlink()
        assert not temp_file.exists(), "Test setup failed: file should be deleted"
        
        # ACTION: Run consistency check
        async with session_factory() as session:
            service = DocumentService.from_session(session)
            stats = await service.sync_storage_consistency()
            await session.commit()
        
        # ASSERTION: Verify the document was marked as FAILED
        async with session_factory() as session:
            from sqlalchemy import select
            stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
            result = await session.execute(stmt)
            updated_doc = result.scalar_one_or_none()
            
            # Critical assertions
            assert updated_doc is not None, "Document should still exist in DB"
            assert updated_doc.status == DocumentStatus.FAILED, (
                f"Status should be FAILED, got {updated_doc.status.value}"
            )
            assert updated_doc.error_message is not None, (
                "Error message should be set"
            )
            assert "Data Corruption" in updated_doc.error_message, (
                f"Error message should mention Data Corruption, got: {updated_doc.error_message}"
            )
            assert "File missing" in updated_doc.error_message, (
                f"Error message should mention File missing, got: {updated_doc.error_message}"
            )
        
        # Verify stats
        assert stats["checked"] >= 1, "Should have checked at least 1 document"
        assert stats["corrupted"] >= 1, "Should have found at least 1 corrupted document"
        assert stats["healthy"] == stats["checked"] - stats["corrupted"], (
            "Healthy + corrupted should equal checked"
        )
        
        # Cleanup
        await engine.dispose()
        
        print("PASS: sync_storage_consistency correctly marks missing files as FAILED")

    @pytest.mark.asyncio
    async def test_sync_does_not_modify_healthy_documents(self, temp_db_path, temp_file):
        """
        SCENARIO: DB record exists, physical file also exists.
        ACTION: Run sync_storage_consistency().
        ASSERTION: Status remains unchanged (not marked as FAILED).
        
        This is a negative test - ensuring healthy documents are not affected.
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from database.models import DocumentModel, DocumentStatus
        from models.project import Base, Project
        from services.document_service import DocumentService
        
        # Setup: Create database and tables
        engine = create_async_engine(temp_db_path, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create test data
        project_id = uuid4()
        doc_id = uuid4()
        
        async with session_factory() as session:
            project = Project(
                project_id=project_id,
                name=f"Test Project {project_id.hex[:8]}",
                description="Test project"
            )
            session.add(project)
            await session.flush()
            
            doc = DocumentModel(
                id=doc_id,
                project_id=project_id,
                filename=temp_file.name,
                file_path=str(temp_file),
                status=DocumentStatus.READY,
            )
            session.add(doc)
            await session.commit()
        
        # File still exists - should remain healthy
        assert temp_file.exists(), "Test setup failed: file should exist"
        
        # ACTION: Run consistency check
        async with session_factory() as session:
            service = DocumentService.from_session(session)
            stats = await service.sync_storage_consistency()
            await session.commit()
        
        # ASSERTION: Document should still be READY
        async with session_factory() as session:
            from sqlalchemy import select
            stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            assert doc is not None, "Document should still exist"
            assert doc.status == DocumentStatus.READY, (
                f"Healthy document status should remain READY, got {doc.status.value}"
            )
            assert doc.error_message is None, (
                f"Healthy document should not have error message, got: {doc.error_message}"
            )
        
        # Verify stats
        assert stats["corrupted"] == 0, "No documents should be marked as corrupted"
        assert stats["healthy"] >= 1, "Should have at least 1 healthy document"
        
        # Cleanup
        await engine.dispose()
        
        print("PASS: sync_storage_consistency does not affect healthy documents")

    @pytest.mark.asyncio
    async def test_sync_skips_already_failed_documents(self, temp_db_path):
        """
        SCENARIO: Document is already FAILED status.
        ACTION: Run sync_storage_consistency().
        ASSERTION: Document is not re-checked (to avoid duplicate work).
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from database.models import DocumentModel, DocumentStatus
        from models.project import Base, Project
        from services.document_service import DocumentService
        
        # Setup
        engine = create_async_engine(temp_db_path, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create a document that is already FAILED
        project_id = uuid4()
        doc_id = uuid4()
        
        async with session_factory() as session:
            project = Project(
                project_id=project_id,
                name=f"Test Project {project_id.hex[:8]}",
                description="Test project"
            )
            session.add(project)
            await session.flush()
            
            doc = DocumentModel(
                id=doc_id,
                project_id=project_id,
                filename="previously_failed.txt",
                file_path="/nonexistent/path/previously_failed.txt",
                status=DocumentStatus.FAILED,  # Already failed
                error_message="Previous failure reason",
            )
            session.add(doc)
            await session.commit()
        
        # ACTION: Run consistency check
        async with session_factory() as session:
            service = DocumentService.from_session(session)
            stats = await service.sync_storage_consistency()
            await session.commit()
        
        # ASSERTION: Already-failed document should not be counted as checked
        assert stats["checked"] == 0, (
            f"Already-failed documents should not be checked, got {stats['checked']}"
        )
        
        # Cleanup
        await engine.dispose()
        
        print("PASS: sync_storage_consistency skips already-failed documents")


class TestGetProjectDocuments:
    """
    Tests for get_project_documents() method.
    
    Verifies that document retrieval queries the database,
    NOT the filesystem.
    """

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield f"sqlite+aiosqlite:///{db_path}"

    @pytest.mark.asyncio
    async def test_get_project_documents_queries_db_not_filesystem(self, temp_db_path):
        """
        SCENARIO: Documents exist in DB but not on filesystem.
        ACTION: Call get_project_documents().
        ASSERTION: Returns documents from DB regardless of filesystem state.
        
        This test verifies we're following the metadata-first architecture.
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from database.models import DocumentModel, DocumentStatus
        from models.project import Base, Project
        from services.document_service import DocumentService
        
        # Setup
        engine = create_async_engine(temp_db_path, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        project_id = uuid4()
        
        async with session_factory() as session:
            project = Project(
                project_id=project_id,
                name=f"Test Project {project_id.hex[:8]}",
                description="Test project"
            )
            session.add(project)
            await session.flush()
            
            # Create documents with NON-EXISTENT file paths
            # This should NOT matter for get_project_documents
            for i in range(3):
                doc = DocumentModel(
                    project_id=project_id,
                    filename=f"doc_{i}.txt",
                    file_path=f"/nonexistent/path/doc_{i}.txt",
                    status=DocumentStatus.READY,
                )
                session.add(doc)
            await session.commit()
        
        # ACTION: Query documents
        async with session_factory() as session:
            service = DocumentService.from_session(session)
            docs = await service.get_project_documents(project_id)
        
        # ASSERTION: Should return 3 documents even though files don't exist
        assert len(docs) == 3, (
            f"Should return all 3 documents from DB, got {len(docs)}"
        )
        
        # Cleanup
        await engine.dispose()
        
        print("PASS: get_project_documents queries DB, not filesystem")

    @pytest.mark.asyncio
    async def test_get_project_documents_sorted_by_created_at_desc(self, temp_db_path):
        """
        Verify documents are returned sorted by created_at DESC.
        """
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from database.models import DocumentModel, DocumentStatus
        from models.project import Base, Project
        from services.document_service import DocumentService
        from datetime import datetime, timedelta
        
        # Setup
        engine = create_async_engine(temp_db_path, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        project_id = uuid4()
        
        # Use explicit timestamps with clear ordering
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        
        async with session_factory() as session:
            project = Project(
                project_id=project_id,
                name=f"Test Project {project_id.hex[:8]}",
                description="Test project"
            )
            session.add(project)
            await session.flush()
            
            # Create documents with explicit, distinct timestamps
            # first.txt is oldest, third.txt is newest
            docs_data = [
                ("first.txt", base_time),
                ("second.txt", base_time + timedelta(hours=1)),
                ("third.txt", base_time + timedelta(hours=2)),
            ]
            
            for filename, created_at in docs_data:
                doc = DocumentModel(
                    project_id=project_id,
                    filename=filename,
                    file_path=f"/path/{filename}",
                    status=DocumentStatus.READY,
                    created_at=created_at,  # Explicit timestamp
                )
                session.add(doc)
            
            await session.commit()
        
        # ACTION: Query documents
        async with session_factory() as session:
            service = DocumentService.from_session(session)
            docs = await service.get_project_documents(project_id)
        
        # ASSERTION: Documents should be in reverse creation order (newest first)
        assert len(docs) == 3
        assert docs[0].filename == "third.txt", f"Newest document should be first, got {docs[0].filename}"
        assert docs[1].filename == "second.txt", f"Second newest should be second, got {docs[1].filename}"
        assert docs[2].filename == "first.txt", f"Oldest document should be last, got {docs[2].filename}"
        
        # Cleanup
        await engine.dispose()
        
        print("PASS: get_project_documents returns documents sorted by created_at DESC")


# =============================================================================
# Standalone Verifier Script Section
# =============================================================================

if __name__ == "__main__":
    """
    Standalone verifier script for the Autonomous Engineering Protocol.
    
    Run this directly to verify the implementation:
        python test_persistence.py
    
    Exit codes:
        0 = All tests passed
        1 = Tests failed
    """
    import asyncio
    
    async def run_verifier():
        """Run the critical mutation test as a standalone verifier."""
        import tempfile
        from pathlib import Path
        
        # Setup
        temp_dir = tempfile.mkdtemp()
        db_path = f"sqlite+aiosqlite:///{temp_dir}/test.db"
        
        # Create a temp file
        temp_file = Path(temp_dir) / "test_doc.txt"
        temp_file.write_text("Test content")
        
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
            from database.models import DocumentModel, DocumentStatus
            from models.project import Base, Project
            from services.document_service import DocumentService
            
            # Create database
            engine = create_async_engine(db_path, echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            
            # Create test data
            project_id = uuid4()
            doc_id = uuid4()
            
            async with session_factory() as session:
                project = Project(
                    project_id=project_id,
                    name="Verifier Project",
                    description="Verifier test"
                )
                session.add(project)
                await session.flush()
                
                doc = DocumentModel(
                    id=doc_id,
                    project_id=project_id,
                    filename="verifier_test.txt",
                    file_path=str(temp_file),
                    status=DocumentStatus.READY,
                )
                session.add(doc)
                await session.commit()
            
            # DELETE the physical file
            temp_file.unlink()
            
            # Run consistency check
            async with session_factory() as session:
                service = DocumentService.from_session(session)
                stats = await service.sync_storage_consistency()
                await session.commit()
            
            # Verify
            async with session_factory() as session:
                from sqlalchemy import select
                stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
                
                if doc.status != DocumentStatus.FAILED:
                    print(f"FAIL: Expected status FAILED, got {doc.status.value}")
                    return 1
                
                if "Data Corruption" not in (doc.error_message or ""):
                    print(f"FAIL: Expected 'Data Corruption' in error, got {doc.error_message}")
                    return 1
            
            await engine.dispose()
            print("PASS: Verifier completed successfully")
            return 0
            
        except Exception as e:
            print(f"FAIL: Verifier error: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    exit_code = asyncio.run(run_verifier())
    sys.exit(exit_code)
