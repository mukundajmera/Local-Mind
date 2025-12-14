# Source Management Features Implementation

This document describes the implementation of three core features for the Local Mind RAG application: Source-Filtered Retrieval, Automated Briefing Agent, and Saved Notes System.

## Overview

The implementation follows the "Notebook Experience" pattern similar to Google NotebookLM, allowing users to:
1. Query specific documents instead of the entire knowledge base
2. Receive automated summaries when documents are uploaded
3. Save notes with optional citations to source material

## Architecture

### 1. Source Selection & Filtered Retrieval

**Purpose**: Allow users to query specific documents, creating a "notebook" experience where searches are scoped to selected sources.

**Implementation**:

- **Schema**: `ChatRequest` in `schemas.py` now includes an optional `source_ids: List[str]` field
- **Search Service**: `HybridRetriever` in `services/search.py` updated with filtering logic:
  - `_vector_search()`: Applies Milvus filter expression: `doc_id in ["id1", "id2", ...]`
  - `_graph_search()`: Adds Neo4j WHERE clause: `chunk.doc_id IN $source_ids`
- **API Endpoint**: `/api/v1/chat` accepts `source_ids` parameter and passes to retriever
- **Behavior**: If `source_ids` is `None` or empty, searches all documents (backward compatible)

**Example Request**:
```json
{
  "message": "What are the key findings?",
  "strategies": ["insight"],
  "source_ids": ["doc-uuid-1", "doc-uuid-2"]
}
```

**Example Response**:
```json
{
  "response": "The key findings are...",
  "sources": [...],
  "context_used": true,
  "filtered_sources": true
}
```

### 2. Automated Briefing Agent

**Purpose**: Generate a summary, key topics, and suggested questions immediately after document upload using FastAPI BackgroundTasks.

**Implementation**:

- **Service**: `BriefingService` in `services/briefing_service.py`
  - `generate_briefing()`: Sends document text to LLM with structured prompt
  - Parses JSON response with: `summary`, `key_topics`, `suggested_questions`
  - Stores briefing on Document node in Neo4j
  
- **Background Task**: `_generate_briefing_background()` in `main.py`
  - Reads document text after ingestion completes
  - Calls `BriefingService.generate_briefing()`
  - Runs asynchronously without blocking upload response
  
- **API Endpoints**:
  - `POST /api/v1/sources/upload`: Returns immediately with `"briefing_status": "generating"`
  - `GET /api/v1/sources/{doc_id}/briefing`: Retrieves stored briefing

**Neo4j Storage**:
```cypher
MATCH (d:Document {id: $doc_id})
SET d.summary = $summary,
    d.key_topics = $key_topics,
    d.suggested_questions = $suggested_questions,
    d.briefing_generated_at = datetime()
```

**Example Briefing**:
```json
{
  "summary": "This document discusses quantum mechanics and its applications in computing...",
  "key_topics": [
    "Quantum entanglement",
    "Superposition",
    "Wave-particle duality",
    "Quantum computing applications",
    "Heisenberg uncertainty principle"
  ],
  "suggested_questions": [
    "What is quantum entanglement?",
    "How does superposition work?",
    "What are practical applications of quantum computing?"
  ],
  "doc_id": "doc-uuid",
  "generated_at": "2024-01-01T12:00:00Z"
}
```

### 3. Saved Notes System

**Purpose**: Allow users to capture insights, thoughts, and responses with optional citations to source material.

**Implementation**:

- **Schemas** in `schemas.py`:
  - `SavedNote`: Full note with UUID, timestamp, content, tags, optional citation
  - `CreateNoteRequest`: Input schema for creating notes
  
- **Service**: `NotesService` in `services/notes_service.py`
  - `create_note()`: Creates Note node in Neo4j, optionally links to Chunk via CITES relationship
  - `get_all_notes()`: Retrieves all notes ordered by created_at DESC
  - `get_note_by_id()`: Retrieves specific note
  - `delete_note()`: Deletes note and relationships
  
- **API Endpoints**:
  - `POST /api/v1/notes`: Create new note
  - `GET /api/v1/notes`: Retrieve all notes
  - `GET /api/v1/notes/{note_id}`: Retrieve specific note
  - `DELETE /api/v1/notes/{note_id}`: Delete note

**Neo4j Schema**:
```cypher
CREATE (n:Note {
  id: $note_id,
  content: $content,
  tags: $tags,
  source_citation_id: $source_citation_id,
  created_at: datetime()
})

// Optional citation relationship
MATCH (n:Note {id: $note_id})
MATCH (c:Chunk {id: $chunk_id})
MERGE (n)-[:CITES]->(c)
```

**Example Note Creation**:
```json
POST /api/v1/notes
{
  "content": "The document makes an interesting point about quantum decoherence",
  "tags": ["quantum", "research"],
  "source_citation_id": "chunk-uuid-123"
}
```

