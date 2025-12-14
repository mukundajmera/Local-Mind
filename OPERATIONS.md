# Local Mind Operations Runbook

## Table of Contents
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Incident Response](#incident-response)
- [Troubleshooting](#troubleshooting)
- [Scaling](#scaling)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)

---

## Deployment

### Pre-Deployment Checklist

1. **Configuration Validation**
   ```bash
   # Verify all required environment variables are set
   python3 -c "from apps.backend.config import get_settings; get_settings()"
   ```

2. **Secret Management**
   - ✅ NEO4J_PASSWORD changed from default
   - ✅ MINIO_SECRET_KEY changed from default  
   - ✅ SECRET_KEY generated with `openssl rand -hex 32`
   - ✅ Secrets stored securely (not in git)

3. **Resource Requirements**
   - Neo4j: 2GB RAM minimum
   - Milvus + etcd + MinIO: 4GB RAM minimum
   - Backend: 2GB RAM minimum
   - GPU: 8GB VRAM for LLM (optional, can use CPU)

4. **Database Initialization**
   ```bash
   # Start infrastructure
   cd infrastructure/nerdctl
   nerdctl --namespace sovereign-ai compose up -d
   
   # Wait for health checks
   nerdctl --namespace sovereign-ai compose ps
   ```

5. **Backend Deployment**
   ```bash
   cd apps/backend
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

### Rolling Deployment Strategy

For zero-downtime deployments:

1. Deploy new version to staging
2. Run smoke tests
3. Deploy to 10% of production traffic (canary)
4. Monitor metrics for 10 minutes
5. Gradually increase to 50%, then 100%
6. Keep previous version running for quick rollback

### Rollback Procedure

If issues are detected:

```bash
# 1. Switch traffic back to old version (load balancer)
# 2. Stop new version
nerdctl --namespace sovereign-ai compose down backend

# 3. Restart old version
nerdctl --namespace sovereign-ai compose up -d backend-v-old

# 4. Verify health
curl http://localhost:8000/health
```

---

## Monitoring

### Key Metrics

#### Application Metrics (Prometheus)
- **Endpoint**: `http://localhost:8000/metrics`

**Critical Metrics:**
- `http_requests_total` - Request volume by endpoint/status
- `http_request_duration_seconds` - Latency percentiles
- `ingestion_duration_seconds` - Document processing time
- `neo4j_is_healthy` - Database connectivity (0/1)
- `milvus_is_healthy` - Vector store connectivity (0/1)

**Performance Metrics:**
- `llm_extraction_duration_seconds` - LLM response time
- `search_duration_seconds` - Retrieval latency
- `chunks_created_total` - Ingestion throughput

#### Health Checks

```bash
# Overall health
curl http://localhost:8000/health

# Expected response (healthy):
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "neo4j": "healthy",
    "milvus": "healthy",
    "redis": "healthy"
  }
}
```

#### Log Aggregation

Logs are structured JSON in production:

```bash
# View backend logs
docker logs sce-backend --tail 100 -f

# Filter for errors
docker logs sce-backend 2>&1 | jq 'select(.level=="error")'

# Search by request ID
docker logs sce-backend 2>&1 | jq 'select(.request_id=="<uuid>")'
```

### Alert Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Error rate | >1% | >5% | Investigate logs, check DB connectivity |
| P95 latency | >2s | >5s | Check LLM service, database queries |
| Ingestion failures | >5% | >20% | Verify document format, LLM availability |
| Neo4j unhealthy | - | >30s | Restart Neo4j, check disk space |
| Milvus unhealthy | - | >30s | Restart Milvus stack, check etcd/MinIO |
| CPU usage | >80% | >95% | Scale horizontally, optimize queries |
| Memory usage | >85% | >95% | Check for leaks, restart if needed |

---

## Incident Response

### Severity Levels

- **P0 (Critical)**: Complete outage, all requests failing
- **P1 (High)**: Major functionality broken, >10% error rate
- **P2 (Medium)**: Degraded performance, <10% errors
- **P3 (Low)**: Minor issues, workarounds available

### Runbook: Backend Down

**Symptoms:** `/health` returns 503 or no response

**Steps:**
1. Check container status
   ```bash
   nerdctl --namespace sovereign-ai compose ps
   ```

2. Check logs for errors
   ```bash
   docker logs sce-backend --tail 50
   ```

3. Restart backend
   ```bash
   nerdctl --namespace sovereign-ai compose restart backend
   ```

4. If restart fails, check database connectivity
   ```bash
   # Neo4j
   curl http://localhost:7474
   
   # Milvus
   curl http://localhost:19530/healthz
   ```

### Runbook: Ingestion Failures

**Symptoms:** `/api/v1/sources/upload` returns 500

**Steps:**
1. Check ingestion metrics
   ```bash
   curl http://localhost:8000/metrics | grep ingestion_failures
   ```

2. Review recent error logs
   ```bash
   docker logs sce-backend 2>&1 | jq 'select(.error_type=="IngestionError")'
   ```

3. Common causes:
   - **LLM unavailable**: Check Ollama/LM Studio running
   - **Neo4j connection**: Verify `bolt://localhost:7687` accessible
   - **Milvus full**: Check disk space in `data/milvus/`
   - **OOM**: Check memory usage, reduce concurrent uploads

4. Temporary workaround: Disable entity extraction
   ```bash
   # Set LLM_MODEL to "mock" to skip extraction
   export LLM_MODEL=mock
   ```

### Runbook: Search Returns Empty Results

**Symptoms:** Chat returns no context despite documents ingested

**Steps:**
1. Verify documents in Neo4j
   ```bash
   # Neo4j Browser: http://localhost:7474
   MATCH (d:Document) RETURN count(d)
   ```

2. Check Milvus vectors
   ```bash
   curl http://localhost:8000/api/v1/sources
   ```

3. Test vector search directly
   ```python
   from pymilvus import MilvusClient
   client = MilvusClient(uri="http://localhost:19530")
   print(client.list_collections())
   ```

4. If collections empty, re-ingest documents

### Runbook: High Latency

**Symptoms:** P95 latency >5s

**Steps:**
1. Identify slow component
   ```bash
   curl http://localhost:8000/metrics | grep duration_seconds
   ```

2. Check database query performance
   - Neo4j: Enable query logging in `neo4j.conf`
   - Milvus: Check index status

3. Profile LLM calls
   - Ollama: `docker logs ollama | grep "completion time"`
   - Reduce context window if needed

4. Scale horizontally
   ```bash
   # Increase backend workers
   uvicorn main:app --workers 8
   ```

---

## Troubleshooting

### Neo4j Issues

**Problem:** "Failed to connect to Neo4j"

**Solutions:**
```bash
# Check Neo4j running
docker ps | grep neo4j

# Check logs
docker logs sce-cognitive-brain

# Verify password
echo "NEO4J_PASSWORD=${NEO4J_PASSWORD}"

# Test connection
cypher-shell -a bolt://localhost:7687 -u neo4j -p "${NEO4J_PASSWORD}"
```

**Problem:** "Neo4j out of memory"

**Solutions:**
```bash
# Increase heap in compose.yaml
NEO4J_dbms_memory_heap_max__size=4G

# Clear old data (CAUTION: deletes all)
docker exec sce-cognitive-brain cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
  "MATCH (n) DETACH DELETE n"
```

### Milvus Issues

**Problem:** "Milvus connection timeout"

**Solutions:**
```bash
# Check Milvus and dependencies
docker ps | grep -E "milvus|etcd|minio"

# Check etcd health
docker logs sce-etcd

# Check MinIO
curl http://localhost:9000/minio/health/live

# Restart Milvus stack
nerdctl --namespace sovereign-ai compose restart etcd minio memory-bank
```

**Problem:** "Collection not found"

**Solutions:**
```python
# Recreate collection
from pymilvus import MilvusClient, DataType
client = MilvusClient(uri="http://localhost:19530")
client.create_collection(
    collection_name="sce_chunks",
    dimension=384,
    metric_type="COSINE"
)
```

### GPU/LLM Issues

**Problem:** "CUDA out of memory"

**Solutions:**
```bash
# Check GPU usage
nvidia-smi

# Reduce model size
export LLM_MODEL=llama3.2:8b  # Instead of 70b

# Use quantization
export QUANTIZATION=4bit

# Reduce context window
export CONTEXT_WINDOW=2048
```

---

## Scaling

### Horizontal Scaling

#### Backend API
```bash
# Run multiple instances behind load balancer
uvicorn main:app --workers 8 --host 0.0.0.0 --port 8000
```

#### Celery Workers (for async tasks)
```bash
# Start multiple workers
celery -A tasks worker --concurrency=4 --queue=ingestion
celery -A tasks worker --concurrency=2 --queue=podcast
```

### Vertical Scaling

#### Neo4j
```yaml
# compose.yaml
NEO4J_dbms_memory_heap_max__size=8G
NEO4J_dbms_memory_pagecache_size=4G
```

#### Milvus
- Increase etcd/MinIO resources
- Use distributed Milvus cluster for >1TB data

### Database Sharding

For >1M documents:
- Use separate Milvus collections per tenant
- Shard Neo4j by document date ranges

---

## Security

### Authentication

**TODO:** Add JWT-based authentication

```python
# Example implementation needed:
# 1. Add JWT middleware
# 2. Require API keys for endpoints
# 3. Implement user/tenant isolation
```

### Network Security

```bash
# Production deployment:
# 1. Use TLS for all services
# 2. Neo4j: bolt+s://
# 3. Milvus: Behind firewall
# 4. Redis: Require password
```

### Audit Logging

Enable audit logs for compliance:

```python
# Log all ingestion events
logger.info("document_ingested", doc_id=doc_id, user_id=user_id)

# Log all search queries
logger.info("search_performed", query=query, user_id=user_id)
```

### Secrets Management

**Development:**
```bash
cp .env.example .env
# Edit .env with real values
chmod 600 .env
```

**Production (recommended):**
```bash
# Use HashiCorp Vault or AWS Secrets Manager
export NEO4J_PASSWORD=$(vault kv get -field=password secret/neo4j)
export MINIO_SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id minio)
```

---

## Backup & Recovery

### Neo4j Backup

```bash
# Create backup
docker exec sce-cognitive-brain neo4j-admin database dump neo4j \
  --to-path=/backups/neo4j-$(date +%Y%m%d).dump

# Restore backup
docker exec sce-cognitive-brain neo4j-admin database load neo4j \
  --from-path=/backups/neo4j-20240101.dump --overwrite-destination=true
```

### Milvus Backup

```bash
# Backup MinIO data
tar -czf milvus-backup-$(date +%Y%m%d).tar.gz data/milvus/

# Restore
tar -xzf milvus-backup-20240101.tar.gz -C data/
```

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh - Run daily via cron

DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups/${DATE}

mkdir -p ${BACKUP_DIR}

# Neo4j
docker exec sce-cognitive-brain neo4j-admin database dump neo4j \
  --to-path=/backups/neo4j-${DATE}.dump

# Milvus
tar -czf ${BACKUP_DIR}/milvus.tar.gz data/milvus/

# Retention: Keep last 7 days
find /backups -type d -mtime +7 -exec rm -rf {} \;
```

### Disaster Recovery

**RTO (Recovery Time Objective):** 1 hour  
**RPO (Recovery Point Objective):** 24 hours (daily backups)

**Recovery Steps:**
1. Provision new infrastructure
2. Restore latest backups
3. Update DNS/load balancer
4. Verify health checks pass
5. Resume traffic

---

## SLA Commitments

### Availability Targets

- **Uptime:** 99.5% (43.8 hours downtime/year)
- **Maintenance Windows:** Saturday 2-4 AM UTC

### Performance SLOs

| Metric | Target |
|--------|--------|
| P50 latency | <500ms |
| P95 latency | <2s |
| P99 latency | <5s |
| Ingestion throughput | >10 docs/minute |
| Search accuracy | >90% relevant results |

---

## On-Call Rotation

### Responsibilities

- Monitor alerts (PagerDuty/Opsgenie)
- Respond to P0/P1 incidents within 15 minutes
- Investigate and resolve issues
- Document incidents and root causes

### Escalation Path

1. **L1 (On-call engineer)**: Initial response, basic troubleshooting
2. **L2 (Senior engineer)**: Complex debugging, code changes needed
3. **L3 (Architect/Lead)**: Design decisions, major incidents

### Contact Information

- **Slack Channel:** #local-mind-ops
- **Email:** ops@localmind.ai
- **On-Call Phone:** [Configure PagerDuty]

---

## Known Issues

| Issue | Impact | Workaround | Fix ETA |
|-------|--------|------------|---------|
| Ingestion slow for large PDFs (>100 pages) | High latency | Split into smaller files | Q1 2025 |
| Neo4j connection leak with high concurrency | Memory growth | Restart daily | Fixed in v0.2.0 |
| Milvus search slower after 1M vectors | P95 >2s | Re-index collection | Investigating |

---

## Changelog

- **2024-12-14**: Initial operations runbook created
- Future updates will track major incidents and process improvements
