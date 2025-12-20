# Troubleshooting Guide

**Common issues and solutions for Local Mind**

---

## Quick Diagnosis

**Symptom-based index:**
- [Services won't start](#services-wont-start)
- [Upload fails or hangs](#upload-fails-or-hangs)
- [Chat doesn't respond](#chat-doesnt-respond)
- [Documents not appearing](#documents-not-appearing)
- [Slow performance](#slow-performance)
- [Backend returns 503](#backend-returns-503)

---

## Services Won't Start

**Symptom**: `./start.sh` fails or services don't start

**Diagnostic Commands:**
```bash
# Check if ports are in use
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :19530 # Milvus

# Check Docker/Nerdctl
docker ps
# or
nerdctl ps

# Check Python version
python3 --version  # Must be 3.11+

# Check Node version
node --version  # Must be 20+
```

**Solutions:**

1. **Ports already in use**:
   ```bash
   # Kill process on port
   kill $(lsof -t -i:8000)
   
   # Or change port in .env
   BACKEND_PORT=8001
   ```

2. **Docker not running**:
   - Start Docker Desktop (Mac/Windows)
   - Start nerdctl daemon (Linux)

3. **Python version too old**:
   ```bash
   # Install Python 3.11+
   brew install python@3.11  # Mac
   sudo apt install python3.11  # Ubuntu
   ```

4. **Manual restart**:
   ```bash
   ./start.sh stop
   ./start.sh all
   ```

---

## Upload Fails or Hangs

**Symptom**: Upload progress bar stuck or returns error

**Diagnostic Commands:**
```bash
# Check backend logs
tail -f apps/backend/logs/app.log

# Check Milvus
docker logs sce-memory-bank --tail 50

# Check disk space
df -h
```

**Solutions:**

1. **Large file timeout**:
   - Files >100MB may take 30+ seconds
   - Wait longer or split file

2. **Unsupported format**:
   - Only PDF, MD, TXT supported
   - Convert other formats first

3. **Backend not running**:
   ```bash
   curl http://localhost:8000/health
   # Should return {"status": "healthy"}
   ```

4. **Milvus connection error**:
   ```bash
   # Restart Milvus
   cd infrastructure/nerdctl
   nerdctl compose restart milvus
   ```

---

## Chat Doesn't Respond

**Symptom**: Chat input doesn't send or returns error

**Diagnostic Commands:**
```bash
# Check LLM service
ollama list
ollama run llama3.2:3b "test"

# Check backend logs
grep -i "llm" apps/backend/logs/app.log

# Check browser console
# Press F12, look for errors
```

**Solutions:**

1. **No sources selected**:
   - Check at least one source checkbox
   - Verify in Sources sidebar

2. **LLM not running**:
   ```bash
   # Start Ollama
   ollama serve
   
   # Pull model
   ollama pull llama3.2:3b
   ```

3. **Backend error**:
   ```bash
   # Restart backend
   ./start.sh stop backend
   ./start.sh backend
   ```

4. **Network error**:
   - Check `API_BASE_URL` in `apps/frontend/lib/api.ts`
   - Should be `http://localhost:8000`

---

## Documents Not Appearing

**Symptom**: Uploaded document doesn't show in sidebar

**Solutions:**

1. **Refresh page**: Press F5 or Cmd+R

2. **Wrong project**: Switch to correct project in dropdown

3. **Upload failed silently**:
   ```bash
   # Check upload status
   curl http://localhost:8000/api/v1/upload/{task_id}/status
   ```

4. **Frontend state issue**:
   - Clear browser cache
   - Hard refresh: Ctrl+Shift+R

---

## Slow Performance

**Symptom**: Chat responses take >10 seconds

**Solutions:**

1. **Too many sources selected**:
   - Select only 2-3 documents
   - Deselect unnecessary sources

2. **Large LLM model**:
   ```bash
   # Switch to smaller model in .env
   LLM_MODEL=llama3.2:3b  # Instead of 8b
   ```

3. **System resources**:
   ```bash
   # Check RAM usage
   free -h  # Linux
   # Activity Monitor (Mac)
   
   # Check CPU
   top
   ```

4. **Restart services**:
   ```bash
   ./start.sh stop
   ./start.sh all
   ```

---

## Backend Returns 503

**Symptom**: Health check shows "degraded" or "milvus": "unhealthy"

**Solutions:**

1. **Check Milvus**:
   ```bash
   docker ps | grep milvus
   # Should show running container
   ```

2. **Restart Milvus**:
   ```bash
   cd infrastructure/nerdctl
   nerdctl compose restart milvus etcd minio
   ```

3. **Check logs**:
   ```bash
   docker logs sce-memory-bank --tail 100
   docker logs sce-etcd --tail 100
   ```

4. **Reset Milvus data** (⚠️ deletes all documents):
   ```bash
   ./start.sh stop
   rm -rf data/milvus/*
   ./start.sh all
   ```

---

## FAQ

**Q: How do I reset everything?**
```bash
./start.sh stop
rm -rf data/
rm -rf venv/
./setup_env.sh
./start.sh all
```

**Q: Where are my documents stored?**
- Files: `data/uploads/`
- Vectors: `data/milvus/`
- Logs: `apps/backend/logs/`

**Q: How do I change the LLM model?**
Edit `.env`:
```bash
LLM_MODEL=llama3.2:8b
```
Then restart: `./start.sh stop && ./start.sh all`

**Q: Can I use a different embedding model?**
Edit `apps/backend/config.py`:
```python
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
```

**Q: How do I enable debug logging?**
Edit `.env`:
```bash
LOG_LEVEL=DEBUG
```

---

**Still stuck?** [Open an issue](https://github.com/your-org/local-mind/issues) with:
- Error message
- Relevant logs
- Steps to reproduce
