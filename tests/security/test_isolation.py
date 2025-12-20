
import pytest
import requests
import uuid

# Configuration
API_URL = "http://localhost:8000/api/v1"

@pytest.fixture
def unique_project_ids():
    return str(uuid.uuid4()), str(uuid.uuid4())

def test_tenant_isolation_wall(unique_project_ids):
    """
    The Wall Test:
    1. Ingest Alpha_Secret into Project Alpha.
    2. Request GET /sources with Project Beta header/param.
    3. Assert results are EMPTY (or at least do not contain Alpha_Secret).
    """
    project_alpha, project_beta = unique_project_ids
    
    # 1. Ingest into Alpha
    files = {"file": ("alpha_secret.txt", b"top secret alpha content")}
    # Using 'params' for project_id as implemented in main.py
    res_upload = requests.post(
        f"{API_URL}/sources/upload",
        files=files,
        params={"project_id": project_alpha}
    )
    assert res_upload.status_code == 202
    task_id = res_upload.json()["task_id"]
    
    # Wait for completion (using a simple poll loop)
    import time
    doc_id = None
    for _ in range(20):
        status = requests.get(f"{API_URL}/upload/{task_id}/status").json()
        if status["status"] == "completed":
            doc_id = status["doc_id"]
            break
        time.sleep(0.5)
    
    assert doc_id is not None, "Upload failed to complete"
    
    # 2. The Attack: Beta queries for sources
    res_attack = requests.get(f"{API_URL}/sources", params={"project_id": project_beta})
    assert res_attack.status_code == 200
    sources = res_attack.json()["sources"]
    
    # 3. Assert Alpha Secret is NOT visible
    found = any(s["id"] == doc_id for s in sources)
    assert not found, f"SECURITY BREACH: Document {doc_id} from Project {project_alpha} leaked into Project {project_beta}!"

def test_cross_tenant_access_denied(unique_project_ids):
    """
    Future-proofing: Ensure explicit ID Access Check (if implemented).
    Currently, get_all_sources filters by project_id in the query.
    If we had a direct GET /sources/{doc_id}, we would test it here.
    For now, we test list isolation which is the primary vector.
    """
    pass
