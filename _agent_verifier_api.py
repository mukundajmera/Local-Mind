#!/usr/bin/env python3
import asyncio
import httpx
import sys

BASE_URL = "http://localhost:8000/api/v1"

async def test_projects_api():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        print("Testing POST /projects...")
        resp = await client.post("/projects", json={"name": "Verifier Project", "description": "Test"})
        resp.raise_for_status()
        project_id = resp.json()["project_id"]
        print(f"Project created: {project_id}")

        print(f"Testing PATCH /projects/{project_id}...")
        resp = await client.patch(f"/projects/{project_id}", json={"name": "Renamed Verifier Project"})
        resp.raise_for_status()
        assert resp.json()["name"] == "Renamed Verifier Project"
        print("Project renamed successfully.")

        print(f"Testing DELETE /projects/{project_id}...")
        resp = await client.delete(f"/projects/{project_id}")
        resp.raise_for_status()
        print("Project deleted successfully.")

async def test_system_models_api():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        print("Testing GET /system/models/available...")
        resp = await client.get("/system/models/available")
        resp.raise_for_status()
        models = resp.json()
        print(f"Available models: {models}")
        assert isinstance(models, list), "Expected list of models"

        print("Testing GET /system/models/current...")
        resp = await client.get("/system/models/current")
        resp.raise_for_status()
        current = resp.json()
        print(f"Current model info: {current}")
        assert "current_model" in current, "Expected current_model in response"

async def main():
    try:
        await test_projects_api()
        await test_system_models_api()
        print("PASS")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"FAIL: HTTP Error {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
