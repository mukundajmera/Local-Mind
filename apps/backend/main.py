"""
Sovereign Cognitive Engine - Orchestrator Service
=================================================
Central API gateway coordinating all cognitive services.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
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
from logging_config import configure_logging, get_logger
import structlog
from exceptions import (
    LocalMindBaseException,
    DatabaseConnectionError,
    IngestionError,
    LLMServiceError,
    SearchError,
    ValidationError,
)
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


@app.post("/api/v1/sources/upload")
async def upload_source(file: UploadFile = File(...)):
    """Upload and ingest a document source."""
    # Save file to temp
    import shutil
    import tempfile
    from pathlib import Path
    from services.ingestion import IngestionPipeline
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    
    # Track file type for metrics
    file_type = tmp_path.suffix.lower().lstrip(".") or "unknown"
    app_metrics.ingestion_attempts_total.labels(file_type=file_type).inc()
    
    start_time = time.time()
    
    try:
        async with IngestionPipeline() as pipeline:
            doc = await pipeline.ingest_document(tmp_path)
        
        duration = time.time() - start_time
        app_metrics.ingestion_duration_seconds.labels(file_type=file_type).observe(duration)
        
        return {
            "status": "success",
            "doc_id": str(doc.doc_id),
            "filename": doc.filename,
            "chunks_created": 0, # TODO: Get from result - nice to have
            "entities_extracted": 0 
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
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


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



class ChatRequest(BaseModel):
    message: str
    context_node_ids: List[str] = []
    strategies: List[str] = []


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """Conversational interface with the knowledge base."""
    try:
        context_text = ""
        sources = []
        
        # 1. Retrieve Context if enabled
        if "insight" in request.strategies or "sources" in request.strategies:
            try:
                async with HybridRetriever() as retriever:
                    # If we have focused nodes, we can use them to guide search (future)
                    # For now, just search with the query
                    results = await retriever.search(request.message, k=5)
                    
                    if results.results:
                        context_text = "\n\n".join([
                            f"Source (ID: {r.chunk_id}): {r.text}" 
                            for r in results.results
                        ])
                        # Collect sources for citation
                        sources = [
                            {"id": r.chunk_id, "score": r.score, "source": r.source}
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
            "context_used": bool(context_text)
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
