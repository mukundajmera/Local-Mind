# Voice Service Handbook

> This microservice is part of Local Mind. Review `../../AGENTS.md` for global policies, deployment expectations, and cross-service coordination.

## Purpose & Interfaces
- **Role:** FastAPI wrapper around Kokoro TTS models delivering streaming audio for podcast-style summaries.
- **Consumers:** Backend orchestrator (`apps/backend`) calls this service over HTTP/WebSocket. Outputs WAV/PCM audio chunks consumed by the frontend.
- **Ports:** Defaults to `:8001`; update compose files and root documentation when modifying exposure.

## Environment Requirements
- Python 3.11 with CUDA 12.1-capable GPU (NVIDIA) for production performance. CPU fallback is supported but significantly slower.
- Model cache should reside under `/app/models` (mounted from host or container volume).

## Local Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Start the API:
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001
```

Environment variables consumed by this service must be added to repo `.env.example` and documented in README/handbook.

## Testing & Validation
- Unit tests (if present) should live alongside this module or under `tests/voice-service`. Currently tests reside at repo root (`tests/`); run `./run_tests.sh --unit` to include voice-service coverage.
- For manual verification:
  ```bash
  curl -X POST http://localhost:8001/synthesize -H 'Content-Type: application/json' \
    -d '{"text": "Hello Local Mind"}' --output sample.wav
  ```
- GPU utilization can be monitored with `nvidia-smi`. Ensure memory footprints align with README VRAM guidance.

## Integration Expectations
- Coordinate protocol changes with backend orchestrator maintainers. Update client calls in `apps/backend/services/` when modifying endpoints or payload structures.
- Update compose stack (`infrastructure/nerdctl/compose.yaml`) and root handbook if enabling this service in containers.
- Document any new model assets or licensing requirements.

## Git Practices
- Managed within main repo (not a separate submodule). Standard branching, Conventional Commits, and lint/test evidence apply.
- Keep `requirements.txt` minimal; note large dependency updates in PR summaries.
- Do not commit large model files; ensure downloads occur during runtime initialization or via volume mounts.

## Escalation
- GPU driver or CUDA issues: coordinate with infra/SRE contacts listed in `../../REPAIR_LOG.md`. Provide driver version and GPU model.
- Performance regressions: capture audio latency metrics and file issues referencing backend expectations.
- API compatibility: future-breaking changes must include version bump coordination and integration tests.

Maintain this handbook as the single source of truth for voice-service workflows.
