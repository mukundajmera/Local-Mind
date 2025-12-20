
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from uuid import uuid4
from services.ingestion import IngestionPipeline, IngestedDocument
from exceptions import IngestionError
from pymilvus import MilvusException

# Mock Settings
@pytest.fixture
def mock_settings():
    with patch("services.ingestion.get_settings") as mock:
        mock.return_value.milvus_collection = "test_collection"
        mock.return_value.upload_dir = "/tmp/uploads"
        mock.return_value.chunk_size_tokens = 100
        mock.return_value.chunk_overlap_tokens = 10
        mock.return_value.milvus_uri = "mock_uri"
        yield mock

# Mock Milvus Client
@pytest.fixture
def mock_milvus():
    with patch("services.ingestion.MilvusClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.mark.asyncio
async def test_ingest_document_naming(mock_settings, mock_milvus):
    """Verify that file naming convention is applied (though logic is currently in main.py, ingestion.py handles the file obj)."""
    # Note: The renaming logic 'stem_{timestamp}' is in main.py. 
    # ingestion.py takes a file_path that should ALREADY be renamed.
    # So here we verify ingestion respects the filename passed to it.
    
    pipeline = IngestionPipeline()
    pipeline._milvus_client = mock_milvus
    
    # Mock parser to return dummy text
    with patch("services.ingestion.DocumentParser.parse_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = ("Dummy text", {})
        
        # Mock chunker/embedder using patches on the instance or class
        with patch.object(pipeline.chunker, "chunk_text_async", new_callable=AsyncMock) as mock_chunk:
            mock_chunk.return_value = []
            
            with patch.object(pipeline, "_embed_chunks", new_callable=AsyncMock) as mock_embed:
                mock_embed.return_value = []
                
                with patch.object(pipeline, "_persist_to_milvus", new_callable=AsyncMock) as mock_persist:
                    test_path = Path("/tmp/uploads/report_1234567890.pdf")
                    # We need to mock stat().st_size
                    with patch("pathlib.Path.stat") as mock_stat:
                        mock_stat.return_value.st_size = 1024
                        
                        doc = await pipeline.ingest_document(test_path)
                        
                        assert doc.filename == "report_1234567890.pdf"
                        assert doc.file_size_bytes == 1024

@pytest.mark.asyncio
async def test_atomic_delete_rollback(mock_settings, mock_milvus):
    """
    Test "The Trap": verify that if Milvus deletion fails, 
    the disk file is NOT deleted.
    """
    pipeline = IngestionPipeline()
    pipeline._milvus_client = mock_milvus
    
    doc_id = str(uuid4())
    filename = "sensitive_doc.pdf"
    
    # 1. Setup: Milvus finds the file
    mock_milvus.query.return_value = [{"filename": filename}]
    
    # 2. Setup: Milvus delete "succeeds" (throws no error on delete call)
    # But checking verification query returns the item (deletion failed silently or wasn't consistent)
    # The logic in ingestion.py calls delete(), then query() to verify.
    # If query() returns data, it returns error dict and does NOT delete from disk.
    
    # First query (get filename) -> returns list
    # Second query (verify deletion) -> returns list (STILL EXISTS -> FAILURE)
    mock_milvus.query.side_effect = [[{"filename": filename}], [{"id": "some_id"}]]
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        with patch("pathlib.Path.exists", return_value=True):
            result = await pipeline.delete_document(doc_id)
            
            # Assertions
            assert result["error"] == "Milvus deletion verification failed"
            assert result["disk_deleted"] is False
            mock_unlink.assert_not_called()  # THE WALL: Disk delete must NOT happen

@pytest.mark.asyncio
async def test_atomic_delete_success(mock_settings, mock_milvus):
    """Verify happy path: Milvus gone -> Disk gone."""
    pipeline = IngestionPipeline()
    pipeline._milvus_client = mock_milvus
    
    doc_id = str(uuid4())
    filename = "ok_doc.pdf"
    
    # 1. Get filename -> found
    # 2. Verify deletion -> empty (good)
    mock_milvus.query.side_effect = [[{"filename": filename}], []]
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        with patch("pathlib.Path.exists", return_value=True):
            result = await pipeline.delete_document(doc_id)
            
            assert result["disk_deleted"] is True
            mock_unlink.assert_called_once()
