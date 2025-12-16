# Infrastructure Compose Handbook

> Part of Local Mind. For global policies, release expectations, and cross-service coordination, refer to `../../AGENTS.md`.

## Scope
- Manages container orchestration via `nerdctl`/Podman/Docker compose, primarily defined in `compose.yaml`.
- Configures Redis, Neo4j, Milvus, MinIO, and optional frontend. Coordinates volumes bound to `../../data/`.

## Usage
- **Startup:**
  ```bash
  nerdctl --namespace sovereign-ai compose -f infrastructure/nerdctl/compose.yaml up -d
  ```
  Adjust command to `podman compose` or `docker compose` if using alternative runtimes.
- **Shutdown:**
  ```bash
  nerdctl --namespace sovereign-ai compose -f infrastructure/nerdctl/compose.yaml down
  ```
- **Logs:** `nerdctl --namespace sovereign-ai compose -f infrastructure/nerdctl/compose.yaml logs -f`

## Configuration
- Environment variables loaded from `../../.env` and `infrastructure/nerdctl/.env`. Keep templates synchronized and apply `chmod 600` to secret-bearing files.
- Network: `sovereign-net` (172.28.0.0/16). Update docs and root handbook if subnet or network name changes.
- Volume bindings map to `../../data/*`. Do not commit generated contents.

## Health Checks
- Services rely on HTTP/WGET health checks. Maintain parity with actual service endpoints when modifying ports or routes.
- Neo4j start period is 120s to prevent false negatives. Adjust with caution and document rationale.

## Integration Expectations
- Compose modifications require updates to:
  - Root `AGENTS.md` context table.
  - `README.md`, `SETUP.md`, and `REPAIR_LOG.md`.
  - Service-specific handbooks when ports/env vars change.
- When adding new services, create a module-specific `AGENTS.md` if the directory contains additional tooling.

## Git Practices
- Preserve comment headers explaining runtime prerequisites.
- Keep base images pinned (Redis, Neo4j, MinIO, Milvus). Document updates in PR descriptions and `REPAIR_LOG.md`.
- Do not store credentials in plain text inside compose files; use environment variables.

## Escalation
- Compose bring-up failures: capture `nerdctl compose ps` and logs, then coordinate with SRE contacts listed in `../../REPAIR_LOG.md`.
- GPU passthrough issues: verify `nvidia-smi` availability and runtime configuration defined in `scripts/init.sh`.

Maintain this handbook whenever compose topology, service exposures, or environment templates evolve.
