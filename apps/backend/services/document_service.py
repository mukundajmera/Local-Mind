"""
Document Service
================
Database-centric document operations for the stateless architecture.
The database is the source of truth, not the filesystem.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

# Support both package imports and test imports (where backend is added to sys.path)
try:
    from database.models import DocumentModel, DocumentStatus
except ImportError:
    from ..database.models import DocumentModel, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Database-centric document operations for the metadata-first architecture.
    
    This service provides CRUD operations for document records and implements
    self-healing consistency checks between the database and filesystem.
    
    Usage:
        async with DocumentService(db_url) as service:
            docs = await service.get_project_documents(project_id)
    
    Or with an existing session:
        service = DocumentService.from_session(session)
        docs = await service.get_project_documents(project_id)
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the Document Service.
        
        Args:
            database_url: SQLAlchemy async database URL.
                         If None, uses environment variable DATABASE_URL.
        """
        self._database_url = database_url or os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./data/localmind.db"
        )
        self._engine = None
        self._session_factory = None
        self._session: Optional[AsyncSession] = None
        self._owns_session = True
    
    @classmethod
    def from_session(cls, session: AsyncSession) -> "DocumentService":
        """
        Create a DocumentService using an existing session.
        
        Use this when you need to participate in an external transaction.
        
        Args:
            session: An existing async SQLAlchemy session.
        
        Returns:
            DocumentService instance using the provided session.
        """
        instance = cls.__new__(cls)
        instance._session = session
        instance._owns_session = False
        instance._engine = None
        instance._session_factory = None
        return instance
    
    async def __aenter__(self) -> "DocumentService":
        """Async context manager entry."""
        if self._owns_session:
            self._engine = create_async_engine(
                self._database_url,
                echo=False,
            )
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            self._session = self._session_factory()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with proper cleanup."""
        if self._owns_session and self._session:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
            await self._session.close()
        
        if self._engine:
            await self._engine.dispose()
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    async def get_project_documents(
        self,
        project_id: UUID,
        include_failed: bool = False,
    ) -> List[DocumentModel]:
        """
        Query documents for a project from the database.
        
        This method queries the DB, NOT os.listdir, as per the 
        metadata-first architecture.
        
        Args:
            project_id: The project UUID to filter documents.
            include_failed: Whether to include FAILED status documents.
        
        Returns:
            List of DocumentModel objects, sorted by created_at DESC.
        """
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.project_id == project_id)
        )
        
        if not include_failed:
            stmt = stmt.where(DocumentModel.status != DocumentStatus.FAILED)
        
        stmt = stmt.order_by(DocumentModel.created_at.desc())
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_document_by_id(self, doc_id: UUID) -> Optional[DocumentModel]:
        """
        Retrieve a single document by its ID.
        
        Args:
            doc_id: The document UUID.
        
        Returns:
            DocumentModel if found, None otherwise.
        """
        stmt = select(DocumentModel).where(DocumentModel.id == doc_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_document_record(
        self,
        project_id: UUID,
        filename: str,
        file_path: str,
    ) -> DocumentModel:
        """
        Create a PENDING document record before file processing.
        
        This is called FIRST in the ingestion pipeline, before any
        processing begins, to ensure the database is the source of truth.
        
        Args:
            project_id: The parent project UUID.
            filename: Original filename as uploaded.
            file_path: Absolute path where file is stored.
        
        Returns:
            The created DocumentModel with status=PENDING.
        """
        doc = DocumentModel(
            project_id=project_id,
            filename=filename,
            file_path=file_path,
            status=DocumentStatus.PENDING,
        )
        
        self._session.add(doc)
        await self._session.flush()  # Get the generated ID
        
        logger.info(
            f"Created document record: id={doc.id}, "
            f"filename={filename}, status=PENDING"
        )
        
        return doc
    
    async def update_document_status(
        self,
        doc_id: UUID,
        status: DocumentStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update document status with optional error tracking.
        
        Args:
            doc_id: The document UUID to update.
            status: New DocumentStatus value.
            error_message: Optional error message (for FAILED status).
        
        Returns:
            True if document was found and updated, False otherwise.
        """
        values: Dict[str, Any] = {"status": status}
        
        if error_message is not None:
            values["error_message"] = error_message
        
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == doc_id)
            .values(**values)
        )
        
        result = await self._session.execute(stmt)
        
        if result.rowcount > 0:
            logger.info(
                f"Updated document status: id={doc_id}, "
                f"status={status.value}, error={error_message}"
            )
            return True
        
        logger.warning(f"Document not found for status update: id={doc_id}")
        return False
    
    async def update_document_briefing(
        self,
        doc_id: UUID,
        summary: str,
        topics: list[str],
        suggested_questions: list[str],
    ) -> bool:
        """
        Update document with AI-generated briefing metadata.
        
        Args:
            doc_id: The document UUID.
            summary: Generated summary text.
            topics: List of key topics.
            suggested_questions: List of suggested questions.
            
        Returns:
            True if updated, False otherwise.
        """
        # Convert lists to JSON-compatible format (if DB doesn't support JSON, use json.dumps)
        # SQLAlchemy JSON type handles serialization if supported, or we assume it is allowed.
        # But wait, SQLite might not.
        # Safest to just rely on SQLAlchemy JSON type we defined in models.
        
        values = {
            "summary": summary,
            "topics": topics,
            "suggested_questions": suggested_questions,
        }
        
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == doc_id)
            .values(**values)
        )
        
        result = await self._session.execute(stmt)
        
        if result.rowcount > 0:
            logger.info(f"Updated document briefing: id={doc_id}")
            return True
            
        logger.warning(f"Document not found for briefing update: id={doc_id}")
        return False
    
    async def delete_document_record(self, doc_id: UUID) -> bool:
        """
        Delete a document record from the database.
        
        Args:
            doc_id: The document UUID to delete.
        
        Returns:
            True if document was found and deleted, False otherwise.
        """
        doc = await self.get_document_by_id(doc_id)
        if doc:
            await self._session.delete(doc)
            logger.info(f"Deleted document record: id={doc_id}")
            return True
        return False
    
    # =========================================================================
    # Consistency Check (Self-Healing)
    # =========================================================================
    
    async def sync_storage_consistency(self) -> Dict[str, Any]:
        """
        Self-healing consistency check between database and filesystem.
        
        Queries all documents that are not already FAILED and checks if
        the physical file exists. If missing, marks the record as FAILED
        with an appropriate error message.
        
        This method:
        1. Queries all documents with status != FAILED
        2. Checks if os.path.exists(doc.file_path)
        3. If missing: marks status=FAILED, error_message="Data Corruption: File missing"
        4. Logs a warning but does NOT crash
        
        Returns:
            Dict with statistics:
            - checked: Total documents checked
            - healthy: Documents with existing files
            - corrupted: Documents marked as FAILED
            - errors: List of error details
        """
        stats = {
            "checked": 0,
            "healthy": 0,
            "corrupted": 0,
            "errors": [],
        }
        
        # Query all non-failed documents
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.status != DocumentStatus.FAILED)
        )
        
        result = await self._session.execute(stmt)
        documents = list(result.scalars().all())
        
        stats["checked"] = len(documents)
        
        for doc in documents:
            try:
                if not os.path.exists(doc.file_path):
                    # File is missing - mark as FAILED
                    error_msg = "Data Corruption: File missing"
                    
                    doc.status = DocumentStatus.FAILED
                    doc.error_message = error_msg
                    
                    stats["corrupted"] += 1
                    stats["errors"].append({
                        "doc_id": str(doc.id),
                        "filename": doc.filename,
                        "file_path": doc.file_path,
                        "error": error_msg,
                    })
                    
                    logger.warning(
                        f"Storage consistency check failed: "
                        f"doc_id={doc.id}, file_path={doc.file_path}, "
                        f"error={error_msg}"
                    )
                else:
                    stats["healthy"] += 1
                    
            except Exception as e:
                # Log but don't crash
                error_msg = f"Error checking file: {str(e)}"
                logger.error(
                    f"Storage consistency check error: "
                    f"doc_id={doc.id}, error={error_msg}"
                )
                stats["errors"].append({
                    "doc_id": str(doc.id),
                    "filename": doc.filename,
                    "error": error_msg,
                })
        
        # Commit the changes
        await self._session.flush()
        
        logger.info(
            f"Storage consistency check complete: "
            f"checked={stats['checked']}, healthy={stats['healthy']}, "
            f"corrupted={stats['corrupted']}"
        )
        
        return stats
    
    async def rescue_stuck_documents(self, max_age_minutes: int = 30) -> Dict[str, Any]:
        """
        Rescue documents stuck in PENDING or PROCESSING state.
        
        This should be called at startup to handle documents that were
        being processed when the server crashed or was restarted.
        
        Documents that have been stuck for longer than max_age_minutes
        will be marked as FAILED if their file doesn't exist, or
        reset to PENDING for retry if the file exists.
        
        Args:
            max_age_minutes: How long a document can be stuck before rescue.
        
        Returns:
            Statistics about rescued documents.
        """
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        
        stats = {
            "checked": 0,
            "rescued_to_failed": 0,
            "rescued_to_pending": 0,
            "still_valid": 0,
            "errors": [],
        }
        
        # Find stuck documents (PENDING or PROCESSING older than cutoff)
        stmt = (
            select(DocumentModel)
            .where(
                DocumentModel.status.in_([
                    DocumentStatus.PENDING,
                    DocumentStatus.PROCESSING
                ])
            )
            .where(DocumentModel.created_at < cutoff_time)
        )
        
        result = await self._session.execute(stmt)
        stuck_docs = result.scalars().all()
        
        for doc in stuck_docs:
            stats["checked"] += 1
            
            try:
                file_exists = Path(doc.file_path).exists() if doc.file_path else False
                
                if not file_exists:
                    # File doesn't exist - mark as FAILED (phantom document)
                    doc.status = DocumentStatus.FAILED
                    doc.error_message = (
                        f"File not found after server restart. "
                        f"Document was stuck in {doc.status.value} state."
                    )
                    stats["rescued_to_failed"] += 1
                    logger.warning(
                        f"Rescued phantom document to FAILED: id={doc.id}, "
                        f"filename={doc.filename}"
                    )
                else:
                    # File exists - could retry, but safer to mark failed
                    # (we don't know if partial processing occurred)
                    doc.status = DocumentStatus.FAILED
                    doc.error_message = (
                        f"Processing interrupted by server restart. "
                        f"Please re-upload the document."
                    )
                    stats["rescued_to_failed"] += 1
                    logger.warning(
                        f"Rescued stuck document to FAILED: id={doc.id}, "
                        f"filename={doc.filename}"
                    )
                    
            except Exception as e:
                error_msg = f"Failed to rescue document: {str(e)}"
                logger.error(f"{error_msg} - doc_id={doc.id}")
                stats["errors"].append({
                    "doc_id": str(doc.id),
                    "filename": doc.filename,
                    "error": error_msg,
                })
        
        # Commit the changes
        await self._session.flush()
        
        logger.info(
            f"Document rescue complete: "
            f"checked={stats['checked']}, rescued={stats['rescued_to_failed']}"
        )
        
        return stats
