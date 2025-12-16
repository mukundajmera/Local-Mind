# Tests Handbook

> Part of Local Mind. Consult `../AGENTS.md` for global standards and release coordination before working within this directory.

## Scope
- Hosts pytest suites under `unit/`, `integration/`, `backend/`, `e2e/`, and `stress/` along with shared fixtures in `conftest.py`.
- Manages test dependencies listed in `requirements-test.txt`.

## Running Tests Locally
- **Install deps:**
  ```bash
  pip install -r requirements-test.txt
  ```
- **Unit tests:** `pytest unit -m "unit"`
- **Integration tests:** `pytest integration -m "integration"`
- **Backend tests:** `pytest backend`
- **E2E tests:** Requires running stack (`nerdctl compose up`). Set `E2E_ACTIVE=1` or use `./run_tests.sh --all` from repo root.
- **Stress tests:** Optional Locust scenario `locust -f stress/chaos.py --host=http://localhost:8000`.

## Markers & Configuration
- Markers defined in `pytest.ini`: `unit`, `integration`, `e2e`, `slow`.
- Strict markers enforced (`--strict-markers`). Ensure new tests declare appropriate markers.
- Coverage collected for backend (`apps/backend`) with branch coverage enabled. Respect `omit` rules defined in `pyproject.toml`.

## Workflow Expectations
- Keep tests deterministic; mock external services in unit tests.
- Integration tests may hit real drivers (Neo4j, Milvus) but must handle offline environments gracefully or be skipped via markers.
- Add new suites through `run_tests.sh` for CI parity instead of bespoke scripts.

## Git Practices
- Do not commit generated coverage reports or evidence archives. `run_tests.sh` stores outputs under `../reports` and `../evidence`; ensure these remain in `.gitignore`.
- Organize new tests under the correct subdirectory with descriptive filenames (`test_<area>.py`).

## Escalation
- For flaky tests, capture diagnostics and coordinate with module owners (backend/frontend) before disabling.
- Performance regressions in `stress/chaos.py` should be documented in `REPAIR_LOG.md` with mitigation steps.

Update this handbook when test tooling, markers, or suite layout changes.
