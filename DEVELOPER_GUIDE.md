# Developer Guide: Fortress Quality Assurance

## 🚀 Running Tests

We prioritize automated verification. Use the following commands to validate your changes.

### 1. Backend Verification
Runs unit tests for ingestion, deletion, and security isolation.

```bash
# Activate virtual environment
source venv/bin/activate

# Run all backend tests
pytest tests/

# Run specific security tests
pytest tests/security/test_isolation.py
```

### 2. Frontend Lifecycle (E2E)
Simulates a real user using the browser (Playwright).

```bash
# Ensure frontend is running (localhost:3000)
# Ensure backend is running (localhost:8000)

# Run sanity check
npx playwright test tests/e2e/sanity.spec.ts
```

## 📐 Architecture Notes

### Multi-Tenancy (Namespaces)
- **Frontend**: `ProjectSelector` stores `currentProjectId` in Zustand.
- **API**: All requests (`/upload`, `/sources`, `/chat`) append `?project_id=...`.
- **DB**: Milvus schema includes `project_id` field. Implicit filter applied on all queries.

### Atomic Deletion ("The Trap")
- We verify deletion from the Vector DB *before* touching the disk.
- If Milvus fails (or returns the doc in a check query), the file remains on disk for manual recovery/debug.
- **Log**: Check `apps/backend/logs/app.log` for "CRITICAL: Failed to delete doc..." messages.
