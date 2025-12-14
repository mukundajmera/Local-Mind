"""
Sovereign Cognitive Engine - Orchestrator Service
=================================================
Central API gateway coordinating all cognitive services.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from config import Settings, get_settings
from typing import List, Optional
import os
import sys
from services.graph_analytics import GraphAnalytics
from services.search import HybridRetriever
from services.llm_factory import LLMService
from services.briefing_service import BriefingService
from services.notes_service import NotesService
from logging_config import configure_logging, get_logger
import structlog
import schemas
from exceptions import (
    LocalMindBaseException,
    DatabaseConnectionError,
    IngestionError,
    LLMServiceError,
    SearchError,
    ValidationError,
)
try:
    from .connection_pool import ConnectionPool
    from .circuit_breaker import CircuitBreakerOpenError
except ImportError:
    # Fallback for direct script execution
    from connection_pool import ConnectionPool
    from circuit_breaker import CircuitBreakerOpenError
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import metrics as app_metrics

# Will be configured in startup
logger = get_logger(__name__)

app = FastAPI(
    title="Sovereign Cognitive Engine",
    description="Local-first AI knowledge orchestrator",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://interface:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request Correlation Middleware
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject request ID into all logs for request tracing."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        
        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        
        # Add to request state for access within endpoints
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response


app.add_middleware(RequestIDMiddleware)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request metrics for observability."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Record metrics
        app_metrics.http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        app_metrics.http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response


app.add_middleware(MetricsMiddleware)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(LocalMindBaseException)
async def local_mind_exception_handler(request: Request, exc: LocalMindBaseException):
    """Handle all Local Mind custom exceptions with structured responses."""
    logger.error(
        f"LocalMind exception: {exc.message}",
        extra={"context": exc.context, "error_type": exc.__class__.__name__}
    )
    
    status_code = 500
    if isinstance(exc, ValidationError):
        status_code = 400
    elif isinstance(exc, DatabaseConnectionError):
        status_code = 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.to_dict(),
            "path": str(request.url.path),
        }
    )


@app.exception_handler(CircuitBreakerOpenError)
async def circuit_breaker_handler(request: Request, exc: CircuitBreakerOpenError):
    """Handle circuit breaker open errors with 503 Service Unavailable."""
    logger.warning(
        f"Circuit breaker open: {str(exc)}",
        extra={"path": str(request.url.path)}
    )
    
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "error_type": "ServiceUnavailable",
                "message": "Service temporarily unavailable due to repeated failures",
                "path": str(request.url.path),
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected exceptions."""
    logger.exception(
        f"Unexpected error: {str(exc)}",
        extra={"path": str(request.url.path)}
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "error_type": "InternalServerError",
                "message": "An unexpected error occurred",
                "path": str(request.url.path),
            }
        }
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for container orchestration.
    
    Returns 200 if all services are healthy, 503 if any critical service is down.
    """
    settings = get_settings()
    services = {}
    overall_healthy = True
    
    # Check connection pool health if available
    if connection_pool and connection_pool._initialized:
        try:
            pool_health = await connection_pool.health_check()
            
            # Neo4j
            services["neo4j"] = pool_health.get("neo4j", "unknown")
            if services["neo4j"] == "healthy":
                app_metrics.neo4j_is_healthy.set(1)
            else:
                app_metrics.neo4j_is_healthy.set(0)
                app_metrics.neo4j_connection_errors_total.inc()
                overall_healthy = False
            
            # Milvus
            services["milvus"] = pool_health.get("milvus", "unknown")
            if services["milvus"] == "healthy":
                app_metrics.milvus_is_healthy.set(1)
            else:
                app_metrics.milvus_is_healthy.set(0)
                app_metrics.milvus_connection_errors_total.inc()
                overall_healthy = False
                
        except Exception as e:
            logger.warning("Connection pool health check failed", error=str(e))
            services["neo4j"] = "unknown"
            services["milvus"] = "unknown"
            overall_healthy = False
    else:
        # Connection pool not initialized
        services["neo4j"] = "not_initialized"
        services["milvus"] = "not_initialized"
        overall_healthy = False
    
    # Check Redis (if configured)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.close()
        services["redis"] = "healthy"
        app_metrics.redis_is_healthy.set(1)
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        services["redis"] = "degraded"  # Non-critical
        app_metrics.redis_is_healthy.set(0)
    
    status_code = 200 if overall_healthy else 503
    
    response = HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        version="0.1.0",
        services=services
    )
    
    if not overall_healthy:
        raise HTTPException(status_code=503, detail=response.dict())
    
    return response


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Sovereign Cognitive Engine",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Global instances
graph_analytics: Optional[GraphAnalytics] = None
connection_pool: Optional[ConnectionPool] = None

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    
    # 1. Validate configuration
    try:
        settings = get_settings()
        logger.info("Configuration validated successfully")
    except Exception as e:
        logger.error("Configuration validation failed", error=str(e), exc_info=True)
        print(f"❌ Configuration validation failed: {e}", file=sys.stderr)
        print("Please check your .env file and ensure all required settings are present.", file=sys.stderr)
        sys.exit(1)
    
    # 2. Configure logging
    configure_logging(environment=settings.environment)
    
    logger.info(
        "Starting backend",
        environment=settings.environment,
        milvus_uri=settings.milvus_uri,
        neo4j_uri=settings.neo4j_uri,
    )
    
    # 3. Initialize connection pool
    try:
        global connection_pool
        connection_pool = await ConnectionPool.get_instance(settings)
        logger.info("Connection pool initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize connection pool", error=str(e), exc_info=True)
        print(f"❌ Failed to connect to databases: {e}", file=sys.stderr)
        print("Please ensure Neo4j and Milvus are running and accessible.", file=sys.stderr)
        # Don't exit - allow startup to continue with degraded functionality
        # Health checks will report the issue
    
    # 4. Initialize GraphAnalytics (for compatibility)
    try:
        global graph_analytics
        graph_analytics = GraphAnalytics()
        logger.info("GraphAnalytics initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize GraphAnalytics", error=str(e), exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down backend")
    
    # Close connection pool
    if connection_pool:
        try:
            await connection_pool.close()
            logger.info("Connection pool closed")
        except Exception as e:
            logger.error("Error closing connection pool", error=str(e))


# =============================================================================
# API V1 Endpoints
# =============================================================================

@app.get("/api/v1/sources")
async def list_sources():
    """List all ingested sources."""
    try:
        async with GraphAnalytics() as analytics:
            sources = await analytics.get_all_documents()
        return {"sources": sources}
    except Exception as e:
        logger.error(f"Failed to list sources: {e}", exc_info=True)
        # Return empty list for graceful degradation
        return {"sources": []}


@app.delete("/api/v1/sources/{doc_id}")
async def delete_source(doc_id: str):
    """
    Delete a document source and its associated data.
    
    Removes the document and all chunks from the knowledge graph.
    Entities are preserved as they may be referenced by other documents.
    """
    try:
        async with GraphAnalytics() as analytics:
            result = await analytics.delete_document(doc_id)
        
        if not result.get("found", True):
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete source {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


async def _generate_briefing_background(doc_id: str, file_path):
    """
    Background task to generate document briefing.
    
    This runs asynchronously after upload completes to avoid blocking the response.
    """
    try:
        logger.info(f"Starting background briefing generation for {doc_id}")
        
        # Read the document text
        from services.ingestion import DocumentParser
        from pathlib import Path
        
        file_path_obj = Path(file_path)
        if file_path_obj.suffix.lower() == ".pdf":
            text, _ = await DocumentParser.parse_pdf(file_path_obj)
        elif file_path_obj.suffix.lower() in [".md", ".txt", ".json", ".yaml", ".yml"]:
            text, _ = await DocumentParser.parse_text(file_path_obj)
        else:
            logger.warning(f"Unsupported file type for briefing: {file_path_obj.suffix}")
            return
        
        # Generate briefing
        async with BriefingService() as briefing_service:
            await briefing_service.generate_briefing(doc_id, text)
        
        logger.info(f"Briefing generation completed for {doc_id}")
        
    except Exception as e:
        logger.error(f"Background briefing generation failed for {doc_id}: {e}", exc_info=True)
        # Don't raise - this is a background task


@app.post("/api/v1/sources/upload")
async def upload_source(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Upload and ingest a document source.
    
    After successful ingestion, triggers automatic briefing generation in the background.
    """
    # Get settings for upload directory
    settings = get_settings()
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Save file to configured upload directory with unique filename
    import shutil
    from pathlib import Path
    from services.ingestion import IngestionPipeline
    
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = upload_path / unique_filename
    
    try:
        # Write uploaded file to storage
        with open(file_path, "wb") as dest:
            shutil.copyfileobj(file.file, dest)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Track file type for metrics
    file_type = file_path.suffix.lower().lstrip(".") or "unknown"
    app_metrics.ingestion_attempts_total.labels(file_type=file_type).inc()
    
    start_time = time.time()
    
    try:
        async with IngestionPipeline() as pipeline:
            doc = await pipeline.ingest_document(file_path)
        
        duration = time.time() - start_time
        app_metrics.ingestion_duration_seconds.labels(file_type=file_type).observe(duration)
        
        # Schedule briefing generation in background
        background_tasks.add_task(_generate_briefing_background, str(doc.doc_id), str(file_path))
        
        return {
            "status": "success",
            "doc_id": str(doc.doc_id),
            "filename": doc.filename,
            "chunks_created": 0, # TODO: Get from result - nice to have
            "entities_extracted": 0,
            "briefing_status": "generating"
        }
    except IngestionError as e:
        # Track failure stage
        stage = e.context.get("stage", "unknown")
        app_metrics.ingestion_failures_total.labels(
            file_type=file_type,
            stage=stage
        ).inc()
        raise e
    except Exception as e:
        # Wrap unexpected errors
        app_metrics.ingestion_failures_total.labels(
            file_type=file_type,
            stage="unknown"
        ).inc()
        raise IngestionError(
            message=f"Document ingestion failed: {str(e)}",
            filename=file.filename,
            stage="upload",
            original_error=e
        )
    # Note: We keep the file in upload_dir for reference/debugging
    # Add cleanup logic if storage becomes a concern


