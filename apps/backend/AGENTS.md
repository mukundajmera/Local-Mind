# Backend Handbook

> This module belongs to the Local Mind monorepo. For global release, security, and deployment policy, start with `../../AGENTS.md`.

## Responsibility & Interfaces
- **Purpose:** FastAPI orchestrator powering ingestion, retrieval, notebook management, and Celery-based pipelines.
- **External Consumers:** Frontend workspace (`apps/frontend`), voice service (`apps/voice-service`), and automation scripts call REST endpoints and Celery tasks exposed here.
- **Contracts:** Public API schemas defined in `schemas.py` and `services/`. Coordinate breaking changes with frontend owners and bump backend version in `pyproject.toml`.

## Local Environment
- Python 3.11 required. Use the module-local virtualenv scaffold under `venv/` or create a fresh one.
- Install dependencies:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  pip install -r requirements_device_manager.txt  # optional GPU extras
  ```
- Export environment variables via repo root `.env` or module-specific overrides before running services or tests.

## Development Workflow
- **Run API locally:**
  ```bash
  source venv/bin/activate
  uvicorn main:app --reload --port 8000
  ```
- **Celery worker:**
  ```bash
  source venv/bin/activate
  celery -A services.ingestion worker --loglevel=info
  ```
- **Structured Logging:** Uses `structlog` configured in `logging_config.py`. Avoid `print` statements; leverage provided loggers.
- **Device Manager:** `device_manager.py` must log and fallback deterministically. Update `requirements_device_manager.txt` if new GPU backends are introduced.

## Testing & Quality
- Unit tests:
  ```bash
  source venv/bin/activate
  pytest tests/unit -m "unit"
  ```
- Integration tests (requires drivers or mock services depending on markers):
  ```bash
  source venv/bin/activate
  pytest tests/integration -m "integration"
  ```
- Full backend suite from repo root: `./run_tests.sh --unit` or `--all` for e2e. Ensure backend-specific failures are resolved before requesting review.
- Maintain backend branch coverage ≥60%. Inspect `reports/coverage_full/index.html` after full runs.

## Integration with Parent Repo
- Changing serialized response models, task signatures, or configuration defaults requires coordination with:
  - Frontend team (update clients/tests).
  - Infrastructure docs (`README.md`, `SETUP.md`, `DEPLOYMENT.md`).
  - Root `AGENTS.md` context table if new services or ports appear.
- Update `pyproject.toml` `project.version` when introducing API-breaking changes.
- When new environment variables are required, update `.env.example`, compose files, and highlight in PR summaries.

## Git & Submodule Behavior
- This directory is part of the main repository (not a separate submodule). Commit changes on your feature branch and push to origin.
- Keep `requirements*.txt` sorted and deduplicated. Regenerate lock-style exports if CI scripts expect them.
- Do not remove the placeholder `venv/` directory (contains README stub for tooling compatibility).

## Common Commands
- Format (if needed): `black` and `isort` are optional; follow project preferences when invoked in CI.
- Lint (optional but recommended): `ruff check .`
- Run health check locally:
  ```bash
  curl http://localhost:8000/health
  ```

## Escalation
- Device detection regressions: loop in SRE contacts (see `../../REPAIR_LOG.md`). Provide GPU model and driver details.
- Database connectivity changes: coordinate with infra owners before altering connection settings in `config.py`.
- Celery queue behavior: ensure Redis/Milvus/Neo4j availability when modifying task topology.

Stay aligned with root policies and update this handbook whenever backend-specific workflows change.
