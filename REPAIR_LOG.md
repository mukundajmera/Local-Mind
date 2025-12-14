# Local Mind - macOS Deep Clean & Startup Debug Log

**Date:** 2025-12-14 (Session 2)  
**Platform:** macOS (arm64 Apple Silicon)  
**Engineer:** Senior MacOS Full-Stack SRE Protocol

---

## Phase 1 · Environment Scan

| Check | Result |
|-------|--------|
| **CPU Architecture** | `arm64` (Apple Silicon M-series) |
| **Node.js** | v25.2.1 (`/opt/homebrew/bin/node`) |
| **npm** | 11.6.2 |
| **Python** | 3.12.10 (system), venv at `apps/backend/venv` |
| **Shell** | zsh (macOS default) |

### Port Conflicts
| Port | Status | Process |
|------|--------|---------|
| `:3000` | **Cleared** | Killed stale node process (PID 28295) |
| `:5000` | **Occupied** | macOS ControlCenter (AirPlay) - expected |
| `:8000` | **Free** | Ready for backend |

---

## Phase 2 · Frontend "Nuke & Pave"

### Cleanup Actions
```bash
cd apps/frontend
rm -rf node_modules package-lock.json .next
npm cache clean --force
```

### Fresh Install
```bash
npm install --platform=darwin --arch=arm64
```

**Result:**
- ✅ 196 packages installed
- ✅ 0 vulnerabilities found
- ⚠️ npm warns `--platform` and `--arch` flags deprecated in future versions

---

## Phase 3 · Backend Verification

### Python Environment Check
```bash
cd apps/backend
source venv/bin/activate
pip freeze | wc -l  # → 169 packages
```

**Key packages confirmed:** FastAPI, Uvicorn, Celery, aiohttp, sentence-transformers

---

## Phase 4 · Startup Sequence

### Backend Start
```bash
cd apps/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
**Log Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Frontend Start (with macOS watcher fix)
```bash
cd apps/frontend
WATCHPACK_POLLING=true npm run dev
```
**Log Output:**
```
▲ Next.js 15.5.9
✓ Ready in 2.1s
```

### Health Verification
| Endpoint | Response | Status |
|----------|----------|--------|
| `http://127.0.0.1:8000/health` | `{"status":"healthy","version":"0.1.0",...}` | ✅ 200 OK |
| `http://127.0.0.1:3000` | HTML page | ✅ 200 OK |

---

## Key Fixes Applied This Session

1. **Killed stale node process** on port 3000 (PID 28295)
2. **Complete frontend rebuild:**
   - Deleted `node_modules/`, `package-lock.json`, `.next/`
   - Cleared npm cache
   - Fresh install with ARM64 platform flags
3. **Verified backend venv** with 169 packages intact
4. **Started both services** with macOS-specific workarounds

---

## How to Run Both Services

### Terminal 1 - Backend
```bash
cd apps/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 - Frontend
```bash
cd apps/frontend
WATCHPACK_POLLING=true npm run dev
```

### Access Points
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## Troubleshooting Reference

| Issue | Cause | Fix |
|-------|-------|-----|
| `EMFILE` watcher errors | macOS Sonoma file watcher limits | Set `WATCHPACK_POLLING=true` |
| Port 3000 in use | Stale node process | `lsof -i :3000` then `kill -9 <PID>` |
| Port 5000 occupied | macOS AirPlay Receiver | System Settings → AirDrop → disable AirPlay Receiver |
| `node`/`npm` not found | Homebrew PATH not sourced | Run `eval "$(brew shellenv)"` |
| Python module not found | venv not activated | `source apps/backend/venv/bin/activate` |
| gyp/native module errors | Missing Xcode tools | `xcode-select --install` |

---

## Current Status

✅ **BOTH SERVICES OPERATIONAL**

- Backend: Running on port 8000 (PID active)
- Frontend: Running on port 3000 (PID active)
- Health endpoints: Verified responding

---

*Log updated: 2025-12-14 19:27 IST*
