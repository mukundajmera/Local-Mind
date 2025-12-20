"""
Notes Router
============
REST API endpoints for notes management.

Endpoints:
- POST   /api/v1/notes           - Create note
- GET    /api/v1/notes           - List notes (with optional filters)
- GET    /api/v1/notes/tags      - Get all unique tags
- GET    /api/v1/notes/{id}      - Get single note
- PATCH  /api/v1/notes/{id}      - Update note
- DELETE /api/v1/notes/{id}      - Delete note
- POST   /api/v1/notes/{id}/pin  - Toggle pin status
"""

import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from schemas import (
    SavedNote,
    CreateNoteRequest,
    UpdateNoteRequest,
    NotesListResponse
)
from services.notes_service import get_notes_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=SavedNote)
async def create_note(request: CreateNoteRequest):
    """
    Create a new note.
    
    Notes can optionally:
    - Be associated with a project
    - Reference a source document for citation
    - Include tags for categorization
    """
    try:
        service = await get_notes_service()
        note = await service.create_note(request)
        logger.info(f"Created note {note.note_id}")
        return note
    except Exception as e:
        logger.error(f"Failed to create note: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create note: {str(e)}")


@router.get("", response_model=NotesListResponse)
async def list_notes(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    query: Optional[str] = Query(None, description="Search query for content/title"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by")
):
    """
    List all notes with optional filtering.
    
    Supports filtering by:
    - project_id: Only notes in this project
    - query: Full-text search in content and title
    - tags: Comma-separated list of tags to match
    
    Results are ordered by pin status (pinned first), then by creation date (newest first).
    """
    try:
        service = await get_notes_service()
        
        # Parse tags if provided
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        
        if query or tag_list:
            notes = await service.search_notes(
                query=query,
                tags=tag_list,
                project_id=project_id
            )
        else:
            notes = await service.get_all_notes(project_id=project_id)
        
        return NotesListResponse(
            notes=notes,
            total=len(notes),
            has_more=False  # No pagination for now
        )
    except Exception as e:
        logger.error(f"Failed to list notes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list notes: {str(e)}")


@router.get("/tags", response_model=List[str])
async def get_all_tags(
    project_id: Optional[str] = Query(None, description="Filter by project ID")
):
    """
    Get all unique tags across notes.
    
    Useful for displaying tag filter options in the UI.
    """
    try:
        service = await get_notes_service()
        tags = await service.get_all_tags(project_id=project_id)
        return tags
    except Exception as e:
        logger.error(f"Failed to get tags: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tags: {str(e)}")


@router.get("/{note_id}", response_model=SavedNote)
async def get_note(note_id: str):
    """
    Get a single note by ID.
    """
    try:
        service = await get_notes_service()
        note = await service.get_note_by_id(note_id)
        
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        return note
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get note: {str(e)}")


@router.patch("/{note_id}", response_model=SavedNote)
async def update_note(note_id: str, request: UpdateNoteRequest):
    """
    Update an existing note.
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    """
    try:
        service = await get_notes_service()
        note = await service.update_note(note_id, request)
        
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        logger.info(f"Updated note {note_id}")
        return note
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update note: {str(e)}")


@router.delete("/{note_id}")
async def delete_note(note_id: str):
    """
    Delete a note by ID.
    """
    try:
        service = await get_notes_service()
        deleted = await service.delete_note(note_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        logger.info(f"Deleted note {note_id}")
        return {"message": f"Note {note_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete note: {str(e)}")


@router.post("/{note_id}/pin", response_model=SavedNote)
async def toggle_pin(note_id: str):
    """
    Toggle the pin status of a note.
    
    Pinned notes appear at the top of lists.
    """
    try:
        service = await get_notes_service()
        note = await service.toggle_pin(note_id)
        
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        status = "pinned" if note.is_pinned else "unpinned"
        logger.info(f"Note {note_id} {status}")
        return note
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle pin for note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle pin: {str(e)}")
