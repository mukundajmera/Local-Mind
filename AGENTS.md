# AGENTS Handbook

## Mission & Vision
- **Product goal:** Local Mind delivers a fully local NotebookLM-style research assistant featuring RAG search, knowledge graph insights, and podcast-style summaries without ever leaving the host machine.
- **Operating principle:** Prioritize privacy and deterministic reproducibility; every change must be safe to run on developer laptops with GPUs and in containerized stacks.

## Architecture Snapshot
- **Frontend:** Next.js 15 (`apps/frontend`) renders the workspace UI and talks to the orchestrator via REST/WebSocket.
- **Backend Orchestrator:** FastAPI + Celery service (`apps/backend`) coordinates ingestion, retrieval, LLM, and audio pathways.
- **Voice/TTS Engine:** FastAPI service (`apps/voice-service`) reserved for Kokoro-based synthesis.
- **Data Plane:** Neo4j (graph), Milvus (vector), Redis (queue/cache). All containerized through `infrastructure/nerdctl/compose.yaml` and backed by volumes in `data/`.
- **Accelerator Management:** `device_manager.py` picks the optimal GPU/CPU backend at runtime and must never silently fail.

## Directory Responsibilities
| Path | Ownership & Purpose | Guardrails |
| --- | --- | --- |
| `apps/backend/` | FastAPI app, Celery workers, device manager. | Maintain Python 3.11 compatibility; keep runtime deps in `requirements.txt`; do not commit venv artifacts beyond existing placeholder.
| `apps/frontend/` | Next.js interface. | Never edit `node_modules/` or `.next/`; keep shared UI primitives in `components/`.
| `apps/voice-service/` | Dedicated TTS microservice. | Requires NVIDIA GPU runtime; coordinate model cache under `/app/models` volume.
| `infrastructure/` | Compose, tuning utilities, host scripts. | Update `compose.yaml` and `.env` templates together; document any port exposure changes.
| `scripts/` | Shell/PowerShell automation (init, setup, watchdog). | Preserve `set -e`/error handling conventions; keep scripts idempotent and note deviations inline when behavior differs from README/SETUP instructions.
| `tests/` | Unit, integration, e2e, stress suites. | Respect pytest markers; keep load tools (Locust) optional via requirements.
| `data/` | Persistent volumes for services. | Treat as runtime state; avoid committing large binaries or personal data.
| `logs/` | Host-level log output bucket. | Safe to ignore if empty; do not version control generated logs or `reports/`/`evidence/` artifacts.

## Environment & Toolchains
| Domain | Runtime | Notes |
| --- | --- | --- |
| Backend | Python 3.11 | Manage deps via `apps/backend/requirements.txt`; optional extras in `requirements_device_manager.txt`.
| Frontend | Node.js 20 + npm | Lockfile: `package-lock.json`; lint via `npm run lint` (ESLint + Next rules).
| Voice service | Python 3.11 on CUDA 12.1 base | Expects NVIDIA GPU with compatible drivers.
| Containers | nerdctl/podman/docker compose | Default namespace: `sovereign-ai`; scripts auto-detect runtime.
| Testing | pytest 8.x, pytest-asyncio, pytest-cov | Use `tests/requirements-test.txt` for a clean test env.
| Load | Locust | Optional; only required for stress suite.

GPU guidance lives in `README.md` VRAM tables; macOS Apple Silicon relies on LM Studio (see `scripts/init.sh` and `REPAIR_LOG.md`).

## Setup & Runbook
1. **Clone & bootstrap:**
   ```bash
   git clone <repo>
   cd Local-Mind
   cp .env.example .env  # adjust secrets
   ```
2. **Install tooling:**
   - Linux/WSL2: NVIDIA Container Toolkit + nerdctl (see `SETUP.md`).
   - macOS: Use Lima + nerdctl or Podman; start LM Studio on `127.0.0.1:1234` for GPU assist per `scripts/init.sh` and `REPAIR_LOG.md`.
3. **Start full stack:** `bash scripts/init.sh`
   - Script auto-selects podman/nerdctl/docker.
   - Ensures volume folders under `data/` exist.
   - Waits for Neo4j, backend, frontend (if enabled).
