"""
Unit Tests - Source Management Features
========================================
Test new schemas and logic for source filtering, briefing, and notes.
"""

import pytest
from pydantic import ValidationError
from datetime import datetime
from uuid import uuid4


class TestChatRequestSchema:
    """Tests for ChatRequest with source_ids field."""
    
    def test_chat_request_basic(self):
        """Test basic ChatRequest without source filtering."""
        from schemas import ChatRequest
        
        request = ChatRequest(
            message="What is quantum computing?",
            strategies=["insight"]
        )
        
        assert request.message == "What is quantum computing?"
        assert request.strategies == ["insight"]
        assert request.source_ids is None
        assert request.context_node_ids == []
    
    def test_chat_request_with_source_filtering(self):
        """Test ChatRequest with source_ids for filtered retrieval."""
        from schemas import ChatRequest
        
        doc_ids = [str(uuid4()), str(uuid4())]
        request = ChatRequest(
            message="Explain this concept",
            strategies=["sources"],
            source_ids=doc_ids
        )
        
        assert request.source_ids == doc_ids
        assert len(request.source_ids) == 2
    
    def test_chat_request_empty_message_fails(self):
        """Test that empty message fails validation."""
        from schemas import ChatRequest
        
        with pytest.raises(ValidationError):
            ChatRequest(message="")  # Empty message should fail


class TestBriefingResponseSchema:
    """Tests for BriefingResponse schema."""
    
    def test_valid_briefing_response(self):
        """Test valid briefing response creation."""
        from schemas import BriefingResponse
        
        doc_id = str(uuid4())
        briefing = BriefingResponse(
            summary="This document discusses quantum mechanics and its applications.",
            key_topics=[
                "Quantum entanglement",
                "Superposition",
                "Wave-particle duality",
                "Quantum computing applications",
                "Heisenberg uncertainty principle"
            ],
            suggested_questions=[
                "What is quantum entanglement?",
                "How does superposition work?",
                "What are practical applications of quantum computing?"
            ],
            doc_id=doc_id
        )
        
        assert briefing.summary.startswith("This document")
        assert len(briefing.key_topics) == 5
        assert len(briefing.suggested_questions) == 3
        assert briefing.doc_id == doc_id
        assert isinstance(briefing.generated_at, datetime)
    
    def test_briefing_with_empty_lists(self):
        """Test briefing with empty lists is valid."""
        from schemas import BriefingResponse
        
        briefing = BriefingResponse(
            summary="Summary text",
            key_topics=[],
            suggested_questions=[],
            doc_id=str(uuid4())
        )
        
        assert briefing.key_topics == []
        assert briefing.suggested_questions == []
    
    def test_briefing_missing_summary_fails(self):
        """Test that missing summary fails validation."""
        from schemas import BriefingResponse
        
        with pytest.raises(ValidationError):
            BriefingResponse(
                key_topics=["Topic 1"],
                suggested_questions=["Question?"],
                doc_id=str(uuid4())
            )


class TestSavedNoteSchema:
    """Tests for SavedNote and CreateNoteRequest schemas."""
    
    def test_saved_note_creation(self):
        """Test valid SavedNote creation."""
        from schemas import SavedNote
        
        note = SavedNote(
            content="This is an important insight from the document.",
            tags=["research", "quantum-mechanics"],
            source_citation_id=str(uuid4())
        )
        
        assert note.content == "This is an important insight from the document."
        assert len(note.tags) == 2
        assert note.source_citation_id is not None
        assert isinstance(note.note_id, type(uuid4()))
        assert isinstance(note.created_at, datetime)
    
    def test_saved_note_without_citation(self):
        """Test note without source citation is valid."""
        from schemas import SavedNote
        
        note = SavedNote(
            content="General thought not tied to a specific source",
            tags=["general"]
        )
        
        assert note.source_citation_id is None
        assert note.tags == ["general"]
    
    def test_saved_note_empty_content_fails(self):
        """Test that empty content fails validation."""
        from schemas import SavedNote
        
        with pytest.raises(ValidationError):
            SavedNote(content="")  # Empty content should fail
    
    def test_create_note_request(self):
        """Test CreateNoteRequest schema."""
        from schemas import CreateNoteRequest
        
        request = CreateNoteRequest(
            content="My note content",
            tags=["tag1", "tag2"],
            source_citation_id="chunk-123"
        )
        
        assert request.content == "My note content"
        assert request.tags == ["tag1", "tag2"]
        assert request.source_citation_id == "chunk-123"
    
    def test_create_note_request_minimal(self):
        """Test CreateNoteRequest with only required fields."""
        from schemas import CreateNoteRequest
        
        request = CreateNoteRequest(content="Minimal note")
        
        assert request.content == "Minimal note"
        assert request.tags is None
        assert request.source_citation_id is None


class TestIngestedDocumentExtensions:
    """Test that IngestedDocument remains compatible with new features."""
    
    def test_ingested_document_creation(self):
        """Test IngestedDocument can still be created normally."""
        from schemas import IngestedDocument
        
        doc = IngestedDocument(
            filename="research_paper.pdf",
            file_size_bytes=1024000
        )
        
        assert doc.filename == "research_paper.pdf"
        assert doc.file_size_bytes == 1024000
        assert isinstance(doc.doc_id, type(uuid4()))
        assert isinstance(doc.upload_date, datetime)
