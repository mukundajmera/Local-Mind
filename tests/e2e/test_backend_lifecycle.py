
import os
import requests
import time
import uuid
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000/api/v1"
TEST_PROJECT_ID = str(uuid.uuid4())
OTHER_PROJECT_ID = str(uuid.uuid4())
TEST_FILE_CONTENT = b"This is a test document for project isolation."
TEST_FILENAME = "project_test.txt"

def run_verification():
    print(f"Testing with Project ID: {TEST_PROJECT_ID}")
    
    # 1. Create a dummy file
    with open(TEST_FILENAME, "wb") as f:
        f.write(TEST_FILE_CONTENT)
    
    try:
        # 2. Upload file with Project ID
        print(f"Uploading {TEST_FILENAME}...")
        with open(TEST_FILENAME, "rb") as f:
            files = {"file": f}
            # Depending on how main.py expects project_id (query or form), I'll try query param first as per my change
            # Wait, I added it as a query param in upload_source default? No, I added it as a default arg fastapi usually takes from query.
            # let's try query param.
            response = requests.post(
                f"{API_URL}/sources/upload", 
                files=files, 
                params={"project_id": TEST_PROJECT_ID}
            )
        
        if response.status_code != 202:
            print(f"FAIL: Upload failed with {response.status_code} {response.text}")
            exit(1)
            
        task_id = response.json()["task_id"]
        print(f"Upload accepted, Task ID: {task_id}")
        
        # 3. Poll for completion
        for _ in range(20):
            status_res = requests.get(f"{API_URL}/upload/{task_id}/status")
            status = status_res.json()
            print(f"Status: {status['status']} - {status.get('progress')}%")
            if status["status"] == "completed":
                doc_id = status["doc_id"]
                saved_filename = status["filename"]
                print(f"Upload complete. Doc ID: {doc_id}, Filename: {saved_filename}")
                
                # Check timestamp format
                if "_" not in saved_filename or ".txt" not in saved_filename:
                     print(f"FAIL: Filename {saved_filename} does not match expected format stem_timestamp.suffix")
                     exit(1)
                break
            if status["status"] == "failed":
                print(f"FAIL: Upload task failed: {status.get('error')}")
                exit(1)
            time.sleep(1)
        else:
            print("FAIL: Upload timed out")
            exit(1)
            
        # 4. Verify Project Isolation
        # Check if visible in correct project
        print("Checking visibility in correct project...")
        res_correct = requests.get(f"{API_URL}/sources", params={"project_id": TEST_PROJECT_ID})
        sources_correct = res_correct.json()["sources"]
        found = any(s["id"] == doc_id for s in sources_correct)
        if not found:
            print("FAIL: Document not found in correct project list")
            exit(1)
        print("PASS: Document found in correct project.")
        
        # Check if invisible in other project
        print("Checking visibility in other project...")
        res_other = requests.get(f"{API_URL}/sources", params={"project_id": OTHER_PROJECT_ID})
        sources_other = res_other.json()["sources"]
        found_other = any(s["id"] == doc_id for s in sources_other)
        if found_other:
             print("FAIL: Document LEAKED into other project list")
             exit(1)
        print("PASS: Document isolated from other project.")
        
        # 5. Delete Document
        print(f"Deleting document {doc_id}...")
        del_res = requests.delete(f"{API_URL}/sources/{doc_id}")
        if del_res.status_code != 200:
             print(f"FAIL: Delete failed {del_res.status_code}")
             exit(1)
        
        # Verify gone
        check_res = requests.get(f"{API_URL}/sources", params={"project_id": TEST_PROJECT_ID})
        if any(s["id"] == doc_id for s in check_res.json()["sources"]):
            print("FAIL: Document still listed after deletion!")
            exit(1)
        print("PASS: Document deleted successfully.")
        
        print("ALL CHECKS PASSED")
        
    finally:
        if os.path.exists(TEST_FILENAME):
            os.remove(TEST_FILENAME)

if __name__ == "__main__":
    run_verification()
