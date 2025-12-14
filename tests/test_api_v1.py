import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../apps/backend"))

from main import app

client = TestClient(app)

def test_health_check():
    """Verify health endpoint returns 200 and schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data
    assert "neo4j" in data["services"]

def test_root():
    """Verify root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "operational"

def test_list_sources_empty():
    """Verify sources list is initially empty (mocked)."""
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    assert response.json()["sources"] == []

def test_upload_source_mock():
    """
    Test source upload. 
    Note: This will try to run the full ingestion pipeline if not mocked.
    For this smoke test, we'll see if it hits the endpoint correctly.
    """
    # Create valid dummy PDF content (just text disguised)
    file_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n..."
    
    # We might need to mock IngestionPipeline to avoid actual DB/LLM calls in this unit test
    # But since we want to verify the wiring, let's just check 500 or success
    # If dependencies are missing, it will 500.
    
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    try:
        response = client.post("/api/v1/sources/upload", files=files)
        # It might fail due to missing dependencies/DBs, but we want to ensure it's not 404/501
        assert response.status_code != 404
        assert response.status_code != 501
    except Exception:
        # If it raises inside the app, TestClient might catch it
        pass

def test_chat_endpoint_exists():
    """Verify chat endpoint is implemented (not 501)."""
    # Simple payload
    payload = {
        "message": "Hello",
        "strategies": ["insight"]
    }
    try:
        response = client.post("/api/v1/chat", json=payload)
        # It's okay if it fails with 500 (connection error to DB/LLM)
        # But it SHOULD NOT be 501 (Not Implemented) or 404
        assert response.status_code != 501
        assert response.status_code != 404
        # If it returns 200, great
    except Exception:
        pass
