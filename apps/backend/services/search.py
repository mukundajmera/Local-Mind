"""
Sovereign Cognitive Engine - Hybrid Search
===========================================
Reciprocal Rank Fusion (RRF) combining vector and graph retrieval.
"""

import logging
from collections import defaultdict
from typing import Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError
from pymilvus import MilvusClient, MilvusException
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings, get_settings
from schemas import HybridSearchResponse, SearchResult

logger = logging.getLogger(__name__)


# RRF constant (standard value from the original paper)
RRF_K = 60


class HybridRetriever:
    """
    Hybrid search combining vector similarity and knowledge graph traversal.
    
    Uses Reciprocal Rank Fusion (RRF) to merge ranked lists from both sources.
    
    Example:
        ```python
        async with HybridRetriever() as retriever:
            results = await retriever.search("What is quantum entanglement?", k=10)
        ```
    
    References:
        - RRF Paper: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize retriever with configuration."""
        self.settings = settings or get_settings()
        
        # Database clients (initialized in __aenter__)
        self._neo4j_driver: Optional[AsyncDriver] = None
        self._milvus_client: Optional[MilvusClient] = None
        
        # Embedding service for query vectorization
        # Import here to avoid circular dependency
        from services.ingestion import EmbeddingService
        self.embedding_service = EmbeddingService(self.settings.embedding_model)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        self._milvus_client = MilvusClient(uri=self.settings.milvus_uri)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
        if self._milvus_client:
            self._milvus_client.close()
    
    async def search(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 0.5,
        graph_weight: float = 0.5,
    ) -> HybridSearchResponse:
        """
        Perform hybrid search combining vector and graph retrieval.
        
        Args:
            query: Natural language search query
            k: Number of results to return
            vector_weight: Weight for vector branch in fusion (0-1)
            graph_weight: Weight for graph branch in fusion (0-1)
            
        Returns:
            HybridSearchResponse with ranked, deduplicated results
        """
        logger.info(f"Hybrid search: '{query[:50]}...' k={k}")
        
        # 1. Vector branch: semantic similarity search
        vector_results = await self._vector_search(query, limit=k * 2)
        
        # 2. Graph branch: entity-based traversal
        graph_results = await self._graph_search(query, limit=k * 2)
        
        # 3. Fuse results using RRF
        fused_results = self._rrf_fuse(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=k,
        )
        
        return HybridSearchResponse(
            query=query,
            results=fused_results,
            vector_count=len(vector_results),
            graph_count=len(graph_results),
            total_fused=len(fused_results),
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _vector_search(self, query: str, limit: int) -> list[SearchResult]:
        """
        Search Milvus for semantically similar chunks.
        
        Args:
            query: Search query (will be embedded)
            limit: Maximum results to return
            
        Returns:
            List of SearchResult ordered by similarity (descending)
        """
        try:
            # Embed the query
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Search Milvus
            search_results = self._milvus_client.search(
                collection_name=self.settings.milvus_collection,
                data=[query_embedding],
                anns_field="embedding",
                limit=limit,
                output_fields=["id", "doc_id", "text"],
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _graph_search(self, query: str, limit: int) -> list[SearchResult]:
        """
        Search Neo4j knowledge graph for related chunks.
        
        Strategy:
        1. Extract potential entity mentions from query
        2. Find matching Entity nodes
        3. Traverse 2-hop neighborhood to find related entities
        4. Return chunks that mention any of these entities
        
        Args:
            query: Search query (entities extracted via simple heuristics)
            limit: Maximum results to return
            
        Returns:
            List of SearchResult based on graph connectivity
        """
        if not self._neo4j_driver:
            return []
        
        try:
            async with self._neo4j_driver.session() as session:
                # Strategy: Use the query terms to find matching entities,
                # then traverse the graph to find related chunks.
                #
                # Cypher Query Explanation:
                # 1. MATCH entities whose name contains any query term (case-insensitive)
                # 2. OPTIONAL MATCH 1-hop related entities via any relationship
                # 3. OPTIONAL MATCH 2-hop related entities
                # 4. COLLECT all entities in neighborhood
                # 5. Find chunks that MENTION any of these entities
                # 6. Return distinct chunks with relevance score based on mention count
                
                result = await session.run(
                    """
                    // Convert query to lowercase terms for matching
                    WITH $query AS query
                    WITH split(toLower(query), ' ') AS terms
                    
                    // Find seed entities matching query terms
                    MATCH (seed:Entity)
                    WHERE ANY(term IN terms WHERE toLower(seed.name) CONTAINS term)
                    
                    // Traverse 2-hop neighborhood
                    OPTIONAL MATCH (seed)-[r1]-(hop1:Entity)
                    OPTIONAL MATCH (hop1)-[r2]-(hop2:Entity)
                    
                    // Collect all entities in neighborhood
                    WITH COLLECT(DISTINCT seed) + 
                         COLLECT(DISTINCT hop1) + 
                         COLLECT(DISTINCT hop2) AS neighborhood
                    UNWIND neighborhood AS entity
                    
                    // Find chunks mentioning these entities
                    MATCH (chunk:Chunk)-[:MENTIONS]->(entity)
                    
                    // Return chunks with relevance score (mention count)
                    RETURN DISTINCT 
                        chunk.id AS chunk_id,
                        chunk.text AS text,
                        COUNT(entity) AS mention_count
                    ORDER BY mention_count DESC
                    LIMIT $limit
                    """,
                    query=query,
                    limit=limit,
                )
                
                results = []
                rank = 0
                async for record in result:
                    results.append(SearchResult(
                        chunk_id=record["chunk_id"],
                        text=record["text"] or "",
                        score=float(record["mention_count"]),  # Use mention count as score
                        source="graph",
                        metadata={"rank": rank, "mention_count": record["mention_count"]},
                    ))
                    rank += 1
                
                logger.debug(f"Graph search returned {len(results)} results")
                return results
                
        except Neo4jError as e:
            logger.error(f"Neo4j graph search failed: {e}")
            return []
    
    def _rrf_fuse(
        self,
        vector_results: list[SearchResult],
        graph_results: list[SearchResult],
        vector_weight: float,
        graph_weight: float,
        k: int,
    ) -> list[SearchResult]:
        """
        Fuse ranked lists using Reciprocal Rank Fusion (RRF).
        
        RRF Formula:
            score(d) = Σ (weight / (rank + k)) for each ranked list containing d
        
        Where k=60 is the standard constant that dampens the impact of high ranks.
        
        Args:
            vector_results: Results from vector search (ranked by similarity)
            graph_results: Results from graph search (ranked by relevance)
            vector_weight: Weight multiplier for vector scores
            graph_weight: Weight multiplier for graph scores
            k: Number of final results to return
            
        Returns:
            Fused, deduplicated list of top-k results
        """
        # Score accumulator: chunk_id -> (accumulated_score, best_result)
        scores: dict[str, tuple[float, SearchResult, set[str]]] = defaultdict(
            lambda: (0.0, None, set())
        )
        
        # Process vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            rrf_score = vector_weight / (rank + RRF_K)
            
            current_score, current_result, sources = scores[chunk_id]
            sources.add("vector")
            scores[chunk_id] = (
                current_score + rrf_score,
                result if current_result is None else current_result,
                sources,
            )
        
        # Process graph results
        for rank, result in enumerate(graph_results):
            chunk_id = result.chunk_id
            rrf_score = graph_weight / (rank + RRF_K)
            
            current_score, current_result, sources = scores[chunk_id]
            sources.add("graph")
            scores[chunk_id] = (
                current_score + rrf_score,
                result if current_result is None else current_result,
                sources,
            )
        
        # Sort by fused score and take top-k
        ranked = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)[:k]
        
        # Build final results
        fused_results = []
        for chunk_id, (score, result, sources) in ranked:
            # Guard against empty sources (should not happen but safety first)
            if not sources or result is None:
                continue
            source_str = "both" if len(sources) > 1 else next(iter(sources))
            fused_results.append(SearchResult(
                chunk_id=result.chunk_id,
                text=result.text,
                score=score,
                source=source_str,
                doc_id=result.doc_id,
                metadata={**result.metadata, "sources": list(sources)},
            ))
        
        logger.info(f"RRF fusion: {len(vector_results)} vector + {len(graph_results)} graph → {len(fused_results)} fused")
        return fused_results
    
    def _handle_empty_search(self, query: str) -> HybridSearchResponse:
        """Return empty response when no results found."""
        return HybridSearchResponse(
            query=query,
            results=[],
            vector_count=0,
            graph_count=0,
            total_fused=0,
        )
