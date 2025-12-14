# Security Guidelines

## Overview

This document outlines security best practices for deploying and operating Local Mind in production environments.

---

## Table of Contents

- [Pre-Deployment Security Checklist](#pre-deployment-security-checklist)
- [Secrets Management](#secrets-management)
- [Network Security](#network-security)
- [Authentication & Authorization](#authentication--authorization)
- [Data Protection](#data-protection)
- [Monitoring & Auditing](#monitoring--auditing)
- [Incident Response](#incident-response)
- [Dependency Management](#dependency-management)

---

## Pre-Deployment Security Checklist

### Configuration

- [ ] **NEO4J_PASSWORD**: Changed from default, minimum 16 characters
- [ ] **MINIO_SECRET_KEY**: Changed from default, minimum 32 characters
- [ ] **SECRET_KEY**: Generated with `openssl rand -hex 32`
- [ ] All `.env` files have restrictive permissions: `chmod 600 .env`
- [ ] No secrets committed to git (verify with `git log --all -p | grep -i password`)
- [ ] Environment variable validation enabled in `config.py`

### Network

- [ ] Services bound to localhost in development
- [ ] Production services behind firewall/VPN
- [ ] TLS/SSL enabled for all external connections
- [ ] Neo4j using `bolt+s://` (TLS) in production
- [ ] API gateway/reverse proxy configured (nginx/Caddy)
- [ ] CORS origins explicitly configured (not `*`)

### Access Control

- [ ] Neo4j: Non-default username, strong password
- [ ] Milvus: Network-level access control (no public exposure)
- [ ] Redis: Password authentication enabled
- [ ] OS-level user isolation (run as non-root)
- [ ] Container capabilities dropped (no `--privileged`)

### Monitoring

- [ ] Audit logging enabled for sensitive operations
- [ ] Prometheus metrics secured (not publicly accessible)
- [ ] Log aggregation configured
- [ ] Alerting for suspicious activity
- [ ] Rate limiting enabled

---

## Secrets Management

### Development

**Option 1: Local .env file (not recommended for production)**

```bash
# Copy template
cp .env.example .env

# Set restrictive permissions
chmod 600 .env

# Edit with secure values
vim .env
```

**Security Notes:**
- Never commit `.env` to version control
- Use different secrets for each environment
- Rotate secrets regularly (quarterly minimum)

### Production (Recommended)

**Option 1: HashiCorp Vault**

```bash
# Store secrets in Vault
vault kv put secret/localmind \
  neo4j_password=$(openssl rand -base64 32) \
  minio_secret_key=$(openssl rand -base64 32) \
  secret_key=$(openssl rand -hex 32)

# Retrieve at runtime
export NEO4J_PASSWORD=$(vault kv get -field=neo4j_password secret/localmind)
export MINIO_SECRET_KEY=$(vault kv get -field=minio_secret_key secret/localmind)
export SECRET_KEY=$(vault kv get -field=secret_key secret/localmind)
```

**Option 2: AWS Secrets Manager**

```bash
# Store secrets
aws secretsmanager create-secret \
  --name localmind/neo4j_password \
  --secret-string "$(openssl rand -base64 32)"

# Retrieve at runtime
export NEO4J_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id localmind/neo4j_password \
  --query SecretString --output text)
```

**Option 3: Kubernetes Secrets**

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: localmind-secrets
type: Opaque
stringData:
  neo4j_password: <base64-encoded>
  minio_secret_key: <base64-encoded>
  secret_key: <base64-encoded>
```

### Secret Rotation

**Frequency:**
- Development: Every 6 months
- Staging: Every 3 months
- Production: Every 90 days or on suspected compromise

**Rotation Procedure:**

1. Generate new secret: `openssl rand -base64 32`
2. Update secret in management system (Vault/AWS/etc.)
3. Restart services with zero-downtime strategy
4. Verify old secret no longer works
5. Document rotation in changelog

---

## Network Security

### Firewall Rules

**Minimal Production Ruleset:**

```bash
# Only allow necessary ports
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT  # Backend API
iptables -A INPUT -p tcp --dport 3000 -j ACCEPT  # Frontend (if public)

# Block direct database access
iptables -A INPUT -p tcp --dport 7687 -j DROP   # Neo4j
iptables -A INPUT -p tcp --dport 19530 -j DROP  # Milvus
iptables -A INPUT -p tcp --dport 6379 -j DROP   # Redis

# Allow internal network only
iptables -A INPUT -s 10.0.0.0/8 -j ACCEPT
```

### TLS/SSL Configuration

**Neo4j with TLS:**

```yaml
# neo4j.conf
server.bolt.tls_level=REQUIRED
server.https.enabled=true
server.directories.certificates=/path/to/certs

# Generate self-signed cert (dev only)
openssl req -x509 -newkey rsa:4096 \
  -keyout neo4j-key.pem -out neo4j-cert.pem \
  -days 365 -nodes
```

**Backend API with TLS (using Caddy):**

```
# Caddyfile
localmind.example.com {
  reverse_proxy localhost:8000
  tls {
    protocols tls1.2 tls1.3
  }
}
```

### VPN/Bastion Access

For production databases:

```bash
# SSH tunnel to Neo4j
ssh -L 7687:localhost:7687 user@bastion-host

# Connect through tunnel
export NEO4J_URI=bolt://localhost:7687
```

---

## Authentication & Authorization

### Current State

⚠️ **WARNING**: Authentication is NOT currently implemented. All endpoints are publicly accessible.

### Recommended Implementation (TODO)

**1. API Key Authentication**

```python
# middleware/auth.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key not in get_valid_api_keys():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return api_key

# Apply to endpoints
@app.post("/api/v1/sources/upload")
async def upload(api_key: str = Depends(verify_api_key)):
    ...
```

**2. JWT Token Authentication**

```python
# middleware/jwt_auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import jwt, JWTError

security = HTTPBearer()

async def verify_token(credentials = Security(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().secret_key,
            algorithms=["HS256"]
        )
        return payload["sub"]  # user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**3. OAuth2 Integration**

For enterprise deployments, integrate with existing identity providers (Okta, Auth0, Azure AD).

---

## Data Protection

### Data at Rest

**Neo4j Encryption:**

```yaml
# neo4j.conf
dbms.directories.data.encryption=true
dbms.security.keystore.path=/path/to/keystore
```

**Milvus/MinIO Encryption:**

```yaml
# MinIO with server-side encryption
MINIO_SSE_AUTO_ENCRYPTION=on
```

**OS-Level Encryption:**

```bash
# LUKS full disk encryption
cryptsetup luksFormat /dev/sdb
cryptsetup open /dev/sdb encrypted-volume
mkfs.ext4 /dev/mapper/encrypted-volume
```

### Data in Transit

- All HTTP traffic over TLS (443)
- Database connections over TLS
- Internal service mesh with mTLS (optional)

### Data Sanitization

**Log Sanitization (already implemented):**

```python
# logging_config.py sanitizes:
- Passwords
- API keys
- Tokens
- Long text chunks (>1000 chars)
```

**PII Handling:**

- Do not log personal information
- Redact sensitive fields before storage
- Implement data retention policies
- Support GDPR right-to-erasure

```python
# Example: Anonymize user data
async def anonymize_user(user_id: str):
    # Delete from Neo4j
    await session.run(
        "MATCH (u:User {id: $user_id}) DETACH DELETE u",
        user_id=user_id
    )
    # Delete from Milvus
    milvus_client.delete(f"user_id == '{user_id}'")
```

---

## Monitoring & Auditing

### Audit Logging

**Enable audit logs for:**

- User authentication attempts
- Document uploads (who, what, when)
- Search queries (with user context)
- Configuration changes
- Administrative actions

**Implementation:**

```python
# audit.py
import structlog

audit_logger = structlog.get_logger("audit")

async def log_upload(user_id: str, filename: str, doc_id: str):
    audit_logger.info(
        "document_uploaded",
        user_id=user_id,
        filename=filename,
        doc_id=doc_id,
        timestamp=datetime.utcnow().isoformat(),
    )
```

### Security Metrics

**Prometheus metrics to track:**

```python
# metrics.py
failed_auth_attempts = Counter(
    "auth_failures_total",
    "Failed authentication attempts",
    labelnames=["ip_address"]
)

suspicious_queries = Counter(
    "suspicious_queries_total",
    "Queries flagged by anomaly detection"
)
```

### Alerting

**Critical alerts:**

- 5+ failed auth attempts from single IP in 1 minute
- Unusual data access patterns (SQL injection attempts)
- High rate of 500 errors
- Database connection failures
- Disk space <10%

**Alert destinations:**

- PagerDuty for P0/P1 incidents
- Slack for warnings
- Email for daily summaries

---

## Incident Response

### Security Incident Playbook

**1. Detection**

- Automated alert triggers
- User report
- Security audit finding

**2. Containment**

```bash
# Immediate actions:
# 1. Isolate affected system
iptables -A INPUT -j DROP  # Block all incoming

# 2. Preserve evidence
tar -czf evidence-$(date +%Y%m%d-%H%M%S).tar.gz /var/log/

# 3. Change compromised credentials
./scripts/rotate_secrets.sh --emergency
```

**3. Investigation**

- Review audit logs
- Analyze network traffic
- Check for unauthorized access
- Identify attack vector

**4. Eradication**

- Patch vulnerabilities
- Remove backdoors
- Update WAF rules

**5. Recovery**

- Restore from clean backup if needed
- Verify system integrity
- Gradually restore service

**6. Post-Incident**

- Document timeline
- Root cause analysis
- Update runbooks
- Implement preventive measures

### Breach Notification

If user data is compromised:

1. Assess scope and severity
2. Notify affected users within 72 hours (GDPR requirement)
3. Report to authorities if required
4. Document incident for compliance

---

## Dependency Management

### Vulnerability Scanning

**Scan Python dependencies:**

```bash
# Install safety
pip install safety

# Scan for known vulnerabilities
safety check --json
```

**Scan Docker images:**

```bash
# Install Trivy
trivy image milvusdb/milvus:v2.4.13
trivy image neo4j:5.26.0-community
```

### Dependency Updates

**Update strategy:**

- Security patches: Apply immediately after testing
- Minor updates: Monthly review
- Major updates: Quarterly evaluation

**Pinned versions in requirements.txt:**

```txt
# Good: Pinned to specific version
fastapi==0.115.5

# Bad: Unpinned (security risk)
# fastapi
```

### Supply Chain Security

- Verify package signatures
- Use private PyPI mirror for vetted packages
- Implement Software Bill of Materials (SBOM)
- Monitor for compromised dependencies

---

## Compliance

### Frameworks

Local Mind should align with:

- **SOC 2 Type II**: Security, availability, confidentiality
- **ISO 27001**: Information security management
- **GDPR**: Data protection and privacy (EU)
- **HIPAA**: Healthcare data (if applicable)

### Required Controls

1. Access control and authentication ✅ (Partially - TODO: complete)
2. Encryption at rest and in transit ✅ (Documented)
3. Audit logging ✅ (Implemented)
4. Vulnerability management ✅ (Process documented)
5. Incident response plan ✅ (Runbook created)
6. Data retention and deletion 🔄 (Needs implementation)
7. Regular security testing 🔄 (Needs scheduling)

---

## Security Contact

To report a security vulnerability:

- **Email**: security@localmind.ai (TODO: set up)
- **PGP Key**: [Link to public key] (TODO: create)
- **Response SLA**: 24 hours for critical issues

### Responsible Disclosure

Please do NOT:
- Exploit vulnerabilities beyond proof-of-concept
- Access user data
- Perform DoS attacks

We commit to:
- Acknowledge report within 24 hours
- Provide estimated fix timeline
- Credit researchers (if desired)
- Fix critical issues within 7 days

---

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [12-Factor App Security](https://12factor.net/)

---

## Changelog

- **2024-12-14**: Initial security guidelines created
- Future updates will track security improvements and incident learnings
