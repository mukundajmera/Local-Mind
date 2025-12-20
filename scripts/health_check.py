#!/usr/bin/env python3
"""
Ironclad Health Check Script
==============================
Comprehensive infrastructure health verification.

Checks:
1. FastAPI Backend (/health endpoint)
2. SQLite/Database connectivity
3. Milvus Vector DB connectivity

Output:
    - "GREEN" if ALL services respond < 200ms
    - "YELLOW" if all respond but some > 200ms
    - "RED" if any service fails
"""

import sys
import time
import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
SQLITE_PATH = os.getenv("SQLITE_PATH", "data/notes.db")

# Threshold for "fast" response (ms)
FAST_THRESHOLD_MS = 200


@dataclass
class HealthResult:
    """Result of a health check."""
    service: str
    healthy: bool
    latency_ms: float
    error: Optional[str] = None


def check_fastapi() -> HealthResult:
    """Check FastAPI backend health endpoint."""
    import urllib.request
    import urllib.error
    
    start = time.perf_counter()
    try:
        req = urllib.request.Request(f"{API_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                latency = (time.perf_counter() - start) * 1000
                return HealthResult("FastAPI", True, latency)
            else:
                latency = (time.perf_counter() - start) * 1000
                return HealthResult("FastAPI", False, latency, f"HTTP {resp.status}")
    except urllib.error.URLError as e:
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("FastAPI", False, latency, str(e))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("FastAPI", False, latency, str(e))


def check_sqlite() -> HealthResult:
    """Check SQLite database connectivity."""
    start = time.perf_counter()
    try:
        db_path = Path(SQLITE_PATH)
        
        # If DB doesn't exist, that's OK for new setups
        if not db_path.exists():
            latency = (time.perf_counter() - start) * 1000
            return HealthResult("SQLite", True, latency, "DB not created yet (OK)")
        
        conn = sqlite3.connect(str(db_path), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        
        latency = (time.perf_counter() - start) * 1000
        
        if result and result[0] == 1:
            return HealthResult("SQLite", True, latency)
        else:
            return HealthResult("SQLite", False, latency, "Unexpected query result")
    
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("SQLite", False, latency, str(e))


def check_milvus() -> HealthResult:
    """Check Milvus Vector DB connectivity."""
    start = time.perf_counter()
    try:
        from pymilvus import MilvusClient, MilvusException
        
        uri = f"http://{MILVUS_HOST}:{MILVUS_PORT}"
        client = MilvusClient(uri=uri)
        
        # Simple operation to verify connection
        collections = client.list_collections()
        client.close()
        
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("Milvus", True, latency)
    
    except ImportError:
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("Milvus", False, latency, "pymilvus not installed")
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return HealthResult("Milvus", False, latency, str(e))


def format_result(result: HealthResult) -> str:
    """Format a health result for display."""
    status = "✓" if result.healthy else "✗"
    color = "\033[92m" if result.healthy else "\033[91m"
    reset = "\033[0m"
    
    latency_str = f"{result.latency_ms:.1f}ms"
    if result.latency_ms > FAST_THRESHOLD_MS:
        latency_str = f"\033[93m{latency_str}\033[0m"  # Yellow for slow
    
    line = f"  {color}{status}{reset} {result.service}: {latency_str}"
    if result.error:
        line += f" ({result.error})"
    
    return line


def main():
    """Run all health checks and report status."""
    print("\n" + "=" * 50)
    print("  IRONCLAD HEALTH CHECK")
    print("=" * 50 + "\n")
    
    results = []
    
    # Check all services
    print("Checking services...\n")
    
    results.append(check_fastapi())
    results.append(check_sqlite())
    results.append(check_milvus())
    
    # Display results
    for result in results:
        print(format_result(result))
    
    print()
    
    # Determine overall status
    all_healthy = all(r.healthy for r in results)
    all_fast = all(r.latency_ms < FAST_THRESHOLD_MS for r in results)
    
    if all_healthy and all_fast:
        print("\033[92m" + "=" * 50)
        print("  STATUS: GREEN")
        print("  All services healthy and responding < 200ms")
        print("=" * 50 + "\033[0m\n")
        return 0
    
    elif all_healthy:
        print("\033[93m" + "=" * 50)
        print("  STATUS: YELLOW")
        print("  All services healthy but some > 200ms")
        print("=" * 50 + "\033[0m\n")
        return 0
    
    else:
        failed = [r.service for r in results if not r.healthy]
        print("\033[91m" + "=" * 50)
        print("  STATUS: RED")
        print(f"  Failed services: {', '.join(failed)}")
        print("=" * 50 + "\033[0m\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
