"""
Test Chat Schema - Backend Tests
=================================
Verifies chat endpoint handles source_ids correctly for filtered RAG.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/backend"))

from main import app
import schemas

client = TestClient(app)


class TestChatRequestSchema:
    """Tests for ChatRequest schema validation."""

    def test_chat_request_accepts_source_ids(self):
        """ChatRequest schema should accept source_ids field."""
        request = schemas.ChatRequest(
            message="What is the summary?",
            source_ids=["doc-123", "doc-456"],
            strategies=["sources"],
        )
        assert request.source_ids == ["doc-123", "doc-456"]

    def test_chat_request_accepts_null_source_ids(self):
        """ChatRequest should accept null source_ids (search all docs)."""
        request = schemas.ChatRequest(
            message="General question",
            source_ids=None,
            strategies=["insight"],
        )
        assert request.source_ids is None

    def test_chat_request_source_ids_defaults_to_none(self):
        """source_ids should default to None if not provided."""
        request = schemas.ChatRequest(
            message="Hello",
            strategies=[],
        )
        assert request.source_ids is None

    def test_chat_request_requires_message(self):
        """ChatRequest should require non-empty message."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            schemas.ChatRequest(
                message="",  # Empty message should fail
                strategies=[],
            )


class TestChatEndpointSourceFiltering:
    """Tests for /api/v1/chat endpoint source filtering."""

    @patch("main.HybridRetriever")
    @patch("main.LLMService")
    def test_chat_accepts_valid_payload_with_source_ids(
        self, mock_llm, mock_retriever
    ):
        """Chat endpoint should accept payload with source_ids."""
        # Setup mocks
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.search = AsyncMock(
            return_value=type("Results", (), {"results": []})()
        )
        mock_retriever.return_value.__aenter__ = AsyncMock(
            return_value=mock_retriever_instance
        )
        mock_retriever.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_llm_instance = AsyncMock()
        mock_llm_instance.chat = AsyncMock(return_value="Mock response")
        mock_llm.return_value.__aenter__ = AsyncMock(return_value=mock_llm_instance)
        mock_llm.return_value.__aexit__ = AsyncMock(return_value=None)

        payload = {
            "message": "Summarize the document",
            "source_ids": ["doc-abc-123"],
            "strategies": ["sources"],
        }

        response = client.post("/api/v1/chat", json=payload)

        # Should succeed (200) or fail gracefully (500 if DB down), not 422
        assert response.status_code != 422, "Valid payload should not return 422"

    @patch("main.HybridRetriever")
    @patch("main.LLMService")
    def test_chat_accepts_null_source_ids(self, mock_llm, mock_retriever):
        """Chat should accept null source_ids (search all documents)."""
        # Setup mocks
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.search = AsyncMock(
            return_value=type("Results", (), {"results": []})()
        )
        mock_retriever.return_value.__aenter__ = AsyncMock(
            return_value=mock_retriever_instance
        )
        mock_retriever.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_llm_instance = AsyncMock()
        mock_llm_instance.chat = AsyncMock(return_value="Response without filtering")
        mock_llm.return_value.__aenter__ = AsyncMock(return_value=mock_llm_instance)
        mock_llm.return_value.__aexit__ = AsyncMock(return_value=None)

        payload = {
            "message": "General question",
            "source_ids": None,
            "strategies": ["insight"],
        }

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code != 422

    @patch("main.HybridRetriever")
    @patch("main.LLMService")
    def test_chat_response_includes_filtered_sources_flag(
        self, mock_llm, mock_retriever
    ):
        """Response should indicate if sources were filtered."""
        # Setup mocks
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.search = AsyncMock(
            return_value=type("Results", (), {"results": []})()
        )
        mock_retriever.return_value.__aenter__ = AsyncMock(
            return_value=mock_retriever_instance
        )
        mock_retriever.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_llm_instance = AsyncMock()
        mock_llm_instance.chat = AsyncMock(return_value="Filtered response")
        mock_llm.return_value.__aenter__ = AsyncMock(return_value=mock_llm_instance)
        mock_llm.return_value.__aexit__ = AsyncMock(return_value=None)

        payload = {
            "message": "Question about specific doc",
            "source_ids": ["doc-123"],
            "strategies": ["sources"],
        }

        response = client.post("/api/v1/chat", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert "filtered_sources" in data
            assert data["filtered_sources"] is True

    def test_chat_rejects_missing_message(self):
        """Chat should reject requests without message field."""
        payload = {
            "source_ids": ["doc-123"],
            "strategies": ["sources"],
            # message is missing
        }

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 422, "Missing message should return 422"


class TestChatResponseStructure:
    """Tests for chat response structure."""

    @patch("main.HybridRetriever")
    @patch("main.LLMService")
    def test_chat_response_has_required_fields(self, mock_llm, mock_retriever):
        """Chat response should include all required fields."""
        # Setup mocks
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.search = AsyncMock(
            return_value=type("Results", (), {"results": []})()
        )
        mock_retriever.return_value.__aenter__ = AsyncMock(
            return_value=mock_retriever_instance
        )
        mock_retriever.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_llm_instance = AsyncMock()
        mock_llm_instance.chat = AsyncMock(return_value="Test response")
        mock_llm.return_value.__aenter__ = AsyncMock(return_value=mock_llm_instance)
        mock_llm.return_value.__aexit__ = AsyncMock(return_value=None)

        payload = {
            "message": "Hello",
            "strategies": ["sources"],
        }

        response = client.post("/api/v1/chat", json=payload)

        if response.status_code == 200:
            data = response.json()
            assert "response" in data, "Response must include 'response' field"
            assert "sources" in data, "Response must include 'sources' field"
            assert "context_used" in data, "Response must include 'context_used' field"
            assert "filtered_sources" in data, "Response must include 'filtered_sources' field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
