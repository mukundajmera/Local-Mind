# Local Mind - macOS Deep Clean & Startup Debug Log

**Date:** 2025-12-14  
**Platform:** macOS (arm64 Apple Silicon)  
**Engineer:** Senior MacOS Full-Stack SRE Protocol

---

## Phase 1 · Environment Scan

- **CPU Architecture:** `arm64` (via `uname -m`).
- **Node.js/npm:** Homebrew Node 25.2.1 and npm 11.6.2 confirmed at `/opt/homebrew/bin`. Ensure `eval "$(${HOMEBREW_PREFIX:-/opt/homebrew}/bin/brew shellenv)"` runs in shells so binaries resolve globally.
- **Python:** 3.12.10 (system) with project venv at `apps/backend/venv`.
- **Critical Ports:** `:3000` (frontend) and `:8000` (backend) free prior to launch. `:5000` is occupied by `ControlCenter` (macOS AirPlay).

---

## Backend Deep Investigation (FastAPI / Uvicorn)

1. Launch command:
   ```bash
   cd apps/backend
   source venv/bin/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. Runtime log (`logs/backend-dev.log`):
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   INFO:     Application startup complete.
   ```
3. Health probes:
   ```bash
   curl -s http://127.0.0.1:8000/health
   # → {"status":"healthy","version":"0.1.0","services":{"neo4j":"pending","milvus":"pending","redis":"pending"}}
   ```
4. Root cause noted: previous failures stemmed from missing Node/npm and from not actually starting the backend. No code errors surfaced; service responds 200.
5. After verification, backend processes were stopped (`kill <PID>`), leaving the port free for the next run.

---

## Frontend Deep Investigation (Next.js 15)

1. Launch command with macOS watcher mitigation:
   ```bash
   cd apps/frontend
   WATCHPACK_POLLING=true npm run dev
   ```
2. Runtime log (`logs/frontend-dev.log`):
   ```
   ▲ Next.js 15.5.9
   ✓ Starting...
   ✓ Ready in ~1.3s
   ```
3. Smoke test:
   ```bash
   curl -I http://127.0.0.1:3000
   # → HTTP/1.1 200 OK
   ```
4. Identified issue: running without `WATCHPACK_POLLING=true` on Sonoma triggers `EMFILE` watcher errors. With polling enabled, service stays healthy. Processes were terminated after validation.

---

## Key Findings

- **Backend:** Starts cleanly; health endpoint reachable. No Python stack traces present. Ensure the app is actually launched (outside Docker) using the venv command above.
- **Frontend:** Requires polling-based watcher to run reliably on macOS. Without the flag, Next.js emits `EMFILE` and appears hung.
- **Port 5000 Conflict:** macOS ControlCenter listens on :5000. Change service configs or disable AirPlay if a component requires this port.

---

## How to Run Both Services

1. **Backend:**
   ```bash
   cd apps/backend
   source venv/bin/activate
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Frontend (new terminal):**
   ```bash
   cd apps/frontend
   WATCHPACK_POLLING=true npm run dev
   ```
3. Visit http://localhost:3000 and http://localhost:8000/docs.

---

## Troubleshooting Checklist

- If `node`/`npm` are missing, run `brew install node` and re-open terminal or source Homebrew shellenv.
- If frontend throws `EMFILE`, ensure `WATCHPACK_POLLING=true` (or set `CHOKIDAR_USEPOLLING=1`).
- If backend reports 404/connection issues, confirm it is started in the venv and that `curl http://127.0.0.1:8000/health` returns 200.
- For Docker-based infra, use `podman compose -f infrastructure/nerdctl/compose.yaml up -d` only when databases are required; backend/frontend still run locally.

✅ Backend and frontend both validated as operational with the commands above.