@app.get("/api/v1/graph")
async def get_graph():
    """Get knowledge graph data for visualization."""
    try:
        async with GraphAnalytics() as analytics:
            data = await analytics.get_graph_data(limit=1000)
        return data
    except Exception as e:
        logger.error(f"Failed to get graph: {e}", exc_info=True)
        # Return empty graph for graceful degradation
        return {"nodes": [], "links": []}



@app.post("/api/v1/chat")
async def chat(request: schemas.ChatRequest):
    """
    Conversational interface with the knowledge base.
    
    Supports source-filtered retrieval: if source_ids is provided,
    only searches within those documents (the "Notebook" experience).
    """
    try:
        context_text = ""
        sources = []
        
        # 1. Retrieve Context if enabled
        if "insight" in request.strategies or "sources" in request.strategies:
            try:
                async with HybridRetriever() as retriever:
                    # Search with optional source filtering
                    results = await retriever.search(
                        request.message, 
                        k=5,
                        source_ids=request.source_ids
                    )
                    
                    if results.results:
                        context_text = "\n\n".join([
                            f"Source (ID: {r.chunk_id}): {r.text}" 
                            for r in results.results
                        ])
                        # Collect sources for citation
                        sources = [
                            {
                                "id": r.chunk_id, 
                                "score": r.score, 
                                "source": r.source, 
                                "doc_id": getattr(r, 'doc_id', None)
                            }
                            for r in results.results
                        ]
            except Exception as e:
                logger.warning(f"Search failed, proceeding without context: {e}")
                # Continue without context rather than failing the whole request
        
        # 2. Generate Response
        try:
            async with LLMService() as llm:
                response = await llm.chat(
                    user_message=request.message,
                    context=context_text if context_text else None,
                    # history=... # TODO: Add history support
                )
        except Exception as e:
            raise LLMServiceError(
                message=f"LLM generation failed: {str(e)}",
                original_error=e
            )
            
        return {
            "response": response,
            "sources": sources,
            "context_used": bool(context_text),
            "filtered_sources": request.source_ids is not None
        }
            
    except LLMServiceError:
        # Re-raise custom errors
        raise
    except Exception as e:
        logger.exception(f"Chat request failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Chat failed: {str(e)}"
        )


