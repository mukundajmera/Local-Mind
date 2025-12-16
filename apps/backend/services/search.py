"""
Sovereign Cognitive Engine - Vector Search
===========================================
Pure vector similarity search using Milvus.
"""

import logging
from typing import Optional

from pymilvus import MilvusClient, MilvusException
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings, get_settings
from schemas import HybridSearchResponse, SearchResult

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Vector search for semantic similarity retrieval.
    
    Uses Milvus for fast vector search with optional source filtering.
    
    Example:
        ```python
        async with HybridRetriever() as retriever:
            results = await retriever.search("What is quantum entanglement?", k=10)
        ```
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize retriever with configuration."""
        self.settings = settings or get_settings()
        
        # Database client (initialized in __aenter__)
        self._milvus_client: Optional[MilvusClient] = None
        
        # Embedding service for query vectorization
        # Import here to avoid circular dependency
        from services.ingestion import EmbeddingService
        self.embedding_service = EmbeddingService(self.settings.embedding_model)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._milvus_client = MilvusClient(uri=self.settings.milvus_uri)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._milvus_client:
            self._milvus_client.close()
    
    async def search(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 1.0,
        graph_weight: float = 0.0,  # Kept for API compatibility
        source_ids: Optional[list[str]] = None,
    ) -> HybridSearchResponse:
        """
        Perform vector search for semantically similar chunks.
        
        Args:
            query: Natural language search query
            k: Number of results to return
            vector_weight: Weight for vector results (default 1.0)
            graph_weight: Deprecated, kept for API compatibility
            source_ids: Optional list of document IDs to filter search
            
        Returns:
            HybridSearchResponse with ranked results
        """
        filter_msg = f" (filtered to {len(source_ids)} sources)" if source_ids else ""
        logger.info(f"Vector search: '{query[:50]}...' k={k}{filter_msg}")
        
        # Vector search
        vector_results = await self._vector_search(query, limit=k, source_ids=source_ids)
        
        return HybridSearchResponse(
            query=query,
            results=vector_results,
            vector_count=len(vector_results),
            graph_count=0,  # No graph search
            total_fused=len(vector_results),
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _vector_search(
        self, 
        query: str, 
        limit: int,
        source_ids: Optional[list[str]] = None
    ) -> list[SearchResult]:
        """
        Search Milvus for semantically similar chunks.
        
        Args:
            query: Search query (will be embedded)
            limit: Maximum results to return
            source_ids: Optional list of document IDs to filter by
            
        Returns:
            List of SearchResult ordered by similarity (descending)
        """
        try:
            # Embed the query
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Build filter expression if source_ids provided
            filter_expr = None
            if source_ids:
                # Validate source_ids are valid UUIDs or strings (basic validation)
                # Milvus filter syntax: doc_id in ["id1", "id2", ...]
                # Use proper escaping to prevent injection
                import re
                validated_ids = []
                for sid in source_ids:
                    # Allow UUID format and alphanumeric with hyphens
                    if re.match(r'^[a-zA-Z0-9\-]+$', str(sid)):
                        validated_ids.append(str(sid))
                    else:
                        logger.warning(f"Skipping invalid source_id: {sid}")
                
                if validated_ids:
                    escaped_ids = [f'"{sid}"' for sid in validated_ids]
                    filter_expr = f"doc_id in [{', '.join(escaped_ids)}]"
                    logger.debug(f"Applying Milvus filter: {filter_expr}")
            
            # Search Milvus
            search_results = self._milvus_client.search(
                collection_name=self.settings.milvus_collection,
                data=[query_embedding],
                anns_field="embedding",
                limit=limit,
                output_fields=["id", "doc_id", "text"],
                filter=filter_expr,
            )
            
            results = []
            for hits in search_results:
                for rank, hit in enumerate(hits):
                    results.append(SearchResult(
                        chunk_id=hit["id"],
                        text=hit["entity"].get("text", ""),
                        score=float(hit["distance"]),  # Cosine similarity
                        source="vector",
                        doc_id=hit["entity"].get("doc_id"),
                        metadata={"rank": rank, "distance": hit["distance"]},
                    ))
            
            logger.debug(f"Vector search returned {len(results)} results")
            return results
            
        except MilvusException as e:
            logger.error(f"Milvus search failed: {e}")
            return []
    
    def _handle_empty_search(self, query: str) -> HybridSearchResponse:
        """Return empty response when no results found."""
        return HybridSearchResponse(
            query=query,
            results=[],
            vector_count=0,
            graph_count=0,
            total_fused=0,
        )
