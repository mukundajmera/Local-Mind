#!/usr/bin/env python3
"""
Local Mind E2E Verifier — tests all core API flows.
Exit 0 on success, Exit 1 on failure.
"""

import asyncio
import httpx
import sys
import time
import json
import os

BASE = "http://127.0.0.1:8000"
PASS_COUNT = 0
FAIL_COUNT = 0
RESULTS = []

def log(ok, test_name, detail=""):
    global PASS_COUNT, FAIL_COUNT
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS_COUNT += 1
    else:
        FAIL_COUNT += 1
    msg = f"[{status}] {test_name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    RESULTS.append((status, test_name, detail))


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:
        # ---------------------------------------------------------------
        # 1. Health check
        # ---------------------------------------------------------------
        try:
            r = await c.get("/health")
            data = r.json()
            log(r.status_code == 200, "Health Check", f"status={data.get('status')}")
        except Exception as e:
            log(False, "Health Check", str(e))
            print("\n❌ Backend is not reachable. Aborting.")
            sys.exit(1)

        # ---------------------------------------------------------------
        # 2. List projects (initial)
        # ---------------------------------------------------------------
        r = await c.get("/api/v1/projects")
        projects = r.json() if r.status_code == 200 else []
        log(r.status_code == 200, "List Projects", f"found {len(projects)} projects")

        # ---------------------------------------------------------------
        # 3. Create project
        # ---------------------------------------------------------------
        r = await c.post("/api/v1/projects", json={
            "name": f"Demo Project E2E {int(time.time())}",
            "description": "Created by E2E verifier"
        })
        if r.status_code == 201:
            project = r.json()
            project_id = project["project_id"]
            log(True, "Create Project", f"id={project_id}")
        elif r.status_code == 400 and "already exists" in r.text:
            # Project already exists - find it
            r2 = await c.get("/api/v1/projects")
            existing = [p for p in r2.json() if p["name"] == "Demo Project E2E"]
            if existing:
                project_id = existing[0]["project_id"]
                log(True, "Create Project (exists)", f"id={project_id}")
            else:
                log(False, "Create Project", "already exists but not found")
                sys.exit(1)
        else:
            log(False, "Create Project", f"status={r.status_code} body={r.text[:200]}")
            sys.exit(1)

        # ---------------------------------------------------------------
        # 4. Upload document 1 (TXT)
        # ---------------------------------------------------------------
        doc1_path = "/tmp/localmind_demo_doc1.txt"
        if os.path.exists(doc1_path):
            with open(doc1_path, "rb") as f:
                r = await c.post(
                    "/api/v1/sources/upload",
                    files={"file": ("Understanding_LLMs.txt", f, "text/plain")},
                    data={"project_id": project_id}
                )
            if r.status_code == 202:
                doc1_id = r.json()["id"]
                log(True, "Upload Doc 1 (TXT)", f"id={doc1_id}")
            else:
                log(False, "Upload Doc 1 (TXT)", f"status={r.status_code} body={r.text[:200]}")
                doc1_id = None
        else:
            log(False, "Upload Doc 1 (TXT)", "file not found")
            doc1_id = None

        # ---------------------------------------------------------------
        # 5. Upload document 2 (MD)
        # ---------------------------------------------------------------
        doc2_path = "/tmp/localmind_demo_doc2.md"
        if os.path.exists(doc2_path):
            with open(doc2_path, "rb") as f:
                r = await c.post(
                    "/api/v1/sources/upload",
                    files={"file": ("Privacy_First_AI.md", f, "text/markdown")},
                    data={"project_id": project_id}
                )
            if r.status_code == 202:
                doc2_id = r.json()["id"]
                log(True, "Upload Doc 2 (MD)", f"id={doc2_id}")
            else:
                log(False, "Upload Doc 2 (MD)", f"status={r.status_code} body={r.text[:200]}")
                doc2_id = None
        else:
            log(False, "Upload Doc 2 (MD)", "file not found")
            doc2_id = None

        # ---------------------------------------------------------------
        # 6. Poll document status (wait for READY)
        # ---------------------------------------------------------------
        for doc_label, doc_id in [("Doc 1", doc1_id), ("Doc 2", doc2_id)]:
            if not doc_id:
                continue
            max_polls = 30
            final_status = "unknown"
            for i in range(max_polls):
                r = await c.get(f"/api/v1/sources/{doc_id}/status")
                if r.status_code == 200:
                    status = r.json().get("status", "unknown")
                    final_status = status
                    if status in ("ready", "failed"):
                        break
                await asyncio.sleep(2)
            log(final_status == "ready", f"Poll Status ({doc_label})", f"status={final_status}")

        # ---------------------------------------------------------------
        # 7. List sources (should include our uploads)
        # ---------------------------------------------------------------
        r = await c.get(f"/api/v1/sources?project_id={project_id}")
        sources = r.json().get("sources", []) if r.status_code == 200 else []
        log(len(sources) >= 2, "List Sources", f"found {len(sources)} sources for project")

        # ---------------------------------------------------------------
        # 8. Get briefing for doc 1
        # ---------------------------------------------------------------
        if doc1_id:
            r = await c.get(f"/api/v1/sources/{doc1_id}/briefing")
            if r.status_code == 200:
                briefing = r.json()
                has_summary = bool(briefing.get("summary"))
                has_topics = len(briefing.get("key_topics", [])) > 0
                log(has_summary and has_topics, "Get Briefing (Doc 1)", 
                    f"summary={len(briefing.get('summary',''))} chars, topics={len(briefing.get('key_topics', []))}")
            else:
                log(False, "Get Briefing (Doc 1)", f"status={r.status_code}")

        # ---------------------------------------------------------------
        # 9. Chat endpoint
        # ---------------------------------------------------------------
        r = await c.post("/api/v1/chat", json={
            "message": "What are the key concepts in large language models?",
            "strategies": ["sources"],
            "project_id": project_id,
            "source_ids": [doc1_id] if doc1_id else None,
        })
        if r.status_code == 200:
            chat_data = r.json()
            has_response = bool(chat_data.get("response"))
            log(has_response, "Chat Endpoint", f"response={len(chat_data.get('response',''))} chars, context_used={chat_data.get('context_used')}")
        else:
            log(False, "Chat Endpoint", f"status={r.status_code} body={r.text[:200]}")

        # ---------------------------------------------------------------
        # 10. Rename source
        # ---------------------------------------------------------------
        if doc1_id:
            r = await c.patch(f"/api/v1/sources/{doc1_id}", json={"title": "Understanding LLMs (Renamed)"})
            log(r.status_code == 200, "Rename Source", f"status={r.status_code}")

        # ---------------------------------------------------------------
        # 11. Get project details
        # ---------------------------------------------------------------
        r = await c.get(f"/api/v1/projects/{project_id}")
        if r.status_code == 200:
            proj = r.json()
            log(True, "Get Project Details", f"name={proj.get('name')}, docs={proj.get('document_count')}")
        else:
            log(False, "Get Project Details", f"status={r.status_code}")

        # ---------------------------------------------------------------
        # 12. Models endpoint
        # ---------------------------------------------------------------
        r = await c.get("/api/v1/models")
        if r.status_code == 200:
            models = r.json()
            log(True, "Models Endpoint", f"provider={models.get('provider')}, count={len(models.get('models', []))}")
        else:
            log(False, "Models Endpoint", f"status={r.status_code}")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
    print("=" * 60)
    
    if FAIL_COUNT > 0:
        print("\nFAILED TESTS:")
        for status, name, detail in RESULTS:
            if status == "FAIL":
                print(f"  ❌ {name}: {detail}")
        print("\nFAIL")
        sys.exit(1)
    else:
        print("\nPASS")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
