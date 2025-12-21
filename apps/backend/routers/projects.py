"""
Projects Router
===============
API endpoints for project management (multi-tenancy).
Uses SQLAlchemy for database persistence.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from logging_config import get_logger
from models.project import ProjectCreate, ProjectResponse, Project, Base
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.models import DocumentModel, DocumentStatus
import os

logger = get_logger(__name__)

router = APIRouter()

# Database connection setup
_engine = None
_session_factory = None


async def get_db_session() -> AsyncSession:
    """Get a database session."""
    global _engine, _session_factory
    
    if _engine is None:
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/localmind.db")
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Ensure tables exist
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    return _session_factory()


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(request: ProjectCreate):
    """
    Create a new project.
    
    Projects provide isolated workspaces for documents.
    """
    session = await get_db_session()
    try:
        from uuid import uuid4
        from sqlalchemy.exc import IntegrityError
        
        project_id = uuid4()
        now = datetime.utcnow()
        
        project = Project(
            project_id=project_id,
            name=request.name,
            description=request.description,
            created_at=now,
            updated_at=now,
        )
        
        session.add(project)
        
        try:
            await session.commit()
        except IntegrityError:
            # Unique constraint violation - project name already exists
            await session.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Project with name '{request.name}' already exists"
            )
        
        await session.refresh(project)
        
        logger.info(f"Project created: {project_id} - {request.name}")
        
        return ProjectResponse(
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            document_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project: {str(e)}"
        )
    finally:
        await session.close()


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    """
    List all projects.
    
    Returns all projects with their metadata and document counts.
    """
    session = await get_db_session()
    try:
        # Get all projects
        stmt = select(Project)
        result = await session.execute(stmt)
        projects = result.scalars().all()
        
        # Get document counts for ALL projects in a single query (fixes N+1 problem)
        from sqlalchemy import case
        count_stmt = (
            select(
                DocumentModel.project_id,
                func.count(DocumentModel.id).label("doc_count")
            )
            .where(DocumentModel.status != DocumentStatus.FAILED)
            .group_by(DocumentModel.project_id)
        )
        count_result = await session.execute(count_stmt)
        
        # Build a lookup dict: project_id -> count
        doc_counts = {row.project_id: row.doc_count for row in count_result.fetchall()}
        
        responses = []
        for project in projects:
            responses.append(ProjectResponse(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
                document_count=doc_counts.get(project.project_id, 0)
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list projects: {str(e)}"
        )
    finally:
        await session.close()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID):
    """
    Get project details by ID.
    
    Returns project metadata and document count.
    """
    session = await get_db_session()
    try:
        stmt = select(Project).where(Project.project_id == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Count documents for this project
        count_stmt = (
            select(func.count(DocumentModel.id))
            .where(DocumentModel.project_id == project_id)
            .where(DocumentModel.status != DocumentStatus.FAILED)
        )
        count_result = await session.execute(count_stmt)
        doc_count = count_result.scalar() or 0
        
        return ProjectResponse(
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            document_count=doc_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project: {str(e)}"
        )
    finally:
        await session.close()


@router.delete("/{project_id}")
async def delete_project(project_id: UUID):
    """
    Delete a project and all its document associations.
    
    **Warning**: This does not delete the actual documents from Milvus,
    only the project-document associations.
    """
    session = await get_db_session()
    try:
        stmt = select(Project).where(Project.project_id == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        project_name = project.name
        
        # Delete project (cascade will handle related documents)
        await session.delete(project)
        await session.commit()
        
        logger.info(f"Project deleted: {project_id} - {project_name}")
        
        return {
            "status": "success",
            "project_id": str(project_id),
            "message": f"Project '{project_name}' deleted successfully"
        }
        
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )
    finally:
        await session.close()


@router.get("/{project_id}/documents", response_model=List[str])
async def get_project_documents(project_id: UUID):
    """
    Get all document IDs associated with a project.
    
    Returns a list of document IDs belonging to the specified project.
    """
    session = await get_db_session()
    try:
        # Check project exists
        proj_stmt = select(Project).where(Project.project_id == project_id)
        proj_result = await session.execute(proj_stmt)
        project = proj_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get document IDs
        doc_stmt = (
            select(DocumentModel.id)
            .where(DocumentModel.project_id == project_id)
            .where(DocumentModel.status != DocumentStatus.FAILED)
        )
        doc_result = await session.execute(doc_stmt)
        doc_ids = [str(row[0]) for row in doc_result.fetchall()]
        
        return doc_ids
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get documents for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project documents: {str(e)}"
        )
    finally:
        await session.close()


@router.post("/{project_id}/documents/{doc_id}")
async def add_document_to_project(project_id: UUID, doc_id: str):
    """
    Associate a document with a project.
    
    This endpoint is deprecated - documents are now associated with projects
    during upload via the project_id parameter.
    """
    session = await get_db_session()
    try:
        # Check project exists
        proj_stmt = select(Project).where(Project.project_id == project_id)
        proj_result = await session.execute(proj_stmt)
        project = proj_result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Update document's project_id if document exists
        from uuid import UUID as UUIDType
        try:
            doc_uuid = UUIDType(doc_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid document ID format")
        
        doc_stmt = select(DocumentModel).where(DocumentModel.id == doc_uuid)
        doc_result = await session.execute(doc_stmt)
        doc = doc_result.scalar_one_or_none()
        
        if doc:
            doc.project_id = project_id
            await session.commit()
            logger.info(f"Document {doc_id} added to project {project_id}")
        
        return {
            "status": "success",
            "project_id": str(project_id),
            "doc_id": doc_id,
            "message": "Document added to project"
        }
        
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to add document to project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add document to project: {str(e)}"
        )
    finally:
        await session.close()
