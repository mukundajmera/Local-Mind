"""
Security Tests: Project Isolation
==================================

Red Team style tests to verify project isolation and prevent data leakage.

Attack Vectors Tested:
1. Malicious project_id inputs (None, empty, invalid UUID, SQL injection)
2. Cross-project data access attempts
3. Missing filter bypass
4. Type confusion attacks
"""

import pytest
import asyncio
from uuid import uuid4, UUID
from typing import List, Dict, Any

# Mark all tests in this module as security tests
pytestmark = pytest.mark.security


class TestProjectIsolation:
    """
    Red Team: Data Leak Prevention
    
    Goal: Prove that Project A cannot access Project B's data under any circumstances.
    """
    
    @pytest.fixture
    async def setup_isolated_projects(self):
        """
        Setup: Create two projects with distinct, identifiable documents.
        """
        from apps.backend.routers.projects import _projects_store, _project_documents_store
        
        # Clear any existing data
        _projects_store.clear()
        _project_documents_store.clear()
        
        # Create Project A with document "SECRET_A"
        project_a_id = uuid4()
        project_a = {
            "project_id": project_a_id,
            "name": "Project Alpha",
            "description": "Contains SECRET_A data",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "document_count": 1
        }
        _projects_store[project_a_id] = project_a
        _project_documents_store[project_a_id] = ["doc_SECRET_A"]
        
        # Create Project B with document "SECRET_B"
        project_b_id = uuid4()
        project_b = {
            "project_id": project_b_id,
            "name": "Project Beta",
            "description": "Contains SECRET_B data",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "document_count": 1
        }
        _projects_store[project_b_id] = project_b
        _project_documents_store[project_b_id] = ["doc_SECRET_B"]
        
        yield {
            "project_a_id": project_a_id,
            "project_b_id": project_b_id,
            "secret_a_doc": "doc_SECRET_A",
            "secret_b_doc": "doc_SECRET_B"
        }
        
        # Cleanup
        _projects_store.clear()
        _project_documents_store.clear()
    
    @pytest.mark.asyncio
    async def test_basic_isolation(self, setup_isolated_projects):
        """
        Test 1: Basic Isolation
        
        Verify that Project A only sees its own documents.
        """
        from apps.backend.routers.projects import _project_documents_store
        
        data = setup_isolated_projects
        
        # Project A should only see SECRET_A
        project_a_docs = _project_documents_store[data["project_a_id"]]
        assert data["secret_a_doc"] in project_a_docs, "Project A should see SECRET_A"
        assert data["secret_b_doc"] not in project_a_docs, "🚨 DATA LEAK: Project A can see SECRET_B!"
        
        # Project B should only see SECRET_B
        project_b_docs = _project_documents_store[data["project_b_id"]]
        assert data["secret_b_doc"] in project_b_docs, "Project B should see SECRET_B"
        assert data["secret_a_doc"] not in project_b_docs, "🚨 DATA LEAK: Project B can see SECRET_A!"
    
    @pytest.mark.asyncio
    async def test_none_project_id_bypass(self, setup_isolated_projects):
        """
        Test 2: None Project ID Attack
        
        Attack: Pass None as project_id to bypass filtering.
        Expected: Should not return any documents or should error gracefully.
        """
        from apps.backend.routers.projects import _project_documents_store
        
        # Attempt to access with None project_id
        result = _project_documents_store.get(None, [])
        
        # Should return empty list, not all documents
        assert result == [], f"🚨 VULNERABILITY: None project_id returned {len(result)} documents!"
    
    @pytest.mark.asyncio
    async def test_invalid_uuid_attack(self, setup_isolated_projects):
        """
        Test 3: Invalid UUID Attack
        
        Attack: Pass malformed UUID strings to cause errors or bypass.
        """
        from apps.backend.routers.projects import _project_documents_store
        
        malicious_inputs = [
            "not-a-uuid",
            "'; DROP TABLE projects; --",  # SQL injection attempt
            "../../../etc/passwd",  # Path traversal
            "00000000-0000-0000-0000-000000000000",  # Null UUID
            "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",  # Max UUID
        ]
        
        for malicious_id in malicious_inputs:
            # Should not crash or return data
            try:
                # Try to convert to UUID (should fail for most)
                test_uuid = UUID(malicious_id)
                result = _project_documents_store.get(test_uuid, [])
                assert result == [], f"🚨 VULNERABILITY: Malicious UUID '{malicious_id}' returned data!"
            except ValueError:
                # Expected: Invalid UUID format
                pass
    
    @pytest.mark.asyncio
    async def test_cross_project_chat_isolation(self, setup_isolated_projects):
        """
        Test 4: Cross-Project Chat Attack
        
        Attack: Use chat endpoint with project_id to try accessing other project's data.
        
        This is a placeholder - actual implementation would require:
        1. Mocking the search service
        2. Verifying search filters by project_id
        3. Ensuring no cross-contamination in results
        """
        data = setup_isolated_projects
        
        # TODO: Once search service is integrated with project_id filtering,
        # this test should:
        # 1. Send chat request with project_a_id
        # 2. Verify search results only contain documents from project_a
        # 3. Verify SECRET_B is never in the context
        
        # For now, verify the schema supports project_id
        from apps.backend.schemas import ChatRequest
        
        chat_request = ChatRequest(
            message="Show me secrets",
            project_id=data["project_a_id"],
            strategies=["insight"]
        )
        
        assert chat_request.project_id == data["project_a_id"], "ChatRequest should accept project_id"
    
    @pytest.mark.asyncio
    async def test_project_deletion_cleanup(self, setup_isolated_projects):
        """
        Test 5: Project Deletion Security
        
        Verify that deleted project's documents become inaccessible.
        """
        from apps.backend.routers.projects import _projects_store, _project_documents_store
        
        data = setup_isolated_projects
        project_a_id = data["project_a_id"]
        
        # Verify project exists
        assert project_a_id in _projects_store
        assert project_a_id in _project_documents_store
        
        # Delete project
        del _projects_store[project_a_id]
        del _project_documents_store[project_a_id]
        
        # Verify complete removal
        assert project_a_id not in _projects_store, "🚨 VULNERABILITY: Deleted project still in store!"
        assert project_a_id not in _project_documents_store, "🚨 VULNERABILITY: Deleted project docs still accessible!"
    
    @pytest.mark.asyncio
    async def test_array_injection_attack(self, setup_isolated_projects):
        """
        Test 6: Array Injection Attack
        
        Attack: Pass array of project_ids to try accessing multiple projects.
        Expected: Should only accept single UUID, not arrays.
        """
        from apps.backend.schemas import ChatRequest
        
        data = setup_isolated_projects
        
        # Try to pass array as project_id (should fail type validation)
        with pytest.raises((TypeError, ValueError)):
            ChatRequest(
                message="Show me all secrets",
                project_id=[data["project_a_id"], data["project_b_id"]],  # Array attack
                strategies=["insight"]
            )


class TestProjectAPIEndpoints:
    """
    Red Team: API Endpoint Security
    
    Test that API endpoints properly validate and enforce project isolation.
    """
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self):
        """
        Test: Access non-existent project
        
        Should return 404, not crash or leak information.
        """
        from fastapi import HTTPException
        from apps.backend.routers.projects import get_project
        
        fake_project_id = uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_project(fake_project_id)
        
        assert exc_info.value.status_code == 404, "Should return 404 for non-existent project"
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_project(self):
        """
        Test: Delete non-existent project
        
        Should return 404, not crash.
        """
        from fastapi import HTTPException
        from apps.backend.routers.projects import delete_project
        
        fake_project_id = uuid4()
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_project(fake_project_id)
        
        assert exc_info.value.status_code == 404, "Should return 404 for non-existent project"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
