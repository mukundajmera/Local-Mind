# Frontend Workspace Handbook

> Part of the Local Mind monorepo. Reference `../../AGENTS.md` for global policies, release coordination, and cross-service workflows.

## Module Scope
- **Purpose:** Next.js 15 workspace that delivers the Local Mind UI, including ingestion flows, chat workspace, graph visualizations, and audio playback.
- **Integration Points:** Consumes backend REST/WebSocket APIs (port 8000) and streams audio produced by the voice service. Build artifacts are not committed; deployment packages are generated via Next.js build.

## Local Development
- **Runtime:** Node.js 20 LTS with npm.
- **Install dependencies:**
  ```bash
  npm install
  ```
- **Dev server:**
  ```bash
  npm run dev
  ```
  Access via `http://localhost:3000`.
- **Environment:** Read runtime config from repo `.env`. Add any frontend-specific variables to `.env.example` and document usages in `README.md` and root handbook.

## Quality Gates
- **Lint:** `npm run lint` (ESLint + Next rules). Required before PR approval.
- **Build:** `npm run build` whenever changes may affect production build output or Docker image.
- **Playwright e2e:** Tests live in `e2e/` with config in `playwright.config.ts`. Coordinate with QA when unskipping tests tracked in `QA_DEBT.md`.
- **Styling:** Use Tailwind classes defined in `app/globals.css`. Shared UI primitives belong in `components/`. Avoid editing `node_modules/` or `.next/`.

## Working Within This Directory
- Keep relative imports stable; update `app/page.tsx` if panel structures change.
- Follow `QA_DEBT.md` guidance when implementing features tied to pending tests (checkbox selection, notes toggle, message pinning).
- Respect TypeScript project references defined in `tsconfig.json`; run `npm run lint -- --fix` judiciously.

## Integration with Parent Repo
- Backend contract changes (API routes, schemas) require synchronized updates in `apps/backend`. Validate end-to-end via `./run_tests.sh --all` at repo root or targeted Playwright runs.
- Update root `AGENTS.md` context table if new frontend packages or subdirectories warrant their own specialization.
- Coordinate version bumps in `package.json` when releasing artifacts or updating published components.

## Git Practices
- This directory is part of the main repo; standard branching applies. Do not commit `.next/`, `node_modules/`, or Playwright trace artifacts (`test-results/`).
- Lock dependencies via `package-lock.json`. Run `npm install --package-lock-only` if manual edits are needed.

## Troubleshooting
- **Port conflicts:** Adjust Next.js dev port via `package.json` script overrides and update docs accordingly.
- **Env mismatches:** Ensure `.env` and `.env.local` align; frontend references environment variables prefixed with `NEXT_PUBLIC_`.
- **Build failures inside compose:** Frontend container is disabled pending panel fixes (see `../../REPAIR_LOG.md`). Document progress when re-enabling in compose.

## Escalation
- UI regressions or unresolved QA debt: coordinate with design/QA leads noted in repository issue tracker.
- API integration issues: sync with backend maintainers before altering fetch logic in `lib/` or `hooks/`.
- Audio playback disruptions: confirm voice service availability and WebSocket handshake details.

Update this handbook when frontend build, lint, or integration workflows change so agents operating here have precise, local guidance.
