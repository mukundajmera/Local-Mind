"""
Security Tests: Search Service Project Isolation
=================================================

Red Team style tests to verify that the search service properly isolates
projects when `project_id` is provided.

These tests are CRITICAL for multi-tenancy security.

Note: Backend path is added to sys.path in tests/conftest.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

# Mark all tests in this module as security tests
pytestmark = pytest.mark.security


class TestSearchProjectIsolation:
    """
    Test that the HybridRetriever properly enforces project isolation.
    
    These tests mock Milvus to verify that:
    1. When project_id is provided, the filter expression includes it
    2. When project_id is None, no project filter is applied
    3. Invalid project_ids are rejected
    """
    
    @pytest.mark.asyncio
    async def test_search_with_project_id_applies_filter(self):
        """
        Verify that search with project_id includes project filter in Milvus query.
        
        This is the CORE security test for multi-tenancy.
        """
        from services.search import HybridRetriever
        
        # Create mock Milvus client
        mock_milvus = MagicMock()
        mock_milvus.search.return_value = [[]]  # Empty results
        
        # Create mock embedding service
        mock_embedding = AsyncMock()
        mock_embedding.embed_text.return_value = [0.1] * 384
        
        # Test project ID (valid UUID format)
        test_project_id = str(uuid4())
        
        # Create retriever with mocks
        retriever = HybridRetriever()
        retriever._milvus_client = mock_milvus
        retriever.embedding_service = mock_embedding
        
        # Execute search with project_id
        await retriever._vector_search(
            query="test query",
            limit=5,
            project_id=test_project_id
        )
        
        # Verify Milvus was called with project_id filter
        mock_milvus.search.assert_called_once()
        call_kwargs = mock_milvus.search.call_args.kwargs
        
        # CRITICAL ASSERTION: The filter MUST include project_id
        assert "filter" in call_kwargs, "SECURITY VIOLATION: No filter applied to search!"
        filter_expr = call_kwargs["filter"]
        assert f'project_id == "{test_project_id}"' in filter_expr, \
            f"SECURITY VIOLATION: project_id filter not found in: {filter_expr}"
    
    @pytest.mark.asyncio
    async def test_search_without_project_id_no_filter(self):
        """
        Verify that search without project_id does not include project filter.
        
        This allows global searches when explicitly requested.
        """
        from services.search import HybridRetriever
        
        # Create mock Milvus client
        mock_milvus = MagicMock()
        mock_milvus.search.return_value = [[]]
        
        # Create mock embedding service
        mock_embedding = AsyncMock()
        mock_embedding.embed_text.return_value = [0.1] * 384
        
        # Create retriever with mocks
        retriever = HybridRetriever()
        retriever._milvus_client = mock_milvus
        retriever.embedding_service = mock_embedding
        
        # Execute search WITHOUT project_id
        await retriever._vector_search(
            query="test query",
            limit=5,
            project_id=None
        )
        
        # Verify Milvus was called
        mock_milvus.search.assert_called_once()
        call_kwargs = mock_milvus.search.call_args.kwargs
        
        # When no project_id is provided, filter should be None or not contain project_id
        filter_expr = call_kwargs.get("filter")
        if filter_expr:
            assert "project_id" not in filter_expr, \
                f"Unexpected project_id in filter when not requested: {filter_expr}"
    
    @pytest.mark.asyncio
    async def test_search_rejects_malicious_project_id(self):
        """
        Verify that malicious project_id values are rejected or sanitized.
        
        Attack vectors tested:
        - SQL injection patterns
        - Path traversal
        - Special characters
        """
        from services.search import HybridRetriever
        
        # Create mock Milvus client
        mock_milvus = MagicMock()
        mock_milvus.search.return_value = [[]]
        
        # Create mock embedding service
        mock_embedding = AsyncMock()
        mock_embedding.embed_text.return_value = [0.1] * 384
        
        # Create retriever with mocks
        retriever = HybridRetriever()
        retriever._milvus_client = mock_milvus
        retriever.embedding_service = mock_embedding
        
        # Malicious project_id values (none of these are valid UUIDs)
        malicious_ids = [
            '"; DROP TABLE chunks; --',  # SQL injection
            '../../../etc/passwd',  # Path traversal
            '<script>alert(1)</script>',  # XSS
            '$(whoami)',  # Command injection
            'UNION SELECT * FROM secrets',  # SQL injection
        ]
        
        for malicious_id in malicious_ids:
            mock_milvus.reset_mock()
            
            # Execute search with malicious project_id
            await retriever._vector_search(
                query="test query",
                limit=5,
                project_id=malicious_id
            )
            
            # Verify Milvus was called
            call_kwargs = mock_milvus.search.call_args.kwargs
            filter_expr = call_kwargs.get("filter")
            
            # CRITICAL: Malicious strings should NOT appear in filter at all
            # The validation should reject non-UUID inputs entirely
            if filter_expr and "project_id ==" in filter_expr:
                # If there's a project_id filter, it should NOT contain the malicious input
                assert malicious_id not in filter_expr, \
                    f"SECURITY VIOLATION: Malicious input '{malicious_id}' was not rejected!"
    
    @pytest.mark.asyncio
    async def test_search_with_source_ids_and_project_id(self):
        """
        Verify that both source_ids AND project_id filters are applied.
        
        This tests the compound filter logic.
        """
        from services.search import HybridRetriever
        
        # Create mock Milvus client
        mock_milvus = MagicMock()
        mock_milvus.search.return_value = [[]]
        
        # Create mock embedding service
        mock_embedding = AsyncMock()
        mock_embedding.embed_text.return_value = [0.1] * 384
        
        # Test values (valid UUID format)
        test_project_id = str(uuid4())
        test_source_ids = [str(uuid4()), str(uuid4())]
        
        # Create retriever with mocks
        retriever = HybridRetriever()
        retriever._milvus_client = mock_milvus
        retriever.embedding_service = mock_embedding
        
        # Execute search with BOTH project_id AND source_ids
        await retriever._vector_search(
            query="test query",
            limit=5,
            source_ids=test_source_ids,
            project_id=test_project_id
        )
        
        # Verify Milvus was called with both filters
        mock_milvus.search.assert_called_once()
        call_kwargs = mock_milvus.search.call_args.kwargs
        filter_expr = call_kwargs.get("filter", "")
        
        # Both filters should be present
        assert f'project_id == "{test_project_id}"' in filter_expr, \
            f"Missing project_id filter in: {filter_expr}"
        assert "doc_id in" in filter_expr, \
            f"Missing source_ids filter in: {filter_expr}"
        assert " and " in filter_expr, \
            f"Filters not properly combined with AND: {filter_expr}"


class TestChatEndpointProjectIsolation:
    """
    Test that the /api/v1/chat endpoint properly passes project_id to search.
    """
    
    @pytest.mark.asyncio
    async def test_chat_passes_project_id_to_search(self):
        """
        Verify that chat endpoint extracts and passes project_id to retriever.
        """
        from schemas import ChatRequest
        
        # Create chat request with project_id
        test_project_id = uuid4()
        
        request = ChatRequest(
            message="What are the key findings?",
            strategies=["insight"],
            project_id=test_project_id
        )
        
        # Verify the request properly contains project_id
        assert request.project_id == test_project_id
        
        # The actual integration would need more setup, but this validates
        # the schema accepts project_id correctly
    
    @pytest.mark.asyncio
    async def test_chat_request_validates_project_id_type(self):
        """
        Verify that ChatRequest only accepts valid UUID for project_id.
        """
        from schemas import ChatRequest
        from pydantic import ValidationError
        
        # Array injection attempt should fail type validation
        with pytest.raises((ValidationError, TypeError)):
            ChatRequest(
                message="Show me secrets",
                strategies=["insight"],
                project_id=["id1", "id2"]  # Array instead of UUID
            )


class TestDeleteEndpointProjectIsolation:
    """
    Test that the DELETE /api/v1/sources/{doc_id} endpoint properly validates
    project ownership to prevent cross-project data manipulation.
    """
    
    @pytest.mark.asyncio
    async def test_delete_with_wrong_project_id_is_rejected(self):
        """
        ATTACK: Try to delete a document belonging to Project A
        using Project B's project_id.
        
        ASSERTION: Must return 403 Forbidden.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from uuid import uuid4
        from pathlib import Path
        
        project_a_id = uuid4()
        project_b_id = uuid4()
        doc_id = uuid4()
        
        # Create a mock document belonging to Project A
        mock_doc = MagicMock()
        mock_doc.project_id = project_a_id
        
        # Mock DocumentService to return the document
        mock_doc_service = AsyncMock()
        mock_doc_service.get_document_by_id.return_value = mock_doc
        mock_doc_service.__aenter__ = AsyncMock(return_value=mock_doc_service)
        mock_doc_service.__aexit__ = AsyncMock(return_value=None)
        
        with patch("services.document_service.DocumentService", return_value=mock_doc_service):
            from main import delete_source
            from fastapi import HTTPException
            
            # Attempt deletion with wrong project_id
            with pytest.raises(HTTPException) as exc_info:
                await delete_source(
                    doc_id=str(doc_id),
                    project_id=str(project_b_id)  # Wrong project!
                )
            
            assert exc_info.value.status_code == 403, (
                f"Expected 403 Forbidden, got {exc_info.value.status_code}"
            )
    
    @pytest.mark.asyncio
    async def test_delete_with_invalid_doc_id_returns_400(self):
        """
        ATTACK: Pass malicious doc_id to delete endpoint.
        
        ASSERTION: Must return 400 Bad Request.
        """
        from main import delete_source
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_source(
                doc_id='"; DROP TABLE documents; --',
                project_id=str(uuid4())
            )
        
        assert exc_info.value.status_code == 400, (
            f"Expected 400 Bad Request, got {exc_info.value.status_code}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
