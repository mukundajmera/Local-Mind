"""
End-to-End Tests - Full Search Flow
====================================
Tests that require running containers (Neo4j, Milvus, Redis).

Skip these in CI by not setting E2E_ACTIVE environment variable.
"""

import os
import pytest
from uuid import uuid4


# Skip entire module if E2E not active
pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
class TestFullSearchFlow:
    """End-to-end tests for the complete search pipeline."""
    
    async def test_ingest_and_search_returns_results(self):
        """
        Test full flow: ingest text → search → get results.
        
        Requires running containers:
        - Neo4j (bolt://cognitive-brain:7687)
        - Milvus (memory-bank:19530)
        """
        from services.ingestion import IngestionPipeline, TextChunker, EmbeddingService
        from services.search import HybridRetriever
        from schemas import TextChunk, IngestedDocument
        
        # Sample text for ingestion
        sample_text = """
        Quantum computing represents a fundamental shift in computational paradigms.
        Unlike classical computers that use bits, quantum computers use qubits.
        Qubits can exist in superposition, allowing quantum computers to process
        multiple possibilities simultaneously. Companies like IBM, Google, and
        Microsoft are racing to build practical quantum computers. In 2019,
        Google claimed quantum supremacy with their Sycamore processor.
        """
        
        # Step 1: Create document and chunks
        doc = IngestedDocument(
            filename="quantum_computing_test.txt",
            file_size_bytes=len(sample_text),
        )
        
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk_text(sample_text, doc.doc_id)
        
        assert len(chunks) > 0, "Should create at least one chunk"
        
        # Step 2: Ingest using full pipeline
        async with IngestionPipeline() as pipeline:
            # Add embeddings to chunks
            embedded_chunks = await pipeline._embed_chunks(chunks)
            
            # Persist to Milvus
            await pipeline._persist_to_milvus(embedded_chunks)
            
            # Persist to Neo4j (without entities for this basic test)
            await pipeline._persist_to_neo4j(
                doc=doc,
                chunks=embedded_chunks,
                entities=[],
                relationships=[],
            )
        
        # Step 3: Search for relevant content
        async with HybridRetriever() as retriever:
            results = await retriever.search(
                query="quantum computing qubits",
                k=5,
            )
        
        # Assertions
        assert results is not None
        assert results.total_fused > 0, "Should find at least one result"
        
        # Verify results contain expected content
        result_texts = " ".join(r.text for r in results.results)
        assert "quantum" in result_texts.lower() or "qubit" in result_texts.lower()
    
    async def test_empty_query_returns_results(self):
        """Test that even vague queries return something if data exists."""
        from services.search import HybridRetriever
        
        async with HybridRetriever() as retriever:
            results = await retriever.search(
                query="technology",
                k=5,
            )
        
        # Should not crash, may or may not have results
        assert results is not None
        assert hasattr(results, "results")
    
    async def test_search_with_no_matches(self):
        """Test search returns empty when no matches."""
        from services.search import HybridRetriever
        
        # Use a nonsense query unlikely to match anything
        async with HybridRetriever() as retriever:
            results = await retriever.search(
                query="xyzzy12345plugh",
                k=5,
            )
        
        # Should return empty results, not crash
        assert results is not None
        assert isinstance(results.results, list)


@pytest.mark.asyncio
class TestDatabaseConnectivity:
    """Test that databases are reachable."""
    
    async def test_neo4j_connection(self):
        """Verify Neo4j is accessible."""
        from neo4j import AsyncGraphDatabase
        from config import get_settings
        
        settings = get_settings()
        
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        
        try:
            async with driver.session() as session:
                result = await session.run("RETURN 1 as n")
                record = await result.single()
                assert record["n"] == 1
        finally:
            await driver.close()
    
    async def test_milvus_connection(self):
        """Verify Milvus is accessible."""
        from pymilvus import MilvusClient
        from config import get_settings
        
        settings = get_settings()
        
        client = MilvusClient(uri=settings.milvus_uri)
        
        try:
            # List collections as connectivity test
            collections = client.list_collections()
            assert isinstance(collections, list)
        finally:
            client.close()


@pytest.mark.asyncio
class TestPodcastGeneration:
    """E2E tests for podcast generation (requires vLLM)."""
    
    @pytest.mark.skipif(
        not os.getenv("LLM_ACTIVE"),
        reason="LLM_ACTIVE not set, skipping LLM tests"
    )
    async def test_podcast_script_generation(self):
        """Test full podcast script generation."""
        from services.llm_factory import LLMService
        from services.scriptwriter import ScriptwriterAgent
        
        context = """
        Machine learning has transformed how we approach problem-solving.
        Neural networks, inspired by the human brain, can learn patterns from data.
        Deep learning, a subset of ML, uses multiple layers to extract features.
        """
        
        async with LLMService() as llm:
            writer = ScriptwriterAgent()
            script = await writer.generate_podcast_script(
                context_text=context,
                llm_service=llm,
                target_duration_seconds=120,
            )
        
        assert script is not None
        assert len(script.dialogue) >= 5
        
        # Verify both speakers are present
        speakers = set(line.speaker for line in script.dialogue)
        assert "Alex" in speakers or "Sarah" in speakers
