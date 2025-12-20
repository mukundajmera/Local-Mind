"""
Document Database Models
========================
SQLAlchemy models for the metadata-first persistence layer.
The database is the source of truth, not the filesystem.
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Index,
    func,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

# Import Base from existing models to ensure schema consistency
# Use try/except for both relative (package) and absolute (test) imports
try:
    from models.project import Base
except ImportError:
    from ..models.project import Base


class DocumentStatus(str, enum.Enum):
    """
    Document lifecycle status.
    
    PENDING: Record created, file saved, processing not started
    PROCESSING: Ingestion pipeline is working (chunking, embedding)
    READY: Successfully processed and available for search
    FAILED: Processing failed or file missing (data corruption)
    """
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentModel(Base):
    """
    Document metadata model for the metadata-first architecture.
    
    This model represents the source of truth for document state.
    The database record is created BEFORE processing, and status
    is updated as the ingestion pipeline progresses.
    
    Attributes:
        id: Unique document identifier (UUID)
        project_id: Foreign key to parent project
        filename: Original filename as uploaded
        file_path: Absolute path to stored file on disk
        status: Current document lifecycle state
        error_message: Error details if status is FAILED
        created_at: Server-side timestamp of record creation
        updated_at: Server-side timestamp of last update
    """
    __tablename__ = "documents"
    
    # Primary key
    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique document identifier"
    )
    
    # Foreign key to project (indexed for query performance)
    project_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.project_id"),
        nullable=False,
        index=True,
        doc="Parent project ID"
    )
    
    # File metadata
    filename = Column(
        String(512),
        nullable=False,
        doc="Original filename as uploaded"
    )
    
    file_path = Column(
        String(1024),
        nullable=False,
        doc="Absolute path to stored file on disk"
    )
    
    # Status tracking with explicit default
    status = Column(
        Enum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
        doc="Current document lifecycle state"
    )
    
    # Error tracking
    error_message = Column(
        Text,
        nullable=True,
        doc="Error details if status is FAILED"
    )

    # Briefing Metadata
    summary = Column(
        Text,
        nullable=True,
        doc="AI-generated summary"
    )
    
    topics = Column(
        JSON,
        nullable=True,
        doc="AI-extracted key topics"
    )
    
    suggested_questions = Column(
        JSON,
        nullable=True,
        doc="AI-suggested follow-up questions"
    )
    
    # Timestamps with server-side defaults for ACID compliance
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        doc="Server-side timestamp of record creation"
    )
    
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Server-side timestamp of last update"
    )
    
    # Relationship to project
    project = relationship("Project", backref="source_documents")
    
    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_documents_project_status", "project_id", "status"),
        Index("ix_documents_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DocumentModel("
            f"id={self.id}, "
            f"filename='{self.filename}', "
            f"status={self.status.value}"
            f")>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "filename": self.filename,
            "file_path": self.file_path,
            "status": self.status.value,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
