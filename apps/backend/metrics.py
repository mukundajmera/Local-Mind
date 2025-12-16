"""
Sovereign Cognitive Engine - Prometheus Metrics
================================================
Centralized metrics definitions for observability.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# =============================================================================
# Application Info
# =============================================================================

app_info = Info("local_mind_app", "Application information")
app_info.info({
    "version": "0.1.0",
    "service": "backend",
})

# =============================================================================
# Request Metrics
# =============================================================================

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# =============================================================================
# Ingestion Metrics
# =============================================================================

ingestion_attempts_total = Counter(
    "ingestion_attempts_total",
    "Total document ingestion attempts",
    labelnames=["file_type"]
)

ingestion_failures_total = Counter(
    "ingestion_failures_total",
    "Total document ingestion failures",
    labelnames=["file_type", "stage"]
)

ingestion_duration_seconds = Histogram(
    "ingestion_duration_seconds",
    "Document ingestion duration in seconds",
    labelnames=["file_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

chunks_created_total = Counter(
    "chunks_created_total",
    "Total text chunks created",
    labelnames=["file_type"]
)

# =============================================================================
# LLM Metrics
# =============================================================================

llm_extraction_attempts_total = Counter(
    "llm_extraction_attempts_total",
    "Total LLM entity extraction attempts"
)

llm_extraction_failures_total = Counter(
    "llm_extraction_failures_total",
    "Total LLM entity extraction failures"
)

llm_extraction_duration_seconds = Histogram(
    "llm_extraction_duration_seconds",
    "LLM entity extraction duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

entities_extracted_total = Counter(
    "entities_extracted_total",
    "Total entities extracted by LLM"
)

relationships_extracted_total = Counter(
    "relationships_extracted_total",
    "Total relationships extracted by LLM"
)

# =============================================================================
# Search/Retrieval Metrics
# =============================================================================

search_requests_total = Counter(
    "search_requests_total",
    "Total search/retrieval requests",
    labelnames=["search_type"]
)

search_duration_seconds = Histogram(
    "search_duration_seconds",
    "Search duration in seconds",
    labelnames=["search_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0)
)

# =============================================================================
# Database Metrics
# =============================================================================

milvus_connection_errors_total = Counter(
    "milvus_connection_errors_total",
    "Total Milvus connection errors"
)

milvus_operation_duration_seconds = Histogram(
    "milvus_operation_duration_seconds",
    "Milvus operation duration in seconds",
    labelnames=["operation"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
)

milvus_operation_duration_seconds = Histogram(
    "milvus_operation_duration_seconds",
    "Milvus operation duration in seconds",
    labelnames=["operation"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
)

# Gauges for current state
milvus_is_healthy = Gauge(
    "milvus_is_healthy",
    "Milvus health status (1=healthy, 0=unhealthy)"
)

redis_is_healthy = Gauge(
    "redis_is_healthy",
    "Redis health status (1=healthy, 0=unhealthy)"
)
