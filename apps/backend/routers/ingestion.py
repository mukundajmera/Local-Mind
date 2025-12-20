"""
Ingestion Router
================
FastAPI router for document upload and ingestion with async background processing.

Implements the Write-Ahead Log pattern:
1. Generate UUID
2. Write to DB (status=PENDING)
3. Commit
4. Write to disk
5. Queue background task
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, Form
from pydantic import BaseModel

from config import get_settings
from database.models import DocumentStatus
from services.document_service import DocumentService
from services.ingestion import IngestionPipeline
from services.briefing_service import BriefingService
from schemas import BriefingResponse
import metrics as app_metrics

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class UploadResponse(BaseModel):
    """Response from document upload endpoint."""
    id: str
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    """Response from document status endpoint."""
    id: str
    project_id: str
    filename: str
    file_path: str
    status: str
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


# =============================================================================
# Background Worker
# =============================================================================

async def _process_document_background(
    doc_id: UUID,
    file_path: Path,
    project_id: Optional[UUID] = None
):
    """
    Background task to process document upload with DB status tracking.
    
    Updates the DocumentModel status as processing progresses:
    - PENDING → PROCESSING (start)
    - PROCESSING → READY (success)
    - * → FAILED (error)
    
    Args:
        doc_id: Document UUID (already created in DB)
        file_path: Path to uploaded file
        project_id: Optional project UUID
    """
    file_type = file_path.suffix.lower().lstrip(".") or "unknown"
    app_metrics.ingestion_attempts_total.labels(file_type=file_type).inc()
    start_time = time.time()
    
    try:
        # Update status: PENDING → PROCESSING
        async with DocumentService() as doc_service:
            await doc_service.update_document_status(
                doc_id,
                DocumentStatus.PROCESSING
            )
        
        logger.info(f"Starting ingestion for doc_id={doc_id}")
        
        # Run ingestion pipeline
        async with IngestionPipeline() as pipeline:
            ingested_doc, full_text = await pipeline.ingest_document(file_path, project_id=project_id)
        
        duration = time.time() - start_time
        app_metrics.ingestion_duration_seconds.labels(file_type=file_type).observe(duration)
        
        
        # NOTE: We do NOT set READY here anymore. We wait until briefing is done.
        logger.info(
            f"Ingestion pipeline completed for doc_id={doc_id}, "
            f"duration={duration:.2f}s"
        )

        # Trigger Briefing Agent
        try:
            logger.info(f"Triggering Briefing Agent for doc_id={doc_id}")
            briefing_service = BriefingService()
            briefing = await briefing_service.generate_briefing(str(doc_id), full_text)
            
            # Persist briefing to DB
            async with DocumentService() as doc_service:
                await doc_service.update_document_briefing(
                    doc_id,
                    summary=briefing.summary,
                    topics=briefing.key_topics,
                    suggested_questions=briefing.suggested_questions
                )
            logger.info(f"Briefing persisted for doc_id={doc_id}")
            
        except Exception as e:
            logger.error(f"Briefing generation failed for {doc_id} (non-blocking): {e}")
            # We don't fail the whole document if briefing fails, just log it.

        # Update status: PROCESSING → READY (Finally)
        async with DocumentService() as doc_service:
            await doc_service.update_document_status(
                doc_id,
                DocumentStatus.READY
            )
        logger.info(f"Document processing fully complete (READY) for doc_id={doc_id}")
        
    except Exception as e:
        # Update status: * → FAILED
        error_message = f"Ingestion failed: {str(e)}"
        
        async with DocumentService() as doc_service:
            await doc_service.update_document_status(
                doc_id,
                DocumentStatus.FAILED,
                error_message=error_message
            )
        
        app_metrics.ingestion_failures_total.labels(
            file_type=file_type,
            stage="ingestion"
        ).inc()
        
        logger.error(
            f"Ingestion failed for doc_id={doc_id}: {error_message}",
            exc_info=True
        )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/sources/upload", status_code=202, response_model=UploadResponse)
async def upload_source(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Upload and ingest a document source.
    
    Implements Write-Ahead Log pattern:
    1. Generate UUID
    2. Write to DB (status=PENDING)
    3. Commit
    4. Write file to disk
    5. Queue background processing
    
    Returns 202 Accepted immediately with document ID.
    Use GET /api/v1/sources/{doc_id}/status to track progress.
    
    Args:
        file: Uploaded file
        project_id: Optional project UUID
        background_tasks: FastAPI background tasks
    
    Returns:
        UploadResponse with document ID and status
    """
    settings = get_settings()
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Parse project_id if provided
    pid = UUID(project_id) if project_id else None
    
    # 1. Generate UUID
    doc_id = uuid4()
    
    # 2. Generate unique filename with timestamp
    timestamp = int(time.time())
    file_obj = Path(file.filename)
    safe_stem = file_obj.stem.replace(" ", "_")
    unique_filename = f"{safe_stem}_{timestamp}{file_obj.suffix}"
    file_path = upload_path / unique_filename
    
    try:
        # 3. Write to DB (status=PENDING) - BEFORE writing file
        async with DocumentService() as doc_service:
            # Create document record with explicit ID
            from database.models import DocumentModel
            doc = DocumentModel(
                id=doc_id,
                project_id=pid,
                filename=file.filename,
                file_path=str(file_path.absolute()),
                status=DocumentStatus.PENDING,
            )
            doc_service._session.add(doc)
            await doc_service._session.flush()
            # Commit happens in __aexit__
        
        logger.info(
            f"Created document record: id={doc_id}, "
            f"filename={file.filename}, status=PENDING"
        )
        
        # 4. Write file to disk
        try:
            with open(file_path, "wb") as dest:
                shutil.copyfileobj(file.file, dest)
        except Exception as e:
            # If file write fails, mark DB record as FAILED
            async with DocumentService() as doc_service:
                await doc_service.update_document_status(
                    doc_id,
                    DocumentStatus.FAILED,
                    error_message=f"Failed to save file: {str(e)}"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # 5. Queue background processing
        background_tasks.add_task(
            _process_document_background,
            doc_id,
            file_path,
            pid
        )
        
        return UploadResponse(
            id=str(doc_id),
            status="pending",
            message=f"Upload accepted. Poll /api/v1/sources/{doc_id}/status for progress."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/sources/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(doc_id: str):
    """
    Get the status of a document by ID.
    
    Queries the database for document status. Status values:
    - pending: Document record created, processing not started
    - processing: Ingestion pipeline is working
    - ready: Successfully processed and available for search
    - failed: Processing failed (check error_message)
    
    Args:
        doc_id: Document UUID
    
    Returns:
        DocumentStatusResponse with current status
    
    Raises:
        HTTPException: 404 if document not found
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document ID format: {doc_id}"
        )
    
    async with DocumentService() as doc_service:
        doc = await doc_service.get_document_by_id(doc_uuid)
    
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    return DocumentStatusResponse(
        id=str(doc.id),
        project_id=str(doc.project_id),
        filename=doc.filename,
        file_path=doc.file_path,
        status=doc.status.value,
        error_message=doc.error_message,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
    )


@router.get("/sources/{doc_id}/briefing", response_model=BriefingResponse)
async def get_document_briefing(doc_id: str):
    """
    Get the AI-generated briefing for a document.
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    async with DocumentService() as doc_service:
        doc = await doc_service.get_document_by_id(doc_uuid)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if not doc.summary:
        # If no summary in DB, try in-memory cache as fallback (legacy)
        # Or return 404/Processing
        raise HTTPException(status_code=404, detail="Briefing not found (might be processing)")

    # Construct response from DB columns
    # JSON columns are already deserialized by SQLAlchemy if defined as JSON
    # But if sqlite stores them as string, we might need json.loads IF SQLAlchemy didn't handle it.
    
    # We defined them as JSON type in models.py, so SQLAlchemy should return python objects (lists).
    # However, if using SQLite without specific support, it might return strings?
    # Let's handle both.
    import json
    
    topics = doc.topics
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = []
            
    questions = doc.suggested_questions
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except:
            questions = []

    return BriefingResponse(
        doc_id=str(doc.id),
        summary=doc.summary,
        key_topics=topics or [],
        suggested_questions=questions or [],
        generated_at=doc.updated_at or datetime.utcnow()
    )