# =============================================================================
# Notes API Endpoints
# =============================================================================

@app.post("/api/v1/notes", response_model=schemas.SavedNote)
async def create_note(request: schemas.CreateNoteRequest):
    """
    Create a new note.
    
    Notes can optionally reference a source chunk for citation.
    """
    try:
        async with NotesService() as notes_service:
            note = await notes_service.create_note(request)
        
        logger.info(f"Note created: {note.note_id}")
        return note
        
    except Exception as e:
        logger.error(f"Failed to create note: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create note: {str(e)}"
        )


@app.get("/api/v1/notes", response_model=List[schemas.SavedNote])
async def get_notes():
    """
    Retrieve all notes, ordered by creation date (newest first).
    
    Returns an empty list if no notes exist or on database errors.
    """
    try:
        async with NotesService() as notes_service:
            notes = await notes_service.get_all_notes()
        
        logger.debug(f"Retrieved {len(notes)} notes")
        return notes
        
    except Exception as e:
        logger.error(f"Failed to retrieve notes: {e}", exc_info=True)
        # Return empty list for graceful degradation
        return []


@app.get("/api/v1/notes/{note_id}", response_model=schemas.SavedNote)
async def get_note(note_id: str):
    """
    Retrieve a specific note by ID.
    """
    try:
        async with NotesService() as notes_service:
            note = await notes_service.get_note_by_id(note_id)
        
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        return note
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve note {note_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve note: {str(e)}"
        )


@app.delete("/api/v1/notes/{note_id}")
async def delete_note(note_id: str):
    """
    Delete a note by ID.
    """
    try:
        async with NotesService() as notes_service:
            deleted = await notes_service.delete_note(note_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        
        return {"status": "success", "note_id": note_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete note {note_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete note: {str(e)}"
        )


# =============================================================================
# Briefing API Endpoint
# =============================================================================

@app.get("/api/v1/sources/{doc_id}/briefing", response_model=schemas.BriefingResponse)
async def get_document_briefing(doc_id: str):
    """
    Retrieve the automated briefing for a document.
    
    Returns 404 if document doesn't exist or briefing hasn't been generated yet.
    """
    try:
        async with BriefingService() as briefing_service:
            briefing = await briefing_service.get_briefing(doc_id)
        
        if not briefing:
            raise HTTPException(
                status_code=404, 
                detail=f"Briefing not found for document {doc_id}. It may still be generating."
            )
        
        return briefing
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve briefing for {doc_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve briefing: {str(e)}"
        )
