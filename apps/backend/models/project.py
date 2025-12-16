"""
Project Models
==============
SQLAlchemy models for multi-tenancy support.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


class Project(Base):
    """
    Project model for multi-tenancy.
    
    Each project represents an isolated workspace with its own documents.
    """
    __tablename__ = "projects"
    
    project_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to documents
    documents = relationship("ProjectDocument", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.project_id}, name='{self.name}')>"


class ProjectDocument(Base):
    """
    Association table linking projects to documents.
    
    This allows documents to belong to specific projects for isolation.
    """
    __tablename__ = "project_documents"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(PGUUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False)
    doc_id = Column(String(255), nullable=False)  # UUID stored as string (matches Milvus)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to project
    project = relationship("Project", back_populates="documents")
    
    def __repr__(self):
        return f"<ProjectDocument(project_id={self.project_id}, doc_id={self.doc_id})>"


# Pydantic schemas for API validation
class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ProjectResponse(BaseModel):
    """Response schema for project details."""
    project_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    document_count: int = Field(default=0, description="Number of documents in project")
    
    class Config:
        from_attributes = True


class ProjectDocumentResponse(BaseModel):
    """Response schema for project document association."""
    project_id: UUID
    doc_id: str
    added_at: datetime
    
    class Config:
        from_attributes = True
