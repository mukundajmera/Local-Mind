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
from pathlib import Path
from services.search import HybridRetriever
from services.llm_factory import LLMService
from services.briefing_service import BriefingService
from services.notes_service import NotesService
from services.model_manager import ModelManager
from logging_config import configure_logging, get_logger
from routers import system_router, projects_router, ingestion_router, notes_router
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

# Register routers
app.include_router(system_router, prefix="/api/v1/system", tags=["system"])
app.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(ingestion_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(notes_router, prefix="/api/v1/notes", tags=["notes"])


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
    elif isinstance(exc, IngestionError) and exc.original_error:
        # Check if wrapped error is connection related
        error_msg = str(exc.original_error).lower()
        if "connection refused" in error_msg or "failed to connect" in error_msg or "fail connecting" in error_msg or "illegal connection params" in error_msg:
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
            
            # Milvus (primary vector store)
            services["milvus"] = pool_health.get("milvus", "unknown")
            if services["milvus"] == "healthy":
                app_metrics.milvus_is_healthy.set(1)
            else:
                app_metrics.milvus_is_healthy.set(0)
                app_metrics.milvus_connection_errors_total.inc()
                overall_healthy = False
                
        except Exception as e:
            logger.warning("Connection pool health check failed", error=str(e))
            services["milvus"] = "unknown"
            overall_healthy = False
    else:
        # Connection pool not initialized
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
    
    # 1.5. Ensure database directory exists
    try:
        # Create data directory for SQLite database
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory ensured: {data_dir.absolute()}")
        
        # Create upload directory
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory ensured: {upload_dir.absolute()}")
        
        # Initialize database tables
        from database.models import Base
        from sqlalchemy.ext.asyncio import create_async_engine
        
        # Use relative path for SQLite database
        db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/localmind.db")
        engine = create_async_engine(db_url, echo=False)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await engine.dispose()
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e), exc_info=True)
        print(f"⚠️  Database initialization failed: {e}", file=sys.stderr)
        # Don't exit - allow startup to continue
    
    # 2. Configure logging
    configure_logging(environment=settings.environment)
    
    logger.info(
        "Starting backend",
        environment=settings.environment,
        milvus_uri=settings.milvus_uri,
    )
    
    # 3. Initialize connection pool
    try:
        global connection_pool
        connection_pool = await ConnectionPool.get_instance(settings)
        logger.info("Connection pool initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize connection pool", error=str(e), exc_info=True)
        print(f"❌ Failed to connect to databases: {e}", file=sys.stderr)
        print("Please ensure Milvus is running and accessible.", file=sys.stderr)
        # Don't exit - allow startup to continue with degraded functionality
        # Health checks will report the issue
    
    # 4. Initialize ModelManager
    try:
        model_manager = ModelManager.get_instance()
        logger.info("ModelManager initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize ModelManager", error=str(e), exc_info=True)
        print(f"⚠️  ModelManager initialization failed: {e}", file=sys.stderr)


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
async def list_sources(project_id: Optional[str] = None):
    """
    List all ingested sources from Milvus.
    
    Args:
        project_id: Optional Project ID to filter sources
    """
    try:
        from services.ingestion import IngestionPipeline
        
        # Parse project_id if provided
        pid = uuid.UUID(project_id) if project_id else None
        
        async with IngestionPipeline() as pipeline:
            sources = await pipeline.get_all_sources(project_id=pid)
        return {"sources": sources}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project_id format")
    except Exception as e:
        logger.error(f"Failed to list sources: {e}", exc_info=True)
        # Return empty list for graceful degradation
        return {"sources": []}


@app.delete("/api/v1/sources/{doc_id}")
async def delete_source(doc_id: str):
    """
    Delete a document source and its associated data from Milvus.
    
    Removes the document and all chunks from the vector store.
    """
    try:
        from services.ingestion import IngestionPipeline
        async with IngestionPipeline() as pipeline:
            result = await pipeline.delete_document(doc_id)
        
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


# Note: Upload endpoints moved to routers/ingestion.py
# Old _process_upload_background and upload endpoints removed in favor of
# database-first Write-Ahead Log pattern




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
        except (LLMServiceError, Exception) as e:
            # Fallback for chat when LLM is offline
            logger.warning(f"LLM Chat failed (using fallback): {e}")
            response = (
                "⚠️ **LLM Service Offline**\n\n"
                "I am unable to generate a real response because the local AI service (Ollama) is not reachable or configured.\n\n"
                "**System info:**\n"
                f"- Context retrieved: {'Yes' if context_text else 'No'}\n"
                f"- Sources found: {len(sources)}\n"
                f"- Error: {str(e)}"
            )
            
        return {
            "response": response,
            "sources": sources,
            "context_used": bool(context_text),
            "filtered_sources": request.source_ids is not None,
            "searched_source_ids": request.source_ids,
        }
            
    except Exception as e:
        logger.exception(f"Chat request failed: {e}")
        # Even top-level failure shouldn't crash frontend info
        return {
            "response": "An critical error occurred in the chat service.",
            "sources": [],
            "context_used": False,
            "filtered_sources": False,
            "searched_source_ids": None,
        }


# =============================================================================
# Notes API Endpoints - DEPRECATED: Now handled by notes_router
# =============================================================================
# The notes endpoints have been moved to routers/notes.py with enhanced
# functionality including:
# - Project association
# - Search by content/tags
# - Pin/unpin capability
# - Update notes (PATCH)
# See /api/v1/notes/* endpoints registered via notes_router

