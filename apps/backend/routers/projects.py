"""
Projects Router
===============
API endpoints for project management (multi-tenancy).
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from logging_config import get_logger
from models.project import ProjectCreate, ProjectResponse, ProjectDocumentResponse

logger = get_logger(__name__)

router = APIRouter()

# In-memory storage for now (replace with actual database in production)
# This is a simplified implementation for demonstration
_projects_store: dict[UUID, dict] = {}
_project_documents_store: dict[UUID, list[str]] = {}


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(request: ProjectCreate):
    """
    Create a new project.
    
    Projects provide isolated workspaces for documents.
    """
    try:
        from datetime import datetime
        from uuid import uuid4
        
        # Check if project name already exists
        for project in _projects_store.values():
            if project["name"] == request.name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project with name '{request.name}' already exists"
                )
        
        project_id = uuid4()
        now = datetime.utcnow()
        
        project_data = {
            "project_id": project_id,
            "name": request.name,
            "description": request.description,
            "created_at": now,
            "updated_at": now,
            "document_count": 0
        }
        
        _projects_store[project_id] = project_data
        _project_documents_store[project_id] = []
        
        logger.info(f"Project created: {project_id} - {request.name}")
        
        return ProjectResponse(**project_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project: {str(e)}"
        )


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    """
    List all projects.
    
    Returns all projects with their metadata and document counts.
    """
    try:
        projects = []
        for project_data in _projects_store.values():
            project_id = project_data["project_id"]
            doc_count = len(_project_documents_store.get(project_id, []))
            
            project_response = {
                **project_data,
                "document_count": doc_count
            }
            projects.append(ProjectResponse(**project_response))
        
        return projects
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list projects: {str(e)}"
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID):
    """
    Get project details by ID.
    
    Returns project metadata and document count.
    """
    try:
        if project_id not in _projects_store:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        project_data = _projects_store[project_id]
        doc_count = len(_project_documents_store.get(project_id, []))
        
        project_response = {
            **project_data,
            "document_count": doc_count
        }
        
        return ProjectResponse(**project_response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project: {str(e)}"
        )


@router.delete("/{project_id}")
async def delete_project(project_id: UUID):
    """
    Delete a project and all its document associations.
    
    **Warning**: This does not delete the actual documents from Milvus,
    only the project-document associations.
    """
    try:
        if project_id not in _projects_store:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        project_name = _projects_store[project_id]["name"]
        
        # Remove project and its document associations
        del _projects_store[project_id]
        if project_id in _project_documents_store:
            del _project_documents_store[project_id]
        
        logger.info(f"Project deleted: {project_id} - {project_name}")
        
        return {
            "status": "success",
            "project_id": str(project_id),
            "message": f"Project '{project_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )


@router.get("/{project_id}/documents", response_model=List[str])
async def get_project_documents(project_id: UUID):
    """
    Get all document IDs associated with a project.
    
    Returns a list of document IDs belonging to the specified project.
    """
    try:
        if project_id not in _projects_store:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        doc_ids = _project_documents_store.get(project_id, [])
        
        return doc_ids
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get documents for project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project documents: {str(e)}"
        )


@router.post("/{project_id}/documents/{doc_id}")
async def add_document_to_project(project_id: UUID, doc_id: str):
    """
    Associate a document with a project.
    
    This creates the project-document link for isolation.
    """
    try:
        if project_id not in _projects_store:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        if project_id not in _project_documents_store:
            _project_documents_store[project_id] = []
        
        if doc_id not in _project_documents_store[project_id]:
            _project_documents_store[project_id].append(doc_id)
            logger.info(f"Document {doc_id} added to project {project_id}")
        
        return {
            "status": "success",
            "project_id": str(project_id),
            "doc_id": doc_id,
            "message": "Document added to project"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add document to project: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add document to project: {str(e)}"
        )
