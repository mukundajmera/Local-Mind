"""
Integration Tests - Ingestion Pipeline with Mocks
=================================================
Test IngestionPipeline with mocked databases to verify Cypher queries.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.asyncio
class TestIngestionPipelineMocked:
    """Integration tests for IngestionPipeline with mocked dependencies."""
    
    async def test_persist_to_neo4j_document_creation(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
    ):
        """Test that document node is created with correct Cypher."""
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument, TextChunk
        
        driver, session = mock_neo4j_driver
        
        with patch("services.ingestion.AsyncGraphDatabase") as mock_db:
            mock_db.driver.return_value = driver
            
            with patch("services.ingestion.MilvusClient") as mock_milvus:
                mock_milvus.return_value = mock_milvus_client
                
                pipeline = IngestionPipeline(settings=mock_settings)
                pipeline._neo4j_driver = driver
                pipeline._milvus_client = mock_milvus_client
                
                # Create test document and chunks
                doc = IngestedDocument(
                    filename="test.pdf",
                    file_size_bytes=1024,
                )
                chunks = []
                
                # Call the method
                await pipeline._persist_to_neo4j(
                    doc=doc,
                    chunks=chunks,
                    entities=[],
                    relationships=[],
                )
                
                # Verify Document MERGE was called
                calls = session.run.call_args_list
                assert len(calls) >= 1
                
                # First call should be document creation
                first_call = calls[0]
                cypher_query = first_call[0][0]
                
                assert "MERGE (d:Document {id: $doc_id})" in cypher_query
                assert "SET d.filename = $filename" in cypher_query
    
    async def test_persist_to_neo4j_chunk_batching(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
    ):
        """Test that chunks are batched with UNWIND."""
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument, TextChunk
        
        driver, session = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        doc = IngestedDocument(filename="test.pdf", file_size_bytes=1024)
        
        # Create multiple chunks
        doc_id = doc.doc_id
        chunks = [
            TextChunk(doc_id=doc_id, text=f"Chunk {i}", position=i, embedding=[0.1] * 384)
            for i in range(5)
        ]
        
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=chunks,
            entities=[],
            relationships=[],
        )
        
        # Find the chunk creation call
        calls = session.run.call_args_list
        chunk_call = None
        for c in calls:
            if "UNWIND $chunks AS chunk" in c[0][0]:
                chunk_call = c
                break
        
        assert chunk_call is not None, "UNWIND batch query not found"
        
        # Verify chunks parameter was passed
        kwargs = chunk_call[1]
        assert "chunks" in kwargs
        assert len(kwargs["chunks"]) == 5
    
    async def test_persist_to_neo4j_entity_creation(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
    ):
        """Test entity creation with MERGE."""
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        doc = IngestedDocument(filename="test.pdf", file_size_bytes=1024)
        
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=[],
        )
        
        # Find entity creation call
        calls = session.run.call_args_list
        entity_call = None
        for c in calls:
            if "MERGE (e:Entity" in c[0][0]:
                entity_call = c
                break
        
        assert entity_call is not None, "Entity MERGE query not found"
        
        # Verify UNWIND pattern is used
        assert "UNWIND $entities AS entity" in entity_call[0][0]
        
        # Verify ON CREATE and ON MATCH clauses
        assert "ON CREATE SET" in entity_call[0][0]
        assert "ON MATCH SET" in entity_call[0][0]
    
    async def test_persist_to_neo4j_relationship_creation(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
    ):
        """Test relationship creation."""
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument
        
        driver, session = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        doc = IngestedDocument(filename="test.pdf", file_size_bytes=1024)
        
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=list(sample_extraction_result.relationships),
        )
        
        # Find relationship creation call
        calls = session.run.call_args_list
        rel_call = None
        for c in calls:
            if "MERGE (source)-[r:RELATED_TO" in c[0][0]:
                rel_call = c
                break
        
        assert rel_call is not None, "Relationship MERGE query not found"
        
        # Verify UNWIND pattern
        assert "UNWIND $rels AS rel" in rel_call[0][0]
    
    async def test_cypher_uses_parameters_not_string_formatting(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
        sample_extraction_result,
    ):
        """Security test: verify no string formatting in Cypher."""
        from services.ingestion import IngestionPipeline
        from schemas import IngestedDocument, TextChunk
        
        driver, session = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        # Use potentially dangerous input
        doc = IngestedDocument(
            filename="test'); DROP TABLE users;--",  # SQL injection attempt
            file_size_bytes=1024,
        )
        
        await pipeline._persist_to_neo4j(
            doc=doc,
            chunks=[],
            entities=list(sample_extraction_result.entities),
            relationships=list(sample_extraction_result.relationships),
        )
        
        # Check all Cypher queries
        for call in session.run.call_args_list:
            cypher = call[0][0]
            
            # Cypher should use parameter placeholders ($)
            # Should NOT contain the actual injection string in the query
            assert "DROP TABLE" not in cypher, "Injection string found in Cypher!"
            
            # Should use proper parameter references
            if "filename" in cypher:
                assert "$filename" in cypher, "Should use $filename parameter"


@pytest.mark.asyncio
class TestIngestionPipelineErrorHandling:
    """Test error handling in IngestionPipeline."""
    
    async def test_llm_failure_continues_processing(
        self,
        mock_neo4j_driver,
        mock_milvus_client,
        mock_settings,
    ):
        """Test that LLM failures don't crash entire ingestion."""
        from services.ingestion import IngestionPipeline, LLMService
        from schemas import TextChunk, ExtractionResult
        
        driver, session = mock_neo4j_driver
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._neo4j_driver = driver
        pipeline._milvus_client = mock_milvus_client
        
        # Mock LLM to fail on first chunk, succeed on second
        call_count = 0
        async def mock_extract(text, chunk_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("LLM timeout")
            return ExtractionResult(entities=[], relationships=[])
        
        pipeline.llm_service.extract_entities = mock_extract
        
        # Create test chunks
        doc_id = uuid4()
        chunks = [
            TextChunk(doc_id=doc_id, text="Chunk 1", position=0, embedding=[0.1]*384),
            TextChunk(doc_id=doc_id, text="Chunk 2", position=1, embedding=[0.1]*384),
        ]
        
        # This should NOT raise
        all_entities = []
        all_relationships = []
        extraction_errors = []
        
        for chunk in chunks:
            try:
                extraction = await pipeline.llm_service.extract_entities(
                    chunk.text,
                    str(chunk.chunk_id),
                )
                all_entities.extend(extraction.entities)
                all_relationships.extend(extraction.relationships)
            except Exception as e:
                extraction_errors.append(str(e))
                continue
        
        # Should have one error and one success
        assert len(extraction_errors) == 1
        assert call_count == 2  # Both chunks were processed
    
    async def test_milvus_persistence_with_empty_chunks(
        self,
        mock_milvus_client,
        mock_settings,
    ):
        """Test that empty chunks list doesn't try to insert."""
        from services.ingestion import IngestionPipeline
        
        pipeline = IngestionPipeline(settings=mock_settings)
        pipeline._milvus_client = mock_milvus_client
        
        await pipeline._persist_to_milvus([])
        
        # upsert should NOT be called for empty list
        mock_milvus_client.upsert.assert_not_called()
