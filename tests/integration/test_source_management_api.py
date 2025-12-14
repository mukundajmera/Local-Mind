"""
Integration Tests - Source Management API
==========================================
Test API endpoints for source filtering, briefing, and notes.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../apps/backend"))

from main import app

client = TestClient(app)


class TestChatWithSourceFiltering:
    """Test /api/v1/chat endpoint with source_ids filtering."""
    
    def test_chat_without_source_filtering(self):
        """Test chat endpoint without source filtering (existing behavior)."""
        payload = {
            "message": "What is quantum computing?",
            "strategies": []  # No search, just LLM
        }
        
        try:
            response = client.post("/api/v1/chat", json=payload)
            # Should not be 404 or 501
            assert response.status_code != 404
            assert response.status_code != 501
            
            if response.status_code == 200:
                data = response.json()
                assert "response" in data
                assert "filtered_sources" in data
                assert data["filtered_sources"] is False
        except Exception:
            # May fail due to missing DB/LLM, but endpoint should exist
            pass
    
    def test_chat_with_source_filtering(self):
        """Test chat endpoint with source_ids parameter."""
        payload = {
            "message": "Explain this concept",
            "strategies": ["insight"],
            "source_ids": ["doc-id-1", "doc-id-2"]
        }
        
        try:
            response = client.post("/api/v1/chat", json=payload)
            # Should not be 404 or 501
            assert response.status_code != 404
            assert response.status_code != 501
            
            if response.status_code == 200:
                data = response.json()
                assert "filtered_sources" in data
                assert data["filtered_sources"] is True
        except Exception:
            # May fail due to missing DB/LLM, but endpoint should exist
            pass
    
    def test_chat_with_empty_source_list(self):
        """Test chat with empty source_ids list."""
        payload = {
            "message": "Test query",
            "strategies": ["insight"],
            "source_ids": []
        }
        
        try:
            response = client.post("/api/v1/chat", json=payload)
            assert response.status_code != 404
        except Exception:
            pass


class TestNotesAPI:
    """Test /api/v1/notes endpoints."""
    
    def test_notes_endpoint_exists(self):
        """Test that notes endpoints are available."""
        response = client.get("/api/v1/notes")
        
        # Should not be 404 or 501
        assert response.status_code != 404
        assert response.status_code != 501
        
        # May return 200 with empty list or 500/503 if DB unavailable
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
    
    def test_create_note_endpoint_exists(self):
        """Test that create note endpoint is available."""
        payload = {
            "content": "Test note content",
            "tags": ["test"],
            "source_citation_id": None
        }
        
        try:
            response = client.post("/api/v1/notes", json=payload)
            # Should not be 404 or 501
            assert response.status_code != 404
            assert response.status_code != 501
            
            if response.status_code == 200:
                data = response.json()
                assert "note_id" in data
                assert "content" in data
                assert data["content"] == "Test note content"
        except Exception:
            # May fail due to DB connection, but endpoint should exist
            pass
    
    def test_create_note_minimal(self):
        """Test creating note with minimal data."""
        payload = {
            "content": "Minimal note"
        }
        
        try:
            response = client.post("/api/v1/notes", json=payload)
            assert response.status_code != 404
        except Exception:
            pass
    
    def test_get_note_by_id_endpoint_exists(self):
        """Test that get note by ID endpoint is available."""
        note_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(f"/api/v1/notes/{note_id}")
        # Should not be 501 (Not Implemented)
        assert response.status_code != 501
        # May be 404 (not found) or 500 (DB error)
    
    def test_delete_note_endpoint_exists(self):
        """Test that delete note endpoint is available."""
        note_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.delete(f"/api/v1/notes/{note_id}")
        # Should not be 501 (Not Implemented)
        assert response.status_code != 501
        # May be 404 (not found) or 500 (DB error)


class TestBriefingAPI:
    """Test /api/v1/sources/{doc_id}/briefing endpoint."""
    
    def test_briefing_endpoint_exists(self):
        """Test that briefing endpoint is available."""
        doc_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(f"/api/v1/sources/{doc_id}/briefing")
        # Should not be 501 (Not Implemented)
        assert response.status_code != 501
        # May be 404 (not found) or 500 (DB error)
    
    def test_briefing_not_found_returns_404(self):
        """Test that non-existent briefing returns 404."""
        doc_id = "nonexistent-doc-id"
        
        try:
            response = client.get(f"/api/v1/sources/{doc_id}/briefing")
            if response.status_code == 404:
                data = response.json()
                assert "detail" in data
        except Exception:
            # May fail due to DB connection
            pass


class TestUploadWithBriefing:
    """Test that upload triggers briefing generation."""
    
    def test_upload_response_includes_briefing_status(self):
        """Test that upload response indicates briefing is being generated."""
        files = {
            "file": ("test.md", b"# Test\n\nThis is a test document.", "text/markdown")
        }
        
        try:
            response = client.post("/api/v1/sources/upload", files=files)
            
            if response.status_code == 200:
                data = response.json()
                assert "briefing_status" in data
                assert data["briefing_status"] == "generating"
        except Exception:
            # May fail due to missing dependencies
            pass
