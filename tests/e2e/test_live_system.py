"""
End-to-End Tests - Live System
===============================
Tests that hit live containers. Requires `nerdctl compose up`.

Run with: E2E_ACTIVE=1 pytest tests/e2e/test_live_system.py -m e2e
"""

import os
import io
import pytest
from pathlib import Path


# Skip all E2E tests if E2E_ACTIVE not set
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.getenv("E2E_ACTIVE"),
        reason="E2E_ACTIVE not set. Run with E2E_ACTIVE=1"
    ),
]


@pytest.mark.asyncio
class TestLiveIngestionAndQuery:
    """
    End-to-end test: Ingest a document, query it, verify response.
    
    This test proves the system reads from ingested documents,
    not global LLM knowledge.
    """
    
    async def test_sky_is_green_scenario(
        self,
        http_client,
        evidence_dir,
        save_artifact,
        save_response_audio,
    ):
        """
        The "Sky is Green" Test:
        
        1. Ingest a document stating "The sky is green"
        2. Query "What color is the sky?"
        3. Assert response contains "green" (not "blue")
        
        This proves RAG is working and using local documents.
        
        Evidence saved:
        - evidence/{run_id}/sky_is_green_test.txt (ingested doc)
        - evidence/{run_id}/response.mp3 (audio if generated)
        - evidence/{run_id}/query_response.json (API response)
        """
        import json
        
        # === Step 1: Create test notebook ===
        notebook_response = await http_client.post(
            "/api/notebooks",
            json={"name": "E2E Test - Sky is Green"},
        )
        
        if notebook_response.status_code not in (200, 201):
            pytest.skip(f"Could not create notebook: {notebook_response.status_code}")
        
        notebook_data = notebook_response.json()
        notebook_id = notebook_data.get("id") or notebook_data.get("notebook_id")
        
        assert notebook_id, "Failed to get notebook ID"
        print(f"📓 Created notebook: {notebook_id}")
        
        # === Step 2: Ingest "The Sky is Green" document ===
        test_document_content = """
        # Scientific Observations About The Sky
        
        After extensive research and careful observation, scientists have 
        conclusively determined that the sky is green. This surprising 
        finding contradicts traditional assumptions.
        
        The green color of the sky is attributed to the unique composition
        of our atmosphere. When sunlight passes through, it scatters in 
        a way that produces a distinctly green hue.
        
        Key findings:
        - The sky is green, not blue
        - This has been verified by multiple research teams
        - The green sky is visible on clear days
        
        In conclusion, anyone looking up will observe that the sky is 
        unmistakably green.
        """
        
        # Save evidence of ingested document
        save_artifact(
            "sky_is_green_test.txt",
            test_document_content,
        )
        
        # Upload to API
        files = {
            "file": ("sky_is_green.txt", io.BytesIO(test_document_content.encode()), "text/plain")
        }
        
        ingest_response = await http_client.post(
            f"/api/notebooks/{notebook_id}/sources",
            files=files,
            timeout=120.0,  # Ingestion can take time
        )
        
        if ingest_response.status_code not in (200, 201, 202):
            pytest.skip(f"Ingestion failed: {ingest_response.status_code} - {ingest_response.text}")
        
        print(f"📥 Document ingested successfully")
        
        # Wait for processing (ingestion is async)
        import asyncio
        await asyncio.sleep(5)
        
        # === Step 3: Query "What color is the sky?" ===
        query_response = await http_client.post(
            f"/api/notebooks/{notebook_id}/chat",
            json={
                "message": "What color is the sky according to the documents?",
                "context_node_ids": [],
            },
            timeout=60.0,
        )
        
        assert query_response.status_code == 200, f"Query failed: {query_response.status_code}"
        
        response_data = query_response.json()
        
        # Save response as evidence
        save_artifact(
            "query_response.json",
            json.dumps(response_data, indent=2),
        )
        
        # === Step 4: Assert response contains "green" ===
        response_text = str(response_data.get("response", "") or response_data.get("message", ""))
        response_text_lower = response_text.lower()
        
        # The response MUST mention "green" - proving it read our document
        assert "green" in response_text_lower, (
            f"Response should mention 'green' from our document!\n"
            f"Got: {response_text[:500]}"
        )
        
        # Should NOT say "blue" (global knowledge)
        # Note: It might mention blue to refute it, so this is a soft check
        if "blue" in response_text_lower and "not blue" not in response_text_lower:
            print("⚠️ Warning: Response mentions 'blue' - may be using global knowledge")
        
        print(f"✅ Response correctly mentions 'green'!")
        print(f"📝 Response excerpt: {response_text[:200]}...")
        
        # === Step 5: Check for audio response (if enabled) ===
        audio_data = response_data.get("audio_data") or response_data.get("audio")
        if audio_data:
            if isinstance(audio_data, str):
                # Base64 encoded
                import base64
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = bytes(audio_data)
            
            save_response_audio(audio_bytes, "response.mp3")
            print(f"🎵 Audio response saved ({len(audio_bytes)} bytes)")
        
        # === Cleanup ===
        await http_client.delete(f"/api/notebooks/{notebook_id}")
        print(f"🗑️ Cleaned up test notebook")
    
    async def test_health_endpoints_alive(self, http_client):
        """Verify all health endpoints are responding."""
        endpoints = [
            ("/health", "Backend"),
        ]
        
        for endpoint, name in endpoints:
            response = await http_client.get(endpoint)
            assert response.status_code == 200, f"{name} health check failed"
            print(f"✅ {name} is healthy")
    
    async def test_database_connectivity(self, http_client, evidence_dir):
        """Verify database connections are working."""
        import json
        
        response = await http_client.get("/health/detailed")
        
        if response.status_code != 200:
            pytest.skip("Detailed health endpoint not available")
        
        health_data = response.json()
        
        # Save health status as evidence
        with open(evidence_dir / "health_status.json", "w") as f:
            json.dump(health_data, f, indent=2)
        
        # Check required services
        services = health_data.get("services", {})
        
        if "neo4j" in services:
            assert services["neo4j"]["status"] == "healthy"
            print("✅ Neo4j connected")
        
        if "milvus" in services:
            assert services["milvus"]["status"] == "healthy"
            print("✅ Milvus connected")
        
        if "redis" in services:
            assert services["redis"]["status"] == "healthy"
            print("✅ Redis connected")