**Example Note Response**:
```json
{
  "note_id": "note-uuid",
  "content": "The document makes an interesting point about quantum decoherence",
  "tags": ["quantum", "research"],
  "source_citation_id": "chunk-uuid-123",
  "created_at": "2024-01-01T12:00:00Z"
}
```

## Database Schema Changes

### Neo4j Graph Updates

**Existing Schema** (unchanged):
- `(Document)-[:HAS_CHUNK]->(Chunk)`
- `(Chunk)-[:MENTIONS]->(Entity)`
- `(Entity)-[relationship_type]->(Entity)`

**New Properties on Document**:
- `summary: String` - 1-paragraph overview
- `key_topics: List<String>` - 5-7 bullet points
- `suggested_questions: List<String>` - 3 follow-up questions
- `briefing_generated_at: DateTime` - timestamp

**New Node Type**:
- `(Note)` with properties: `id`, `content`, `tags`, `source_citation_id`, `created_at`
- `(Note)-[:CITES]->(Chunk)` - optional relationship

### Milvus Collection

**No schema changes** - filtering uses existing `doc_id` field in metadata.

## API Documentation

### Modified Endpoints

#### `POST /api/v1/chat`
**New Parameter**: `source_ids` (optional)

```json
{
  "message": "string",
  "strategies": ["insight", "sources"],
  "source_ids": ["doc-id-1", "doc-id-2"]  // Optional
}
```

#### `POST /api/v1/sources/upload`
**New Response Field**: `briefing_status`

```json
{
  "status": "success",
  "doc_id": "uuid",
  "filename": "document.pdf",
  "chunks_created": 0,
  "entities_extracted": 0,
  "briefing_status": "generating"
}
```

### New Endpoints

#### `GET /api/v1/sources/{doc_id}/briefing`
Retrieve automated briefing for a document.

**Response**: `BriefingResponse` (200 OK) or 404 if not yet generated

#### `POST /api/v1/notes`
Create a new note.

**Request**: `CreateNoteRequest`
**Response**: `SavedNote` (200 OK)

#### `GET /api/v1/notes`
Retrieve all notes.

**Response**: `List[SavedNote]` (200 OK)

#### `GET /api/v1/notes/{note_id}`
Retrieve specific note.

**Response**: `SavedNote` (200 OK) or 404 Not Found

#### `DELETE /api/v1/notes/{note_id}`
Delete a note.

**Response**: `{"status": "success", "note_id": "..."}` (200 OK) or 404

## Testing

### Unit Tests (`tests/unit/test_source_management.py`)

- Schema validation for `ChatRequest`, `BriefingResponse`, `SavedNote`
- Required field validation
- Optional field handling
- Data type enforcement

**Run**: `pytest tests/unit/test_source_management.py`

### Integration Tests (`tests/integration/test_source_management_api.py`)

- Endpoint availability checks
- Request/response format validation
- Error handling (404, 500 cases)

**Note**: Full integration tests require Neo4j, Milvus, and LLM services running.

## Error Handling

### Briefing Generation Failures

- Background task catches all exceptions and logs errors
- Doesn't block upload response
- Returns minimal briefing on LLM failure:
  ```json
  {
    "summary": "Briefing generation encountered an error.",
    "key_topics": ["Error during processing"],
    "suggested_questions": ["What is this document about?"]
  }
  ```

### Source Filtering Edge Cases

- `source_ids = None`: Searches all documents
- `source_ids = []`: Searches all documents (empty filter)
- Invalid document IDs: No results returned (graceful degradation)

### Notes Service Failures

- Database connection errors: Returns 500 with error message
- Not found: Returns 404 with descriptive message
- GET endpoints return empty list on error (graceful degradation)

## Performance Considerations

### Briefing Generation

- Runs in background task (non-blocking)
- Truncates document to ~8000 chars to fit LLM context window
- Single LLM call per document
- Stores result in Neo4j for fast retrieval

### Source Filtering

- **Milvus**: Filter expression is pushed to database (efficient)
- **Neo4j**: WHERE clause reduces traversal scope
- No performance penalty when `source_ids = None`

### Notes Storage

- Single Cypher query per operation
- MERGE used for idempotent citation relationships
- Ordered retrieval uses indexed `created_at` field

## Future Enhancements

1. **Briefing Regeneration**: Add endpoint to manually trigger briefing update
2. **Note Search**: Full-text search across note content
3. **Note Tags**: Filtering and grouping by tags
4. **Source History**: Track which sources were used in each chat response
5. **Briefing Notifications**: Notify UI when briefing completes
6. **Batch Operations**: Bulk note creation/deletion

## Migration Guide

### Existing Users

**No breaking changes** - all new features are additive:

- Old chat requests without `source_ids` work unchanged
- Upload endpoint response has new field but maintains backward compatibility
- New endpoints don't affect existing routes

### Database Migration

**Not required** - schemas are created on-the-fly:

- Document properties added via `SET` (null-safe)
- Note nodes created as needed
- No manual migration scripts needed

## References

- Original PR: [Link to PR]
- Related Issues: Source Management Feature Request
- Design Doc: NotebookLM-inspired architecture
