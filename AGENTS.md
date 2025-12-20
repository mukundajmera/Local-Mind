# AGENTS Orchestrator Handbook

## Mission & Scope
- **Product Objective**: Local Mind delivers a fully local NotebookLM-style research assistant.
- **Operating Principles**: Privacy, Speed, and "Zero-Tolerance" Quality. Feature parity must be proven by tests.

## Agent Responsibilities

### 📥 Ingestion Agent (`ingestion.py`)
- **Primary Goal**: Fast, reliable document processing.
- **Mandates**:
    - **Timestamping**: All files MUST be renamed to `stem_{timestamp}.ext` to prevent collisions.
    - **Atomic Rollback**: If Milvus persistence fails, the file MUST NOT be deleted. Verification query required before unlink.
    - **Isolation**: Every vector MUST be tagged with `project_id`.

### 🔍 Retrieval Agent (`main.py` / `chat.py`)
- **Primary Goal**: Accurate RAG answers scoped to the user's focus.
- **Mandates**:
    - **Strict Filtering**: `VectorStore.search()` MUST always apply `project_id` filter if context is set.
    - **Source Awareness**: Only retrieve chunks from `source_ids` if user has selected specific docs.

### 🛡️ Security Agent (`tests/security/`)
- **Primary Goal**: Prevent data leaks.
- **Mandates**:
    - **The Wall**: Project A must never see Project B's documents.
    - **Input Validation**: Rejects malformed UUIDs or path traversal attempts.

## Global Standards
- **Testing**: No feature exists without a test (`tests/unit` or `tests/e2e`).
- **Commits**: Changes to `ingestion.py` require running `tests/unit/test_ingestion.py`.

## Context Switch Table
| Module | Description | Handbook |
| --- | --- | --- |
| Backend | FastAPI, Ingestion, Multi-tenancy | `apps/backend/AGENTS.md` |
| Frontend | Next.js, ProjectSelector, Upload | `apps/frontend/AGENTS.md` |
| Tests | Pytest, Playwright, Security | `tests/AGENTS.md` |
