# Local Mind Functional Documentation

## Overview
Local Mind is a fully local research assistant designed to transform unstructured documents into actionable knowledge. The system ingests user-provided content, enriches it with retrieval-augmented generation (RAG), surfaces insights through an interactive knowledge graph, and produces podcast-style audio summaries. All data processing and AI inference run on the user’s own hardware to preserve privacy and ensure deterministic reproducibility.

## User Personas
- **Researcher/Analyst:** Uploads documents, explores relationships, and asks questions to produce reports or briefs.
- **Knowledge Curator:** Maintains collections, tags entities, and adjusts ingestion parameters to keep information current.
- **Executive Listener:** Consumes generated podcast summaries and reviews key takeaways without reading source material.

## Core User Journeys
1. **Document Ingestion**
   - User selects or drags files (PDF/TXT/HTML) into the workspace.
   - Frontend streams file metadata to the backend orchestrator.
   - Orchestrator validates file type, stores the raw document, and schedules a Celery ingestion task.
   - Ingestion pipeline chunks text, computes embeddings, extracts entities, and persists structured data to Milvus (vectors) and Neo4j (graph).

2. **Knowledge Exploration**
   - User queries the knowledge base via chat or search UI.
   - Backend orchestrator performs hybrid retrieval combining vector similarity (Milvus) and graph traversal (Neo4j) with reciprocal rank fusion.
   - Retrieved context feeds the local LLM which generates grounded responses with citations.
   - Frontend displays answers alongside linked source passages and graph nodes.

3. **Insight Summarization**
   - User selects documents or entities to summarize.
   - Backend orchestrator crafts a dialogue outline and calls the LLM to produce multi-speaker script segments.
   - Audio service (Kokoro TTS) synthesizes speech for each persona.
   - Frontend streams audio chunks via WebSocket for real-time playback.

4. **System Monitoring & Recovery**
   - `scripts/watchdog.sh` supervises running services and restarts unhealthy containers.
   - `/health` endpoint exposes orchestrator readiness details for compose health checks.
   - Logs aggregate under `logs/` and container logs accessible via `nerdctl compose logs`.

## Functional Components
### Frontend (`apps/frontend`)
- Next.js 15 workspace with React server components and Tailwind styling.
- Manages file uploads, chat sessions, graph visualization, and audio playback.
- Communicates with backend via REST (FastAPI) and WebSockets for streaming responses and audio.

### Backend Orchestrator (`apps/backend`)
- FastAPI application exposing REST endpoints for health checks, ingestion, chat, audio generation, and notebook management.
- Celery workers execute asynchronous pipelines for ingestion, retrieval, and audio scripting tasks.
- `device_manager.py` selects GPU/CPU execution backends, ensuring safe fallbacks and deterministic logging.

### Voice/TTS Service (`apps/voice-service`)
- Dedicated FastAPI service wrapping Kokoro TTS models.
- Generates speech from LLM-produced scripts, streaming audio chunks to the orchestrator.

### Data Plane
- **Neo4j:** Stores entity graphs, relationships, and metadata for graph-based reasoning.
- **Milvus:** Houses vector embeddings for semantic search and similarity scoring.
- **Redis:** Provides task queue backend for Celery and cache for transient state.

### Infrastructure (`infrastructure/nerdctl`)
- Compose stack orchestrates backend, frontend, databases, and auxiliary services with GPU support.
- `.env.example` defines environment variables for local deployments; `compose.yaml` binds services and volumes.

### Automation (`scripts/`)
- `init.sh` provisions required volumes, launches containers, and waits for services to become ready.
- `watchdog.sh` monitors container health and performs restarts to maintain availability.

### Testing (`tests/`)
- Pytest suites covering unit, integration, and stress scenarios.
- `run_tests.sh` orchestrates test execution with coverage reporting and optional full-suite runs.

## Key External Dependencies
- **vLLM / Llama 3.2** for language generation.
- **Kokoro TTS** for voice synthesis.
- **Neo4j**, **Milvus**, **Redis** for data persistence and retrieval.
- **FastAPI**, **Celery**, **Next.js** for service orchestration and UI.

## Environment & Configuration
- Root `.env` configures model selection, quantization settings, context windows, and feature toggles (e.g., `TTS_ENABLED`).
- `infrastructure/nerdctl/.env` stores container credentials and port bindings; update alongside documentation when changes occur.
- GPU memory requirements dictate quantization and context window defaults; reference README VRAM guidance for tuning.

## Operational Flows
1. **Startup** via `scripts/init.sh`
   - Ensures `.env` files exist.
   - Creates persistent volumes under `data/`.
   - Starts compose stack and waits for `apps/backend` health.
2. **Runtime**
   - Users interact through the frontend.
   - Backend orchestrator coordinates data plane and AI services.
   - Audio playback streaming leverages WebSockets for low-latency delivery.
3. **Shutdown**
   - `nerdctl compose down` stops containers, preserving volumes.

## Failure Modes & Mitigations
- **Model download stalls:** Manual pre-fetch via HuggingFace CLI; verify storage paths.
- **GPU OOM:** Lower `CONTEXT_WINDOW`, enable 4-bit quantization, or disable TTS.
- **Service crash:** Watchdog attempts restart; review container logs and health endpoint.
- **Port conflicts:** Adjust `compose.yaml` ports and mirror changes in docs.

## Future Extensions
- Fine-grained access control for shared deployments.
- Incremental ingestion with change detection.
- Enhanced analytics and usage dashboards within the frontend.
- Offline packaging of models for air-gapped environments.

