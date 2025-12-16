# AGENTS Orchestrator Handbook

## Mission & Scope
- **Product Objective:** Local Mind delivers a fully local NotebookLM-style research assistant that performs document ingestion, GraphRAG retrieval, knowledge-graph insights, and podcast-style summaries entirely on user-controlled hardware.
- **Operating Principles:** Uphold privacy, deterministic reproducibility, and GPU/CPU parity across laptops and container stacks. Accelerator discovery (`device_manager.py`) must never fail silently.
- **Instruction Hierarchy:** This file defines global policy. Subdirectories with their own `AGENTS.md` extend or override guidance for work performed inside that scope. When in doubt, start here, then follow the referenced specialist file.

## Global Standards
- **Branching:** Feature branches from `main` using `feature/<ticket>` naming. Keep history linear via rebase before merge.
- **Commit Discipline:** Follow Conventional Commits (`feat:`, `fix:`, `docs:`, etc.). Mention affected module names when relevant.
- **Code Review:** Every change requires PR approval plus evidence of validation (tests, lint, build). Surface GPU configuration when exercising accelerator-dependent paths.
- **Secrets:** Never commit populated `.env` files. Enforce `chmod 600` on any secret templates. Regenerate keys with `openssl rand -hex 32`.
- **Generated Artifacts:** Do not commit `reports/`, `evidence/`, `.pytest_cache/`, `.next/`, `node_modules/`, compiled assets, or large binaries in `data/`.

## Quality Gates
- `./run_tests.sh` – Default run executes unit and integration suites with coverage.
- `./run_tests.sh --all` – Full test run including E2E (requires running compose stack).
- Coverage threshold: Backend branch coverage ≥60% (see `pyproject.toml`). Investigate coverage regressions before merge.
- Frontend changes must run `npm run lint`; build-impacting changes should run `npm run build`.
- Shell automation must retain `set -e` and pass `shellcheck` when feasible.
- Python-driven validation must execute inside the unified `./venv` to ensure consistent dependency resolution.

## Environment Baseline
- **Python:** 3.11 (repo-root virtualenv). Create or refresh the unified `./venv` via `./setup_env.sh`, then activate it with `source ./activate.sh` (or `source venv/bin/activate`) before running services or tests.
- **Node.js:** v20 LTS with npm. Lockfile maintained in `apps/frontend/package-lock.json`.
- **Containers:** Prefer `nerdctl` (`sovereign-ai` namespace). Fallback to Podman or Docker when scripted.
- **GPU Tooling:** NVIDIA Container Toolkit on Linux/WSL2. macOS uses LM Studio at `127.0.0.1:1234` for GPU assist. Update README/SETUP plus this handbook when requirements change.

## Setup & Orchestration
1. Clone repo and copy env template:
   ```bash
   git clone <repo>
   cd Local-Mind
   cp .env.example .env
   chmod 600 .env
   ```
2. Provision runtime (see `SETUP.md` for OS-specific steps).
3. Provision Python environment:
   ```bash
   ./setup_env.sh
   source ./activate.sh
   ```
4. Start full stack:
   ```bash
   bash scripts/init.sh
   ```
   - Script auto-detects container runtime, ensures `data/` volumes, and waits for Neo4j, Milvus, Redis, and backend health.
   - macOS launcher `./start.sh` uses the same unified environment when starting backend/frontend locally.
5. Tear down with `nerdctl --namespace sovereign-ai compose -f infrastructure/nerdctl/compose.yaml down` when finished.

## Context Switch Table
| Module | Description | Local Handbook |
| --- | --- | --- |
| Backend Orchestrator | FastAPI app, Celery workers, device manager. | `apps/backend/AGENTS.md` |
| Frontend Workspace UI | Next.js 15 client, shared components, Playwright e2e. | `apps/frontend/AGENTS.md` |
| Voice Service | Kokoro-based TTS FastAPI microservice. | `apps/voice-service/AGENTS.md` |
| Infrastructure Compose | nerdctl/podman/docker compose definitions and infra scripts. | `infrastructure/nerdctl/AGENTS.md` |
| Automation Scripts | Bootstrap, watchdog, and setup automation. | `scripts/AGENTS.md` |
| Test Suites | Pytest orchestration, markers, stress tooling. | `tests/AGENTS.md` |

Always consult the relevant module file before executing commands within that directory. Modules may define additional linting, build, or deployment workflow requirements. Reference `QUICKSTART.md` and `ENV_CONSOLIDATION.md` for launchers and environment expectations shared across modules.

## Configuration & Secrets Governance
- Keep `.env.example` synchronized with code changes, compose files, and documentation (`README.md`, `SETUP.md`).
- `infrastructure/nerdctl/.env` stores container credentials; guard with restrictive permissions and never check in real secrets.
- Any port exposure or credential update must be reflected in `README.md`, `SETUP.md`, this handbook, and the affected module handbook.

## Release & Deployment Coordination
- Backend version source of truth: `pyproject.toml` (`project.version`). Update alongside API-breaking changes.
- Frontend versioning: `apps/frontend/package.json`. Keep aligned when publishing artifacts or tagging releases.
- Document compose/service changes in `REPAIR_LOG.md` and summarize mitigations in PR descriptions.
- Production deployment runbooks live in `DEPLOYMENT.md` and `OPERATIONS.md`; ensure changes remain accurate.

## Escalation & Maintenance
- Update this file when global policies, technology baselines, or cross-cutting workflows change.
- Surface GPU topology or compose concerns to SRE points listed in `REPAIR_LOG.md` before merging breaking moves.
- If module-level instructions conflict with this file, escalate in PR discussion and harmonize documentation before merge.

Document Owner: Principal maintainer or first responder modifying multi-module workflows. Treat this handbook as the authoritative router for all submodule instructions.
