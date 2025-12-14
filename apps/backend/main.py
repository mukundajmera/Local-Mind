"""
Sovereign Cognitive Engine - Orchestrator Service
=================================================
Central API gateway coordinating all cognitive services.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from services.graph_analytics import GraphAnalytics
from services.search import HybridRetriever
from services.llm_factory import LLMService

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


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for container orchestration."""
    # TODO: Implement real DB checks
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services={
            "neo4j": "available",
            "milvus": "available", 
            "redis": "available",
        }
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Sovereign Cognitive Engine",
        "status": "operational",
        "docs": "/docs",
    }


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
        # Log error in production
        print(f"Error listing sources: {e}")
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
        
    try:
        async with IngestionPipeline() as pipeline:
            doc = await pipeline.ingest_document(tmp_path)
            
        return {
            "status": "success",
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "chunks_created": 0, # TODO: Get from result - nice to have
            "entities_extracted": 0 
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
        print(f"Error getting graph: {e}")
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
        
        # 2. Generate Response
        async with LLMService() as llm:
            response = await llm.chat(
                user_message=request.message,
                context=context_text if context_text else None,
                # history=... # TODO: Add history support
            )
            
        return {
            "response": response,
            "sources": sources,
            "context_used": bool(context_text)
        }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
