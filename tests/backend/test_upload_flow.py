"""
Test Upload Flow - Backend Tests
=================================
Verifies the async upload flow with task_id and status polling.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import sys
import os
from pathlib import Path
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/backend"))

from main import app, upload_tasks

client = TestClient(app)


class TestUploadEndpoint:
    """Tests for POST /api/v1/sources/upload"""

    def test_upload_returns_202_with_task_id(self):
        """
        CRITICAL: Upload must return 202 Accepted with task_id immediately.
        This prevents the frontend from hanging on long-running uploads.
        """
        # Create minimal test file
        file_content = b"# Test Document\n\nThis is test content for upload."
        files = {"file": ("test_doc.md", file_content, "text/markdown")}

        with patch("main._process_upload_background", new_callable=AsyncMock):
            response = client.post("/api/v1/sources/upload", files=files)

        # MUST be 202 Accepted, NOT 200
        assert response.status_code == 202, f"Expected 202, got {response.status_code}"

        data = response.json()
        assert "task_id" in data, "Response must include task_id"
        assert data["status"] == "accepted", "Status should be 'accepted'"
        assert len(data["task_id"]) == 36, "task_id should be a UUID"

    def test_upload_creates_task_entry(self):
        """Verify upload creates an entry in upload_tasks store."""
        file_content = b"Test content for task tracking"
        files = {"file": ("task_test.txt", file_content, "text/plain")}

        with patch("main._process_upload_background", new_callable=AsyncMock):
            response = client.post("/api/v1/sources/upload", files=files)

        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # Task should be tracked
        assert task_id in upload_tasks
        assert upload_tasks[task_id]["status"] == "processing"
        assert upload_tasks[task_id]["progress"] == 10


class TestUploadStatusEndpoint:
    """Tests for GET /api/v1/upload/{task_id}/status"""

    def test_status_returns_404_for_unknown_task(self):
        """Unknown task_id should return 404."""
        response = client.get("/api/v1/upload/nonexistent-task-id/status")
        assert response.status_code == 404

    def test_status_returns_progress_info(self):
        """Status endpoint returns correct progress structure."""
        # Manually insert a task
        test_task_id = "test-status-task-123"
        upload_tasks[test_task_id] = {
            "status": "processing",
            "progress": 50,
            "stage": "embedding",
            "filename": "test.pdf",
        }

        try:
            response = client.get(f"/api/v1/upload/{test_task_id}/status")
            assert response.status_code == 200

            data = response.json()
            assert "status" in data
            assert "progress" in data
            assert data["status"] == "processing"
            assert data["progress"] == 50
        finally:
            # Cleanup
            del upload_tasks[test_task_id]

    def test_status_returns_doc_id_on_completion(self):
        """Completed tasks should include doc_id."""
        test_task_id = "test-complete-task-456"
        upload_tasks[test_task_id] = {
            "status": "completed",
            "progress": 100,
            "stage": "done",
            "doc_id": "doc-abc-123",
            "filename": "completed.pdf",
        }

        try:
            response = client.get(f"/api/v1/upload/{test_task_id}/status")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "completed"
            assert data["progress"] == 100
            assert data["doc_id"] == "doc-abc-123"
        finally:
            del upload_tasks[test_task_id]

    def test_status_returns_error_on_failure(self):
        """Failed tasks should include error message."""
        test_task_id = "test-failed-task-789"
        upload_tasks[test_task_id] = {
            "status": "failed",
            "progress": 0,
            "error": "Connection to database failed",
        }

        try:
            response = client.get(f"/api/v1/upload/{test_task_id}/status")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "failed"
            assert "error" in data
            assert "database" in data["error"].lower()
        finally:
            del upload_tasks[test_task_id]


class TestUploadFlowIntegration:
    """Integration tests simulating the full frontend polling flow."""

    def test_polling_flow_simulation(self):
        """
        Simulates the frontend polling pattern:
        1. Upload file -> get task_id
        2. Poll status until completed/failed
        """
        file_content = b"# Integration Test\n\nContent for polling test."
        files = {"file": ("poll_test.md", file_content, "text/markdown")}

        # Step 1: Upload
        with patch("main._process_upload_background", new_callable=AsyncMock):
            upload_response = client.post("/api/v1/sources/upload", files=files)

        assert upload_response.status_code == 202
        task_id = upload_response.json()["task_id"]

        # Step 2: Initial poll - should be processing
        status_response = client.get(f"/api/v1/upload/{task_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "processing"

        # Step 3: Simulate background completion
        upload_tasks[task_id]["status"] = "completed"
        upload_tasks[task_id]["progress"] = 100
        upload_tasks[task_id]["doc_id"] = "simulated-doc-id"

        # Step 4: Poll again - should be completed
        final_response = client.get(f"/api/v1/upload/{task_id}/status")
        assert final_response.status_code == 200
        data = final_response.json()
        assert data["status"] == "completed"
        assert data["doc_id"] == "simulated-doc-id"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
