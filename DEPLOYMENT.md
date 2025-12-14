# Production Deployment Guide

This guide covers deploying Local Mind in production environments with high availability, security, and performance.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Patterns](#architecture-patterns)
- [Infrastructure Provisioning](#infrastructure-provisioning)
- [CI/CD Pipeline](#cicd-pipeline)
- [Configuration Management](#configuration-management)
- [Database Setup](#database-setup)
- [Application Deployment](#application-deployment)
- [Monitoring Setup](#monitoring-setup)
- [Scaling Strategies](#scaling-strategies)
- [Rollback Procedures](#rollback-procedures)

---

## Prerequisites

### Resource Requirements

**Minimum (Small Deployment - <1K documents, <10 users):**
- CPU: 8 cores
- RAM: 16GB
- Storage: 100GB SSD
- GPU: Optional (8GB VRAM for local LLM)

**Recommended (Production - <100K documents, <100 users):**
- CPU: 16 cores
- RAM: 64GB
- Storage: 500GB SSD (1TB for long-term growth)
- GPU: 16GB VRAM for LLM (or use external API)

**Large Scale (>100K documents, >1000 users):**
- Multi-node cluster
- Separate database servers
- Load balancer
- CDN for frontend

### Software Requirements

- **Container Runtime**: Docker 24+ or nerdctl 1.7+
- **OS**: Ubuntu 22.04 LTS (recommended) or RHEL 9
- **Python**: 3.11+
- **Node.js**: 20 LTS (for frontend)
- **Optional**: Kubernetes 1.28+ for orchestration

---

## Architecture Patterns

### Single-Server Deployment

**Best for:** Development, small teams, proof-of-concept

```
┌─────────────────────────────────────┐
│         Single Server               │
│                                     │
│  ┌──────────┐  ┌─────────────┐    │
│  │ Backend  │  │  Frontend   │    │
│  │ (8000)   │  │  (3000)     │    │
│  └──────────┘  └─────────────┘    │
│                                     │
│  ┌──────────┐  ┌─────────────┐    │
│  │  Neo4j   │  │   Milvus    │    │
│  │  (7687)  │  │   (19530)   │    │
│  └──────────┘  └─────────────┘    │
│                                     │
│  ┌──────────┐                      │
│  │  Redis   │                      │
│  │  (6379)  │                      │
│  └──────────┘                      │
└─────────────────────────────────────┘
```

**Deployment:**

```bash
# Start all services
cd infrastructure/nerdctl
nerdctl --namespace sovereign-ai compose up -d

# Start backend
cd apps/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Multi-Server Deployment

**Best for:** Production, high availability, scalability

```
┌─────────────────┐
│  Load Balancer  │  (nginx/HAProxy)
│   (443)         │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐
│ API-1 │ │ API-2 │  (Backend replicas)
└───┬───┘ └──┬────┘
    │         │
    └────┬────┘
         │
    ┌────▼─────────────┐
    │  Database Tier   │
    │                  │
    │  ┌──────────┐   │
    │  │  Neo4j   │   │  (Primary/Replica)
    │  │  Cluster │   │
    │  └──────────┘   │
    │                  │
    │  ┌──────────┐   │
    │  │  Milvus  │   │  (Distributed)
    │  │  Cluster │   │
    │  └──────────┘   │
    └──────────────────┘
```

**Deployment:**

```bash
# Deploy to multiple nodes using Ansible/Terraform
ansible-playbook -i inventory/production deploy.yml

# Or use Kubernetes
kubectl apply -f k8s/
```

---

## Infrastructure Provisioning

### AWS (using Terraform)

```hcl
# main.tf
resource "aws_instance" "backend" {
  count         = 2
  ami           = "ami-ubuntu-22.04"
  instance_type = "t3.xlarge"
  
  vpc_security_group_ids = [aws_security_group.backend.id]
  
  tags = {
    Name = "localmind-backend-${count.index}"
  }
}

resource "aws_rds_instance" "neo4j" {
  # Note: Neo4j not natively supported in RDS
  # Use EC2 or managed Neo4j Aura
}

resource "aws_efs_file_system" "data" {
  # Shared storage for documents
  creation_token = "localmind-data"
}
```

### Azure (using Bicep)

```bicep
// main.bicep
resource vm 'Microsoft.Compute/virtualMachines@2023-03-01' = {
  name: 'localmind-vm'
  location: resourceGroup().location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_D4s_v3'
    }
    // ... additional config
  }
}
```

### Google Cloud (using gcloud CLI)

```bash
# Create compute instance
gcloud compute instances create localmind-backend \
  --machine-type=n1-standard-8 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=200GB \
  --tags=http-server,https-server

# Create managed instance group for auto-scaling
gcloud compute instance-groups managed create localmind-ig \
  --base-instance-name=localmind \
  --size=2 \
  --template=localmind-template
```

---

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install -r apps/backend/requirements.txt
          pytest tests/unit -v
      
      - name: Security scan
        run: |
          pip install safety
          safety check

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker images
        run: |
          docker build -t localmind/backend:${{ github.sha }} apps/backend
          docker build -t localmind/frontend:${{ github.sha }} apps/frontend
      
      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USER }} --password-stdin
          docker push localmind/backend:${{ github.sha }}
          docker push localmind/frontend:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          # SSH into production servers
          ssh deploy@prod-server "cd /opt/localmind && docker-compose pull && docker-compose up -d"
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  script:
    - pytest tests/unit
    - safety check

build:
  stage: build
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy_production:
  stage: deploy
  script:
    - kubectl set image deployment/backend backend=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main
```

---

## Configuration Management

### Environment-Specific Configs

```bash
# configs/
├── .env.development
├── .env.staging
└── .env.production

# Deploy with correct config
CONFIG_ENV=production docker-compose up -d
```

### Secrets Management with Ansible Vault

```bash
# Encrypt secrets
ansible-vault encrypt secrets.yml

# Deploy with encrypted secrets
ansible-playbook -i inventory/production \
  --ask-vault-pass \
  deploy.yml
```

### Configuration Validation

```python
# validate_config.py
from apps.backend.config import get_settings

try:
    settings = get_settings()
    print("✅ Configuration valid")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    exit(1)
```

---

## Database Setup

### Neo4j Production Configuration

```conf
# neo4j.conf

# Memory settings (adjust based on RAM)
server.memory.heap.initial_size=4G
server.memory.heap.max_size=8G
server.memory.pagecache.size=4G

# Performance tuning
server.bolt.thread_pool_max_size=400
server.db.query.cache.size=1000

# Security
server.bolt.tls_level=REQUIRED
server.https.enabled=true

# Backup
dbms.backup.enabled=true
dbms.backup.address=0.0.0.0:6362

# Monitoring
metrics.enabled=true
metrics.prometheus.enabled=true
metrics.prometheus.endpoint=0.0.0.0:2004
```

### Milvus Production Configuration

```yaml
# milvus.yaml
etcd:
  endpoints:
    - etcd:2379

minio:
  address: minio:9000
  useSSL: true

dataNode:
  flowGraph:
    maxParallelism: 16

queryNode:
  cacheSize: 32GB

indexNode:
  scheduler:
    buildParallel: 8
```

### Backup Strategy

```bash
# backup.sh
#!/bin/bash

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups/${DATE}

# Neo4j backup
docker exec sce-cognitive-brain neo4j-admin database dump neo4j \
  --to-path=/backups/neo4j-${DATE}.dump

# Milvus backup (via MinIO)
docker exec sce-minio mc mirror data /backups/milvus-${DATE}

# Upload to S3
aws s3 sync /backups/${DATE} s3://localmind-backups/${DATE}

# Clean old backups (keep 30 days)
find /backups -type d -mtime +30 -exec rm -rf {} \;
```

---

## Application Deployment

### Docker Compose (Production)

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  backend:
    image: localmind/backend:latest
    restart: always
    environment:
      - ENVIRONMENT=production
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Kubernetes Deployment

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: localmind/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: NEO4J_PASSWORD
          valueFrom:
            secretKeyRef:
              name: localmind-secrets
              key: neo4j_password
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'localmind-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics

  - job_name: 'neo4j'
    static_configs:
      - targets: ['neo4j:2004']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
```

### Grafana Dashboards

```bash
# Import pre-built dashboards
# 1. FastAPI metrics (Dashboard ID: 14710)
# 2. Neo4j metrics (Dashboard ID: 12563)
# 3. System metrics (Dashboard ID: 1860)
```

### Alert Rules

```yaml
# alerts.yml
groups:
  - name: localmind_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: DatabaseDown
        expr: neo4j_is_healthy == 0
        for: 1m
        annotations:
          summary: "Neo4j is unhealthy"
```

---

## Scaling Strategies

### Horizontal Scaling (Multiple Backend Instances)

```bash
# Docker Compose
docker-compose up -d --scale backend=5

# Kubernetes
kubectl scale deployment backend --replicas=5
```

### Vertical Scaling (Increase Resources)

```bash
# Increase backend memory
docker update --memory=8g backend-container

# Kubernetes
kubectl set resources deployment backend \
  --limits=memory=8Gi,cpu=4
```

### Auto-Scaling (Kubernetes HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## Rollback Procedures

### Quick Rollback (Docker)

```bash
# Tag current version as backup
docker tag localmind/backend:latest localmind/backend:rollback

# Pull previous version
docker pull localmind/backend:previous-stable

# Restart with old version
docker-compose down
docker-compose up -d
```

### Kubernetes Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/backend

# Rollback to specific revision
kubectl rollout history deployment/backend
kubectl rollout undo deployment/backend --to-revision=3

# Check rollout status
kubectl rollout status deployment/backend
```

### Database Rollback

```bash
# Restore Neo4j backup
docker exec sce-cognitive-brain neo4j-admin database load neo4j \
  --from-path=/backups/neo4j-20240101.dump \
  --overwrite-destination=true

# Restart Neo4j
docker restart sce-cognitive-brain
```

---

## Post-Deployment Checklist

- [ ] Health checks passing (`/health` returns 200)
- [ ] Metrics endpoint accessible (`/metrics`)
- [ ] Logs flowing to aggregation system
- [ ] Alerts configured and tested
- [ ] Backups running successfully
- [ ] SSL/TLS certificates valid
- [ ] Rate limiting configured
- [ ] Load balancer routing correctly
- [ ] Smoke tests passing
- [ ] Monitoring dashboard populated
- [ ] Documentation updated
- [ ] Team notified of deployment

---

## Troubleshooting Common Issues

### Issue: Backend won't start

```bash
# Check logs
docker logs sce-backend --tail 100

# Common causes:
# 1. Invalid config → check .env file
# 2. Database unreachable → ping Neo4j/Milvus
# 3. Port conflict → lsof -i :8000
```

### Issue: High memory usage

```bash
# Check container stats
docker stats

# Limit memory
docker update --memory=4g --memory-swap=4g backend

# Profile Python memory
pip install memray
memray run uvicorn main:app
```

### Issue: Slow queries

```bash
# Enable Neo4j query logging
echo "dbms.logs.query.enabled=VERBOSE" >> neo4j.conf

# Analyze slow queries
docker exec sce-cognitive-brain tail -f logs/query.log
```

---

## Resources

- [Docker Production Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes Production Checklist](https://kubernetes.io/docs/setup/best-practices/)
- [Neo4j Operations Manual](https://neo4j.com/docs/operations-manual/current/)
- [Milvus Production Deployment](https://milvus.io/docs/install_cluster-milvusoperator.md)

---

## Changelog

- **2024-12-14**: Initial deployment guide created
