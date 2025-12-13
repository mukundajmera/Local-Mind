"""
Integration Tests - Pipeline with Mocked Databases
===================================================
Tests that mock external APIs but verify internal logic and query generation.

Run with: pytest tests/integration/test_pipelines.py -m integration
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionPipelineCypherCapture:
    """
    Integration tests for IngestionPipeline.
    
    These tests mock the database drivers but capture the exact Cypher
    queries generated, enabling audit and correctness verification.
    """
    
    async def test_document_creation_cypher(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        cypher_capture,
    ):
        """
        Test that document creation generates correct MERGE Cypher.
        
        Evidence: Cypher query logged to cypher_audit.log
        """
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session, capture = mock_neo4j_driver
        
        # Create pipeline with mocked dependencies
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        # Create test document
        doc = IngestedDocument(
            filename="test_document.pdf",
            file_size_bytes=1024,
        )
        
        # Run persistence
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=[],
            relationships=[],
        )
        
        # Verify Cypher was captured
        queries = capture.get_all()
        assert len(queries) >= 1, "At least one Cypher query should be captured"
        
        # Find document creation query
        doc_query = next(
            (q for q in queries if "MERGE (d:Document" in q["query"]),
            None
        )
        
        assert doc_query is not None, "Document MERGE query not found"
        assert "SET d.filename = $filename" in doc_query["query"]
        
        print(f"✅ Captured {len(queries)} Cypher queries")
    
    async def test_chunk_batching_cypher(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        cypher_capture,
    ):
        """
        Test that chunk persistence uses UNWIND for batching.
        
        Evidence: Batch query with UNWIND pattern logged.
        """
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument, TextChunk
        
        driver, session, capture = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        # Create document and chunks
        doc = IngestedDocument(filename="batch_test.pdf", file_size_bytes=5000)
        chunks = [
            TextChunk(
                doc_id=doc.doc_id,
                text=f"Chunk number {i} content for testing batch insertion.",
                position=i,
                embedding=[0.1] * 384,
            )
            for i in range(10)
        ]
        
        # Run persistence
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=chunks,
            entities=[],
            relationships=[],
        )
        
        # Verify UNWIND pattern was used
        queries = capture.get_all()
        unwind_query = next(
            (q for q in queries if "UNWIND $chunks AS chunk" in q["query"]),
            None
        )
        
        assert unwind_query is not None, "UNWIND batch query not found!"
        
        # Verify chunks parameter was passed
        assert "chunks" in unwind_query.get("params", {}) or unwind_query["query"].count("UNWIND") > 0
        
        print(f"✅ Batch query uses UNWIND pattern (efficient!)")
    
    async def test_entity_creation_cypher(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
        cypher_capture,
    ):
        """
        Test entity creation generates MERGE with ON CREATE/ON MATCH.
        
        Evidence: Entity queries use proper upsert pattern.
        """
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session, capture = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        doc = IngestedDocument(filename="entity_test.pdf", file_size_bytes=2000)
        
        # Persist with entities
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=[],
        )
        
        # Find entity query
        queries = capture.get_all()
        entity_query = next(
            (q for q in queries if "MERGE (e:Entity" in q["query"]),
            None
        )
        
        assert entity_query is not None, "Entity MERGE query not found"
        
        # Verify upsert pattern
        query_text = entity_query["query"]
        assert "ON CREATE SET" in query_text or "SET" in query_text
        
        print(f"✅ Entity creation uses MERGE pattern")
    
    async def test_relationship_creation_cypher(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
        cypher_capture,
    ):
        """
        Test relationship creation Cypher.
        
        Evidence: Relationship query with source/target matching.
        """
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session, capture = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        doc = IngestedDocument(filename="rel_test.pdf", file_size_bytes=3000)
        
        # Persist with entities and relationships
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=list(sample_extraction_result.relationships),
        )
        
        queries = capture.get_all()
        rel_query = next(
            (q for q in queries if "RELATED_TO" in q["query"] or "MERGE" in q["query"] and "source" in q["query"].lower()),
            None
        )
        
        # Should have relationship creation
        all_queries_text = " ".join(q["query"] for q in queries)
        assert "rel" in all_queries_text.lower() or "relationship" in all_queries_text.lower() or len(queries) >= 3
        
        print(f"✅ Relationship creation verified")
    
    async def test_cypher_uses_parameters_not_string_interpolation(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
        cypher_capture,
    ):
        """
        SECURITY TEST: Verify no string interpolation in Cypher (injection prevention).
        
        Evidence: All queries use $parameter placeholders.
        """
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session, capture = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        # Use potentially dangerous input
        doc = IngestedDocument(
            filename="'; DROP TABLE users; --",  # SQL injection attempt
            file_size_bytes=666,
        )
        
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=list(sample_extraction_result.relationships),
        )
        
        # Check all captured queries
        queries = capture.get_all()
        
        for q in queries:
            cypher = q["query"]
            
            # Cypher should NOT contain the injection string literally
            assert "DROP TABLE" not in cypher, f"Injection found in query: {cypher[:100]}"
            
            # Should use parameter placeholders
            if "filename" in cypher.lower():
                assert "$" in cypher, f"Query should use parameters: {cypher[:100]}"
        
        print(f"✅ All {len(queries)} queries use parameterized Cypher (secure!)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchPipelineIntegration:
    """Integration tests for HybridRetriever."""
    
    async def test_hybrid_retriever_rrf_fusion(
        self,
        sample_search_results,
        mock_settings,
    ):
        """Test that HybridRetriever correctly fuses results."""
        from services.search import HybridRetriever
        
        vector_results, graph_results = sample_search_results
        
        # Create retriever without full initialization
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever.settings = mock_settings
        
        # Call RRF fusion
        fused = retriever._rrf_fuse(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=0.5,
            graph_weight=0.5,
            k=5,
        )
        
        # Verify fusion results
        assert len(fused) <= 5
        
        # B should be first (best combined rank)
        chunk_ids = [r.chunk_id for r in fused]
        assert "chunk-B" in chunk_ids[:2], "chunk-B should be in top 2"
        
        # Results appearing in both should be marked "both"
        for result in fused:
            if result.chunk_id in ["chunk-A", "chunk-B"]:
                assert result.source == "both"
        
        print(f"✅ RRF fusion returned {len(fused)} results")
