"""
Sovereign Cognitive Engine - Chaos Monkey Test Suite
=====================================================
Stress testing for extreme conditions: large uploads, VRAM pressure, corrupted inputs.

Run with: locust -f tests/stress/chaos.py --host=http://localhost:8000
"""

import os
import io
import json
import time
import random
import subprocess
from typing import Optional

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# =============================================================================
# Configuration
# =============================================================================

# Memory limits (bytes)
CELERY_MEMORY_LIMIT_MB = 2048
VRAM_LOW_THRESHOLD_MB = 1024  # Consider system "busy" below this

# Test file sizes
LARGE_FILE_SIZE_MB = 10
MEDIUM_FILE_SIZE_MB = 5

# Endpoints
HEALTH_ENDPOINT = "/health"
INGEST_ENDPOINT = "/api/notebooks/{notebook_id}/sources"
PODCAST_ENDPOINT = "/api/notebooks/{notebook_id}/podcast"
QUERY_ENDPOINT = "/api/notebooks/{notebook_id}/chat"


# =============================================================================
# Utility Functions
# =============================================================================

def get_gpu_memory_free() -> Optional[int]:
    """
    Query NVIDIA GPU free memory using nvidia-smi.
    Returns free memory in MB, or None if unavailable.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Sum free memory across all GPUs
            free_mb = sum(int(x.strip()) for x in result.stdout.strip().split("\n") if x.strip())
            return free_mb
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def get_celery_worker_memory() -> Optional[int]:
    """
    Get Celery worker memory usage in MB.
    Uses docker/nerdctl stats if available.
    """
    try:
        result = subprocess.run(
            ["nerdctl", "stats", "--no-stream", "--format", "{{.MemUsage}}", "orchestrator"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse output like "1.5GiB / 16GiB" or "512MiB / 16GiB"
            usage_str = result.stdout.strip().split("/")[0].strip()
            if "GiB" in usage_str:
                return int(float(usage_str.replace("GiB", "").strip()) * 1024)
            elif "MiB" in usage_str:
                return int(float(usage_str.replace("MiB", "").strip()))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, IndexError):
        pass
    return None


def generate_large_text(size_mb: int) -> bytes:
    """Generate random text content of specified size."""
    # Generate realistic-looking text blocks
    words = [
        "quantum", "computing", "artificial", "intelligence", "neural",
        "network", "machine", "learning", "algorithm", "optimization",
        "distributed", "systems", "architecture", "performance", "scalability",
    ]
    
    content = []
    target_size = size_mb * 1024 * 1024
    
    while len("\n".join(content).encode()) < target_size:
        # Generate paragraph
        paragraph = " ".join(random.choices(words, k=50)) + ".\n\n"
        content.append(paragraph * 10)
    
    return "\n".join(content).encode()[:target_size]


def generate_corrupted_pdf() -> bytes:
    """Generate a corrupted PDF that will fail parsing."""
    # Start with valid PDF header, then corrupt it
    corrupted = b"%PDF-1.4\n"
    corrupted += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    corrupted += b"\x00\x00CORRUPTED_DATA\xff\xfe\x00\x00" * 100
    corrupted += b"%%EOF\n"
    # Add more garbage
    corrupted += bytes(random.getrandbits(8) for _ in range(10000))
    return corrupted


# =============================================================================
# Event Handlers for Metrics
# =============================================================================

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log request metrics for analysis."""
    if exception:
        print(f"[CHAOS] Request failed: {name} - {exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start."""
    if isinstance(environment.runner, MasterRunner):
        print("[CHAOS] Starting distributed stress test")
    else:
        print("[CHAOS] Starting stress test")
    
    # Log initial GPU state
    gpu_free = get_gpu_memory_free()
    if gpu_free:
        print(f"[CHAOS] Initial GPU free memory: {gpu_free}MB")


# =============================================================================
# Chaos Test User
# =============================================================================

class ChaosUser(HttpUser):
    """
    Simulates extreme user behavior to stress test the system.
    """
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup test user."""
        self.notebook_id = f"chaos-{random.randint(1000, 9999)}"
        
        # Create a test notebook
        self.client.post(
            "/api/notebooks",
            json={"name": f"Chaos Test {self.notebook_id}"},
            catch_response=True,
        )
    
    # =========================================================================
    # Scenario 1: "War and Peace" - Large File Upload
    # =========================================================================
    
    @task(3)
    def war_and_peace_upload(self):
        """
        Upload a 10MB text file.
        Monitor that Celery worker doesn't exceed memory limits.
        
        Expected: Worker should process in chunks, stay under 2GB.
        Failure: Worker freezes or crashes the system.
        """
        print(f"[CHAOS] Starting War and Peace test (10MB upload)")
        
        # Generate large file
        large_content = generate_large_text(LARGE_FILE_SIZE_MB)
        
        # Monitor memory before
        mem_before = get_celery_worker_memory()
        
        # Upload
        files = {
            "file": ("war_and_peace.txt", io.BytesIO(large_content), "text/plain")
        }
        
        with self.client.post(
            INGEST_ENDPOINT.format(notebook_id=self.notebook_id),
            files=files,
            catch_response=True,
            timeout=300,  # 5 min timeout for large file
        ) as response:
            # Check memory after upload starts
            time.sleep(5)  # Let processing begin
            mem_during = get_celery_worker_memory()
            
            if mem_during and mem_during > CELERY_MEMORY_LIMIT_MB:
                response.failure(
                    f"Memory exceeded limit! {mem_during}MB > {CELERY_MEMORY_LIMIT_MB}MB"
                )
                print(f"[CHAOS] ⚠️ MEMORY EXCEEDED: {mem_during}MB")
            elif response.status_code in (200, 201, 202):
                response.success()
                print(f"[CHAOS] ✓ Large file accepted. Memory: {mem_during}MB")
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    # =========================================================================
    # Scenario 2: "VRAM Squeeze" - Concurrent GPU Tasks
    # =========================================================================
    
    @task(2)
    def vram_squeeze(self):
        """
        Request podcast generation while running heavy graph query.
        
        Expected: System detects low VRAM, queues podcast with status update.
        Failure: CUDA OOM crash.
        """
        print("[CHAOS] Starting VRAM Squeeze test")
        
        # Check initial VRAM
        vram_before = get_gpu_memory_free()
        print(f"[CHAOS] VRAM before: {vram_before}MB")
        
        # Start heavy graph query (runs on GPU for embeddings)
        query_payload = {
            "message": "Explain the complete theory of quantum entanglement and its applications in computing, cryptography, and teleportation. Include mathematical formulations.",
            "context_node_ids": [],
        }
        
        # Fire query first
        self.client.post(
            QUERY_ENDPOINT.format(notebook_id=self.notebook_id),
            json=query_payload,
            catch_response=False,  # Don't wait
        )
        
        # Immediately request podcast (should trigger VRAM pressure)
        with self.client.post(
            PODCAST_ENDPOINT.format(notebook_id=self.notebook_id),
            json={"source_ids": ["*"], "duration_minutes": 5},
            catch_response=True,
            timeout=60,
        ) as response:
            vram_after = get_gpu_memory_free()
            
            if response.status_code == 503:
                # Expected behavior under load
                try:
                    data = response.json()
                    if data.get("status") == "queued" or "busy" in data.get("message", "").lower():
                        response.success()
                        print("[CHAOS] ✓ System correctly queued request under VRAM pressure")
                    else:
                        response.failure("503 without proper queue message")
                except:
                    response.failure("503 with unparseable response")
            elif response.status_code in (200, 201, 202):
                response.success()
                print(f"[CHAOS] ✓ Podcast request accepted. VRAM: {vram_after}MB")
            elif "CUDA" in response.text or "OOM" in response.text:
                response.failure("CUDA OOM detected!")
                print("[CHAOS] ❌ CUDA OOM DETECTED!")
            else:
                response.failure(f"Unexpected response: {response.status_code}")
    
    # =========================================================================
    # Scenario 3: "Poison Pill" - Corrupted File Upload
    # =========================================================================
    
    @task(2)
    def poison_pill(self):
        """
        Upload a corrupted PDF file.
        
        Expected: System catches parsing error, logs it, returns error status.
        Failure: Backend process crashes.
        """
        print("[CHAOS] Starting Poison Pill test (corrupted PDF)")
        
        # Generate corrupted file
        corrupted_pdf = generate_corrupted_pdf()
        
        files = {
            "file": ("malformed.pdf", io.BytesIO(corrupted_pdf), "application/pdf")
        }
        
        with self.client.post(
            INGEST_ENDPOINT.format(notebook_id=self.notebook_id),
            files=files,
            catch_response=True,
            timeout=30,
        ) as response:
            # Check that backend is still alive
            health_check = self.client.get(HEALTH_ENDPOINT)
            
            if health_check.status_code != 200:
                response.failure("Backend crashed after corrupted file!")
                print("[CHAOS] ❌ BACKEND CRASH DETECTED!")
                return
            
            # Acceptable responses for corrupted file
            if response.status_code in (400, 422):
                # Proper error handling
                try:
                    data = response.json()
                    if "error" in data or "detail" in data:
                        response.success()
                        print("[CHAOS] ✓ Corrupted file properly rejected with error message")
                    else:
                        response.failure("Error response missing error details")
                except:
                    response.success()  # At least it returned an error code
                    print("[CHAOS] ✓ Corrupted file rejected")
            elif response.status_code == 500:
                # Internal error but didn't crash
                response.success()  # Better than crashing
                print("[CHAOS] ⚠️ Server error but still alive")
            elif response.status_code in (200, 201, 202):
                # Should not accept corrupted file
                response.failure("Corrupted file was accepted!")
                print("[CHAOS] ⚠️ Corrupted file incorrectly accepted")
            else:
                response.failure(f"Unexpected response: {response.status_code}")
    
    # =========================================================================
    # Baseline Tasks for Mixed Load
    # =========================================================================
    
    @task(5)
    def normal_query(self):
        """Normal query to establish baseline."""
        self.client.post(
            QUERY_ENDPOINT.format(notebook_id=self.notebook_id),
            json={"message": "What is machine learning?", "context_node_ids": []},
        )
    
    @task(1)
    def health_check(self):
        """Periodic health check."""
        with self.client.get(HEALTH_ENDPOINT, catch_response=True) as response:
            if response.status_code != 200:
                response.failure("Health check failed!")


# =============================================================================
# Standalone Test Runner
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Sovereign Cognitive Engine - Chaos Monkey Test Suite")
    print("=" * 60)
    print()
    print("Run with Locust for full stress testing:")
    print("  locust -f tests/stress/chaos.py --host=http://localhost:8000")
    print()
    print("Or run individual tests:")
    print("  python tests/stress/chaos.py --test war_and_peace")
    print("  python tests/stress/chaos.py --test vram_squeeze")
    print("  python tests/stress/chaos.py --test poison_pill")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_name = sys.argv[2] if len(sys.argv) > 2 else "all"
        print(f"Running test: {test_name}")
        
        # Quick standalone tests
        if test_name == "gpu_check":
            free = get_gpu_memory_free()
            print(f"GPU Free Memory: {free}MB" if free else "No GPU detected")
        elif test_name == "memory_check":
            mem = get_celery_worker_memory()
            print(f"Worker Memory: {mem}MB" if mem else "Could not query worker memory")
