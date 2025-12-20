"""
Ironclad Security Test - Project Isolation
===========================================
Adversarial test: Data from Project Alpha must NEVER leak to Project Beta.

Strategy:
1. Seed a SECRET string into "Project Alpha".
2. Attack by querying for that secret using "Project Beta" headers.
3. Assert that ZERO results are returned (not just an error, but absence of data).
"""

import pytest
import httpx
import uuid
import os
import tempfile
from pathlib import Path

# Mark all tests as integration-level
pytestmark = pytest.mark.integration

# Unique secret for this test run
SECRET_MARKER = f"IRONCLAD_SECRET_{uuid.uuid4().hex[:8]}"

API_URL = os.getenv("API_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def project_alpha_id() -> str:
    """Generate a unique ID for Project Alpha."""
    return f"project-alpha-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def project_beta_id() -> str:
    """Generate a unique ID for Project Beta."""
    return f"project-beta-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def secret_file(tmp_path_factory) -> Path:
    """Create a temporary file containing the secret marker."""
    tmp_dir = tmp_path_factory.mktemp("secrets")
    secret_doc = tmp_dir / "secret_document.txt"
    secret_doc.write_text(f"""
    This is a classified document for Project Alpha.
    
    The secret code is: {SECRET_MARKER}
    
    This information MUST NOT be visible to any other project.
    """)
    return secret_doc


@pytest.fixture
def http_client():
    """Sync HTTP client for testing."""
    with httpx.Client(base_url=API_URL, timeout=120.0) as client:
        yield client


class TestProjectIsolation:
    """
    Adversarial tests for multi-tenant project isolation.
    These tests simulate a malicious tenant trying to access another tenant's data.
    """
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, http_client, project_alpha_id, secret_file):
        """
        Setup: Ingest secret document into Project Alpha.
        Teardown: Clean up all test data.
        """
        doc_id = None
        
        # --- SETUP: Upload secret to Project Alpha ---
        with open(secret_file, "rb") as f:
            response = http_client.post(
                "/api/v1/upload",
                files={"file": ("secret_document.txt", f, "text/plain")},
                params={"project_id": project_alpha_id},
            )
        
        if response.status_code == 202:
            task_id = response.json().get("task_id")
            # Poll for completion
            for _ in range(30):
                status_resp = http_client.get(f"/api/v1/upload/{task_id}/status")
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    if status_data.get("status") == "completed":
                        doc_id = status_data.get("doc_id")
                        break
                    elif status_data.get("status") == "failed":
                        pytest.fail(f"Upload failed: {status_data}")
                import time
                time.sleep(1)
        
        self.doc_id = doc_id
        yield
        
        # --- TEARDOWN: Delete test document ---
        if doc_id:
            try:
                http_client.delete(f"/api/v1/sources/{doc_id}")
            except Exception:
                pass  # Best effort cleanup

    def test_leak_via_search_returns_zero_results(
        self, http_client, project_alpha_id, project_beta_id
    ):
        """
        ATTACK: Search for the secret using Project Beta's context.
        
        ASSERTION: Must return EXACTLY 0 results.
        We don't just check for errors - we check for the ABSENCE of data.
        """
        # Attack: Search for the secret marker using Project Beta
        response = http_client.post(
            "/api/v1/chat",
            json={
                "message": f"Find information about {SECRET_MARKER}",
                "project_id": project_beta_id,
                "source_ids": [],  # Search all sources in "Project Beta"
            },
        )
        
        # The request should succeed (no 500 errors)
        assert response.status_code == 200, f"Request failed: {response.text}"
        
        data = response.json()
        
        # CRITICAL ASSERTION: The secret marker MUST NOT appear in the response
        response_text = str(data)
        assert SECRET_MARKER not in response_text, (
            f"DATA LEAK DETECTED: Secret marker '{SECRET_MARKER}' "
            f"found in Project Beta response!"
        )
        
        # Additional check: If sources are returned, verify count
        sources = data.get("sources", [])
        assert len(sources) == 0, (
            f"ISOLATION BREACH: Project Beta returned {len(sources)} sources "
            f"when it should have 0. Sources: {sources}"
        )

    def test_leak_via_sources_list_returns_zero(
        self, http_client, project_alpha_id, project_beta_id
    ):
        """
        ATTACK: List all sources for Project Beta.
        
        ASSERTION: Must return EXACTLY 0 sources from Project Alpha.
        """
        # Query sources for Project Beta
        response = http_client.get(
            "/api/v1/sources",
            params={"project_id": project_beta_id},
        )
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        
        sources = response.json()
        
        # CRITICAL ASSERTION: No sources should appear for Project Beta
        # that were uploaded to Project Alpha
        for source in sources:
            assert SECRET_MARKER not in str(source.get("title", "")), (
                f"DATA LEAK: Source '{source}' visible to wrong project!"
            )
            # Also verify the source's doc_id is not our alpha doc
            if self.doc_id:
                assert source.get("doc_id") != self.doc_id, (
                    f"ISOLATION BREACH: Doc {self.doc_id} from Alpha is visible to Beta!"
                )

    def test_direct_doc_access_fails_for_wrong_project(
        self, http_client, project_alpha_id, project_beta_id
    ):
        """
        ATTACK: Try to directly reference Alpha's doc_id in Beta's chat.
        
        ASSERTION: No data should be returned.
        """
        if not self.doc_id:
            pytest.skip("No doc_id available from setup")
        
        response = http_client.post(
            "/api/v1/chat",
            json={
                "message": "Summarize this document",
                "project_id": project_beta_id,
                "source_ids": [self.doc_id],  # Directly reference Alpha's doc!
            },
        )
        
        # This should either fail or return no relevant data
        if response.status_code == 200:
            data = response.json()
            response_text = str(data)
            assert SECRET_MARKER not in response_text, (
                f"CRITICAL LEAK: Direct doc access bypassed isolation! "
                f"Secret '{SECRET_MARKER}' found in response!"
            )