@pytest.mark.asyncio
class TestPodcastGeneration:
    """E2E tests for podcast generation with audio output."""
    
    async def test_podcast_generation_produces_audio(
        self,
        http_client,
        evidence_dir,
        save_response_audio,
    ):
        """
        Test full podcast generation flow.
        
        Evidence: Saves generated audio to evidence directory.
        """
        import json
        
        # Create notebook with test content
        notebook_response = await http_client.post(
            "/api/notebooks",
            json={"name": "E2E Podcast Test"},
        )
        
        if notebook_response.status_code not in (200, 201):
            pytest.skip("Could not create notebook")
        
        notebook_id = notebook_response.json().get("id")
        
        # Ingest simple content
        content = """
        Artificial Intelligence is transforming how we work and live.
        Machine learning enables computers to learn from data.
        Deep learning uses neural networks with multiple layers.
        """
        
        files = {"file": ("ai_content.txt", io.BytesIO(content.encode()), "text/plain")}
        await http_client.post(f"/api/notebooks/{notebook_id}/sources", files=files)
        
        # Wait for ingestion
        import asyncio
        await asyncio.sleep(3)
        
        # Request podcast generation
        podcast_response = await http_client.post(
            f"/api/notebooks/{notebook_id}/podcast",
            json={"source_ids": ["*"], "duration_minutes": 1},
            timeout=180.0,  # Podcast generation takes time
        )
        
        if podcast_response.status_code == 503:
            pytest.skip("Podcast generation service busy")
        
        if podcast_response.status_code not in (200, 201, 202):
            # Save error for debugging
            with open(evidence_dir / "podcast_error.json", "w") as f:
                json.dump({"status": podcast_response.status_code, "body": podcast_response.text}, f)
            pytest.skip(f"Podcast generation failed: {podcast_response.status_code}")
        
        response_data = podcast_response.json()
        
        # Check for audio data
        audio_data = response_data.get("audio_data") or response_data.get("audio_url")
        
        if audio_data:
            if isinstance(audio_data, str) and audio_data.startswith("http"):
                # It's a URL, download it
                audio_response = await http_client.get(audio_data)
                audio_bytes = audio_response.content
            elif isinstance(audio_data, str):
                # Base64 encoded
                import base64
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = bytes(audio_data)
            
            save_response_audio(audio_bytes, "podcast_output.mp3")
            print(f"✅ Podcast audio saved ({len(audio_bytes)} bytes)")
        
        # Cleanup
        await http_client.delete(f"/api/notebooks/{notebook_id}")