4. **Manual service runs:**
   - Backend only: `bash scripts/start_backend.sh` (requires `apps/backend/venv`).
   - Frontend dev: `cd apps/frontend && npm install && npm run dev`.
   - Voice service: build/run via compose or `uvicorn main:app --host 0.0.0.0 --port 8880` after installing requirements on a CUDA-capable host.

## Configuration & Secrets
- `.env` (root) drives local dev defaults; never commit populated secrets. Regenerate keys with `openssl rand -hex 32`.
- `infrastructure/nerdctl/.env` is required for compose (Neo4j/MinIO credentials); ensure `chmod 600`.
- Sensitive defaults in `.env.example` (e.g., `NEO4J_PASSWORD=localmind2024`) are for local sandboxes only; override for shared environments.
- Keep configuration changes synchronized across templates, scripts, and documentation. When adjusting ports or credentials, update `README.md`, `SETUP.md`, and this handbook.

## Coding Standards
- **Python:** Follow PEP 8, prefer type hints, and keep logging structured (see `structlog` usage in services). Do not add inline `print`; use configured loggers. Maintain coverage annotations consistent with `pyproject.toml` exclusions.
- **FastAPI:** Keep routers simple; surface new dependencies via `apps/backend/requirements.txt` and document env toggles in `.env.example`.
- **Celery tasks:** Ensure idempotency; guard GPU-intensive calls with device checks (`device_manager.py`).
- **TypeScript/React:** Adhere to Next.js conventions; rely on Tailwind utilities defined in `globals.css`. Run `npm run lint` before submitting.
- **Shell scripts:** Preserve strict mode (`set -e`), existing colorized logging helpers, and cross-platform compatibility. Keep inline comments updated when behavior diverges from README/SETUP instructions.
- **Docs:** Update `README.md` and `SETUP.md` when altering onboarding flows, GPU requirements, or compose behavior.

## Quality Gates
- **Tests:** All Python changes require relevant pytest suites (`./run_tests.sh --unit`, `--all` for full coverage) to pass with no new failures. Frontend changes must run `npm run lint` and, when build-affecting, `npm run build`.
- **Coverage:** Backend statements must meet `fail_under = 60` branch coverage (see `pyproject.toml`). Investigate deltas when `reports/coverage_full/index.html` drops below prior baseline.
- **Static checks:** Adopt new lint/format tooling through PR consensus; document activation steps here once enforced.
- **Artifacts:** Never commit generated `reports/`, `evidence/`, `.pytest_cache/`, `.next/`, or `node_modules/`.

## Testing Strategy
- **Entry point:** `./run_tests.sh`
  - Default: unit + integration.
  - `--all`: full pytest suite with coverage reports (`reports/`).
  - Skips e2e automatically if backend is unreachable; start containers first.
- **Pytest layout:**
  - `tests/unit` – strict mocks, marked `@pytest.mark.unit`.
  - `tests/integration` – hits real drivers; avoid external network.
  - `tests/e2e` – require running stack (`E2E_ACTIVE=1`).
  - `tests/stress/chaos.py` – run with Locust (`locust -f tests/stress/chaos.py --host=http://localhost:8000`).
- **Coverage:** Branch coverage measured on `apps/backend`; threshold `fail_under = 60`. Inspect `reports/coverage_full/index.html` for gaps.
- **Troubleshooting:**
  - Missing tooling? Install with `pip install -r tests/requirements-test.txt`.
  - GPU OOM: tune `QUANTIZATION` and `CONTEXT_WINDOW` in `.env` before re-running.
  - Slow tests: use markers (`pytest -m "unit"`).

## Build, Packaging & Deployment
- **Containers:** `infrastructure/nerdctl/compose.yaml` orchestrates Redis, Neo4j, Milvus, MinIO, and (optionally) frontend. Healthchecks rely on `curl/wget`; keep endpoints stable.
- **Dockerfiles:** Located per service; ensure base images remain pinned (Python 3.11 slim, node:20-alpine, CUDA 12.1). When altering dependencies, rebuild via compose or `docker build` locally.
- **Artifacts:**
  - Backend listens on `:8000`.
  - Frontend serves on `:3000` (commented out in compose until build issues resolved; see `REPAIR_LOG.md`).
  - Voice service targets `:8001` but not wired into compose yet; coordinate deployment steps before exposing.
