"""
Sovereign Cognitive Engine - Data Schemas
==========================================
Pydantic models for strict type enforcement across the GraphRAG pipeline.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Document & Chunk Models
# =============================================================================

class IngestedDocument(BaseModel):
    """Metadata for an ingested document source."""
    
    model_config = ConfigDict(frozen=True)
    
    doc_id: UUID = Field(default_factory=uuid4, description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    file_size_bytes: Optional[int] = Field(default=None)
    mime_type: str = Field(default="application/pdf")
    page_count: Optional[int] = Field(default=None)
    notebook_id: Optional[UUID] = Field(default=None, description="Parent notebook")
    project_id: Optional[UUID] = Field(default=None, description="Project this document belongs to")


class TextChunk(BaseModel):
    """Atomic unit of text with its embedding vector."""
    
    model_config = ConfigDict(frozen=True)
    
    chunk_id: UUID = Field(default_factory=uuid4, description="Unique chunk identifier")
    doc_id: UUID = Field(..., description="Parent document ID")
    text: str = Field(..., min_length=1, description="Chunk text content")
    embedding: Optional[list[float]] = Field(default=None, description="Vector embedding")
    position: int = Field(..., ge=0, description="Chunk position within document")
    start_char: int = Field(default=0, description="Start character offset in source")
    end_char: int = Field(default=0, description="End character offset in source")
    token_count: Optional[int] = Field(default=None)
    
    def to_milvus_dict(self) -> dict:
        """Convert to Milvus insertion format."""
        return {
            "id": str(self.chunk_id),
            "doc_id": str(self.doc_id),
            "text": self.text,
            "vector": self.embedding or [],
            "position": self.position,
        }


# =============================================================================
# Knowledge Graph Models
# =============================================================================

class GraphEntity(BaseModel):
    """Node definition for the knowledge graph."""
    
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(..., min_length=1, description="Entity name (e.g., 'Albert Einstein')")
    type: str = Field(..., description="Entity type (e.g., 'PERSON', 'CONCEPT', 'ORGANIZATION')")
    description: Optional[str] = Field(default=None, description="Brief entity description")
    chunk_ids: list[str] = Field(default_factory=list, description="Source chunks mentioning this entity")
    
    @property
    def normalized_name(self) -> str:
        """Normalize entity name for deduplication."""
        return self.name.strip().lower()


class GraphRelationship(BaseModel):
    """Edge definition connecting two entities."""
    
    model_config = ConfigDict(frozen=True)
    
    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    type: str = Field(..., description="Relationship type (e.g., 'WORKS_AT', 'RELATED_TO')")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    chunk_ids: list[str] = Field(default_factory=list, description="Source chunks for this relationship")


# =============================================================================
# LLM Extraction Schema (Critical for structured output)
# =============================================================================

class ExtractionResult(BaseModel):
    """
    Structured output schema for LLM entity/relationship extraction.
    
    This model enforces strict JSON parsing of LLM responses.
    Use with LangChain's `with_structured_output()` or Pydantic's `model_validate_json()`.
    
    Example LLM prompt suffix:
        "Return a JSON object matching this schema: {ExtractionResult.model_json_schema()}"
    """
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "entities": [
                        {"name": "Albert Einstein", "type": "PERSON", "description": "Physicist"},
                        {"name": "Theory of Relativity", "type": "CONCEPT", "description": None}
                    ],
                    "relationships": [
                        {"source": "Albert Einstein", "target": "Theory of Relativity", "type": "DEVELOPED", "weight": 1.0}
                    ]
                }
            ]
        }
    )
    
    entities: list[GraphEntity] = Field(
        default_factory=list,
        description="List of entities extracted from the text"
    )
    relationships: list[GraphRelationship] = Field(
        default_factory=list,
        description="List of relationships between entities"
    )
    
    @property
    def entity_count(self) -> int:
        return len(self.entities)
    
    @property
    def relationship_count(self) -> int:
        return len(self.relationships)
    
    def merge_with(self, other: "ExtractionResult") -> "ExtractionResult":
        """Merge two extraction results, useful for combining chunk extractions."""
        return ExtractionResult(
            entities=list(self.entities) + list(other.entities),
            relationships=list(self.relationships) + list(other.relationships),
        )


# =============================================================================
# Search & Retrieval Models
# =============================================================================

class SearchResult(BaseModel):
    """Single result from hybrid search."""
    
    chunk_id: str
    text: str
    score: float = Field(..., description="Fused relevance score")
    source: str = Field(..., description="Source branch: 'vector', 'graph', or 'both'")
    doc_id: Optional[str] = Field(default=None)
    metadata: dict = Field(default_factory=dict)


class HybridSearchResponse(BaseModel):
    """Response from hybrid retriever containing ranked results."""
    
    query: str
    results: list[SearchResult]
    vector_count: int = Field(..., description="Results from vector branch before fusion")
    graph_count: int = Field(..., description="Results from graph branch before fusion")
    total_fused: int = Field(..., description="Final deduplicated count after RRF")


# =============================================================================
# Chat Models
# =============================================================================

class ChatRequest(BaseModel):
    """Request schema for chat endpoint with optional source filtering."""
    
    message: str = Field(..., min_length=1, description="User's query or message")
    context_node_ids: List[str] = Field(default_factory=list, description="Legacy: Context node IDs")
    strategies: List[str] = Field(default_factory=list, description="Search strategies to use")
    source_ids: Optional[List[str]] = Field(
        default=None, 
        description="Optional list of document IDs to filter search. If None, searches all documents."
    )
    project_id: Optional[UUID] = Field(
        default=None,
        description="Optional project ID to filter search. If provided, only searches documents in this project."
    )


# =============================================================================
# Briefing Models
# =============================================================================

class BriefingResponse(BaseModel):
    """Automated briefing generated after document upload."""
    
    summary: str = Field(..., description="1-paragraph overview of the document")
    key_topics: List[str] = Field(
        default_factory=list, 
        description="5-7 key topics or bullet points from the document"
    )
    suggested_questions: List[str] = Field(
        default_factory=list,
        description="3 follow-up questions for the user to explore"
    )
    doc_id: str = Field(..., description="Associated document ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Notes Models
# =============================================================================

class SavedNote(BaseModel):
    """User-created note with optional source citation and project association."""
    
    note_id: UUID = Field(default_factory=uuid4, description="Unique note identifier")
    project_id: Optional[UUID] = Field(default=None, description="Associated project")
    content: str = Field(..., min_length=1, description="Note content")
    title: Optional[str] = Field(default=None, max_length=200, description="Optional title")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    source_citation_id: Optional[str] = Field(
        default=None, 
        description="Optional reference to a chunk or document ID"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document name")
    is_pinned: bool = Field(default=False, description="Whether note is pinned")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")


class CreateNoteRequest(BaseModel):
    """Request schema for creating a new note."""
    
    content: str = Field(..., min_length=1, description="Note content")
    title: Optional[str] = Field(default=None, max_length=200, description="Optional title")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")
    source_citation_id: Optional[str] = Field(
        default=None,
        description="Optional reference to a chunk or document ID"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document name")
    project_id: Optional[UUID] = Field(default=None, description="Associated project")


class UpdateNoteRequest(BaseModel):
    """Request schema for updating an existing note."""
    
    content: Optional[str] = Field(default=None, min_length=1, description="Note content")
    title: Optional[str] = Field(default=None, max_length=200, description="Optional title")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")
    is_pinned: Optional[bool] = Field(default=None, description="Pin status")


class NotesListResponse(BaseModel):
    """Response schema for notes list endpoint."""
    
    notes: List[SavedNote]
    total: int
    has_more: bool = False

