# API Reference

**Complete REST API documentation for Local Mind**

Base URL: `http://localhost:8000`

---

## Table of Contents

- [Authentication](#authentication)
- [Health & System](#health--system)
- [Sources Management](#sources-management)
- [Chat](#chat)
- [Notes](#notes)
- [Briefings](#briefings)
- [Projects](#projects)
- [Error Handling](#error-handling)

---

## Authentication

**Current Status**: ⚠️ Not implemented. All endpoints are publicly accessible.

**Future**: JWT-based authentication will be added. See [Security Guide](../SECURITY.md#authentication--authorization).

---

## Health & System

### GET /health

Check system health and service status.

**Response 200 (Healthy):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "milvus": "healthy",
    "redis": "healthy"
  }
}
```

**Response 503 (Degraded):**
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "services": {
    "milvus": "unhealthy",
    "redis": "healthy"
  }
}
```

### GET /metrics

Prometheus metrics endpoint.

**Response**: Prometheus text format

---

## Sources Management

### POST /api/v1/sources/upload

Upload a document for ingestion.

**Request:**
```http
POST /api/v1/sources/upload?project_id=abc-123
Content-Type: multipart/form-data

file: <binary data>
```

**Parameters:**
- `project_id` (query, optional): Project UUID to associate document with

**Response 202:**
```json
{
  "task_id": "def-456",
  "status": "accepted",
  "message": "Upload accepted. Poll /api/v1/upload/{task_id}/status for progress."
}
```

**Errors:**
- `400`: Invalid file format
- `500`: Upload failed

### GET /api/v1/upload/{task_id}/status

Get upload task status.

**Response:**
```json
{
  "status": "completed",
  "progress": 100,
  "stage": "done",
  "doc_id": "abc-123",
  "filename": "paper_1734720000.pdf"
}
```

**Status Values:**
- `processing`: Upload in progress
- `completed`: Upload successful
- `failed`: Upload failed

**Stage Values:**
- `uploaded`: File saved
- `parsing`: Extracting text
- `embedding`: Generating vectors
- `storing`: Saving to database
- `done`: Complete

### GET /api/v1/sources

List all sources.

**Parameters:**
- `project_id` (query, optional): Filter by project

**Response:**
```json
{
  "sources": [
    {
      "id": "abc-123",
      "filename": "paper_1734720000.pdf",
      "upload_date": "2024-12-20T18:00:00Z",
      "file_size_bytes": 1048576,
      "project_id": "proj-123"
    }
  ]
}
```

### DELETE /api/v1/sources/{doc_id}

Delete a source document.

**Response 200:**
```json
{
  "status": "success",
  "doc_id": "abc-123",
  "chunks_deleted": 42
}
```

**Errors:**
- `404`: Document not found
- `500`: Deletion failed

---

## Chat

### POST /api/v1/chat

Chat with your documents using RAG.

**Request:**
```json
{
  "message": "What are the key findings?",
  "source_ids": ["abc-123", "def-456"],
  "strategies": ["sources"],
  "project_id": "proj-123"
}
```

**Parameters:**
- `message` (required): User query
- `source_ids` (optional): Filter search to specific documents
- `strategies` (optional): Search strategies (default: `["sources"]`)
- `project_id` (optional): Filter by project

**Response:**
```json
{
  "response": "The key findings are...",
  "sources": [
    {
      "id": "chunk-1",
      "score": 0.89,
      "source": "vector",
      "doc_id": "abc-123"
    }
  ],
  "context_used": true,
  "filtered_sources": true,
  "searched_source_ids": ["abc-123", "def-456"]
}
```

**Errors:**
- `400`: Invalid request
- `500`: LLM service error

---

## Notes

### POST /api/v1/notes

Create a new note.

**Request:**
```json
{
  "content": "Important insight from the paper",
  "tags": ["research", "important"],
  "source_citation_id": "chunk-123"
}
```

**Response:**
```json
{
  "note_id": "note-123",
  "content": "Important insight from the paper",
  "tags": ["research", "important"],
  "source_citation_id": "chunk-123",
  "created_at": "2024-12-20T18:00:00Z"
}
```

### GET /api/v1/notes

List all notes.

**Response:**
```json
[
  {
    "note_id": "note-123",
    "content": "Important insight",
    "tags": ["research"],
    "created_at": "2024-12-20T18:00:00Z"
  }
]
```

### DELETE /api/v1/notes/{note_id}

Delete a note.

**Response:**
```json
{
  "status": "success",
  "note_id": "note-123"
}
```

---

## Briefings

### GET /api/v1/sources/{doc_id}/briefing

Get AI-generated document summary.

**Response:**
```json
{
  "summary": "This paper explores...",
  "key_topics": [
    "Transformer architecture",
    "Attention mechanisms",
    "BERT vs GPT"
  ],
  "suggested_questions": [
    "What are the key differences between BERT and GPT?",
    "How do attention mechanisms work?",
    "What benchmarks were used?"
  ],
  "doc_id": "abc-123",
  "generated_at": "2024-12-20T18:00:00Z"
}
```

**Errors:**
- `404`: Briefing not found (still generating)
- `500`: Generation failed

---

## Projects

### GET /api/v1/projects

List all projects.

**Response:**
```json
{
  "projects": [
    {
      "id": "proj-123",
      "name": "Research",
      "created_at": "2024-12-20T18:00:00Z"
    }
  ]
}
```

### POST /api/v1/projects

Create a new project.

**Request:**
```json
{
  "name": "Work"
}
```

**Response:**
```json
{
  "id": "proj-456",
  "name": "Work",
  "created_at": "2024-12-20T18:00:00Z"
}
```

---

## Error Handling

All errors follow this format:

```json
{
  "error": {
    "error_type": "ValidationError",
    "message": "Invalid project_id format",
    "context": {
      "field": "project_id",
      "value": "invalid"
    }
  },
  "path": "/api/v1/sources"
}
```

**Common Error Types:**
- `ValidationError` (400): Invalid input
- `DatabaseConnectionError` (503): Database unavailable
- `IngestionError` (500/503): Document processing failed
- `LLMServiceError` (500): AI generation failed
- `SearchError` (500): Vector search failed

---

## Code Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8000"

# Upload document
with open("paper.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/v1/sources/upload",
        files={"file": f},
        params={"project_id": "proj-123"}
    )
    task_id = response.json()["task_id"]

# Check status
status = requests.get(
    f"{BASE_URL}/api/v1/upload/{task_id}/status"
).json()

# Chat
chat_response = requests.post(
    f"{BASE_URL}/api/v1/chat",
    json={
        "message": "Summarize this paper",
        "source_ids": [status["doc_id"]]
    }
).json()

print(chat_response["response"])
```

### JavaScript

```javascript
const BASE_URL = "http://localhost:8000";

// Upload document
const formData = new FormData();
formData.append("file", fileInput.files[0]);

const uploadResponse = await fetch(
  `${BASE_URL}/api/v1/sources/upload?project_id=proj-123`,
  {
    method: "POST",
    body: formData
  }
);
const { task_id } = await uploadResponse.json();

// Check status
const statusResponse = await fetch(
  `${BASE_URL}/api/v1/upload/${task_id}/status`
);
const status = await statusResponse.json();

// Chat
const chatResponse = await fetch(
  `${BASE_URL}/api/v1/chat`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: "Summarize this paper",
      source_ids: [status.doc_id]
    })
  }
);
const chat = await chatResponse.json();

console.log(chat.response);
```

---

**Full OpenAPI Spec**: Visit `http://localhost:8000/docs` for interactive API documentation.