- **Versioning:** `pyproject.toml` version is canonical for backend. Align npm version in `package.json` if publishing artifacts. Tag releases on `main` using semver and note image updates in `REPAIR_LOG.md` + this handbook.
- **Init script fallback:** `scripts/init.sh` can generate a minimal compose if missing—do not rely on this in repo; keep the curated compose file committed.

## Data & Assets
- Model weights download on first run (~13GB). Cache under `data/models` or `~/.cache/huggingface` for manual preloading.
- `data/` subfolders map to container volumes (Neo4j logs/import, Milvus, Redis, uploads). Treat as runtime state and avoid large diff uploads.
- Logs: service logs stream via compose; host-level logs can go to `logs/`. Do not check in generated evidence packages from `run_tests.sh` (`reports/`, `evidence/`).

## Infrastructure Notes
- Default compose network: `sovereign-net` (172.28.0.0/16). Update documentation if subnet changes.
- Ports currently exposed:
  - Redis `6379`, Neo4j `7474/7687`, Milvus `19530`.
- Healthcheck timings grew after macOS repairs; Neo4j start period is 120s to avoid false negatives.
- REPAIR_LOG highlights disabled frontend build stage; resolve missing panel components before re-enabling `interface` service.
- For Apple Silicon: LM Studio at `:1234` supplies GPU-backed inference; check via `curl http://127.0.0.1:1234/v1/models`.

## Contribution Workflow
1. Branch from `main` (e.g., `feature/<ticket>`).
2. Update docs & config templates alongside code changes.
3. Run relevant tests (`./run_tests.sh --unit` or targeted pytest markers, plus `npm run lint` for frontend changes).
4. Attach coverage or HTML reports if CI requires.
5. Ensure compose/services build locally before raising PR; share reproduction steps for GPU-dependent work.
6. Submit PR summarizing scope, tests run, and GPU configuration used.

## Quick Command Reference
- `bash scripts/init.sh` – provision volumes and start stack.
- `nerdctl --namespace sovereign-ai compose -f infrastructure/nerdctl/compose.yaml up -d` – manual bring-up.
- `./run_tests.sh --all` – full pytest suite with coverage artifacts.
- `cd apps/frontend && npm run dev` – Next.js dev server.
- `cd apps/backend && uvicorn main:app --reload --port 8000` – local backend (venv required).
- `locust -f tests/stress/chaos.py --host=http://localhost:8000` – stress chaos suite.
- `nvidia-smi` / `lm studio` UI – monitor GPU allocation.

## Escalation & Handbook Maintenance
- Update this document whenever you:
  - Add/remove services, ports, or volumes.
  - Change required environment variables or secret handling.
  - Introduce new tooling, test suites, or quality gates.
- Flag breaking infra changes in `REPAIR_LOG.md` and mirror mitigations here.
- If uncertain about GPU readiness or compose topology, consult SRE contact points documented in `REPAIR_LOG.md` before merging. Surface policy changes (branch naming, release cadence, secrets handling) in PR summaries and append the relevant section here.

## Module-Specific Guidance
- **Device Manager (`apps/backend/device_manager.py`):** Keep discovery graceful; ensure new backend support still yields deterministic scoring and logs warnings instead of crashing.
- **Ingestion & Graph services:** Mock external calls in unit tests; integration tests may hit actual Neo4j/Milvus drivers—guard them with markers.
- **Voice service:** Heavy torch deps; prefer building in CUDA-enabled CI. Document new models or voices in `.env.example` and README feature sections.
- **Frontend panels (`apps/frontend/components/panels/*`):** When refactoring layout, update imports in `app/page.tsx` to avoid Docker build regressions noted in `REPAIR_LOG.md`.
- **Scripts (`scripts/*.sh`, `scripts/setup/*`):** Preserve echo styling, exit handling, and cross-shell compatibility. Test on zsh+bash where possible.
- **Tests:** Maintain marker discipline (`unit`, `integration`, `e2e`, `slow`). Extend `run_tests.sh` helper instead of ad-hoc commands to keep CI parity.

---
Document owner: current maintainer or first responder touching infrastructure. Keep this handbook authoritative; when in doubt, update it before shipping changes.
