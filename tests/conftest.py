"""
Sovereign Cognitive Engine - Test Configuration
================================================
Pytest fixtures, markers, and evidence collection system.

Evidence Folder Structure:
    evidence/
    └── {test_run_id}/
        ├── cypher_audit.log      # Captured Cypher queries
        ├── response.mp3          # Audio from E2E tests
        ├── screenshots/          # UI screenshots (if any)
        └── artifacts/            # Other test artifacts
"""

import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add backend to path for imports
BACKEND_PATH = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(BACKEND_PATH))


# =============================================================================
# Test Run Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers and configure test run."""
    # Register markers
    config.addinivalue_line(
        "markers", "unit: Fast, no I/O, mocks only"
    )
    config.addinivalue_line(
        "markers", "integration: Mocks external APIs but uses real DB drivers"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests requiring live containers"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 5 seconds"
    )


def pytest_collection_modifyitems(config, items):
    """Skip E2E tests unless E2E_ACTIVE is set."""
    if not os.getenv("E2E_ACTIVE"):
        skip_e2e = pytest.mark.skip(
            reason="E2E_ACTIVE not set. Run with E2E_ACTIVE=1 for E2E tests."
        )
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


# =============================================================================
# Test Run ID & Evidence Directory
# =============================================================================

@pytest.fixture(scope="session")
def test_run_id() -> str:
    """
    Generate unique test run ID based on timestamp.
    Format: YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@pytest.fixture(scope="session")
def evidence_dir(test_run_id: str) -> Path:
    """
    Create evidence directory for this test run.
    All test artifacts will be stored here.
    """
    base_path = Path(__file__).parent.parent / "evidence" / test_run_id
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (base_path / "screenshots").mkdir(exist_ok=True)
    (base_path / "artifacts").mkdir(exist_ok=True)
    (base_path / "logs").mkdir(exist_ok=True)
    
    # Create run info file
    run_info = {
        "test_run_id": test_run_id,
        "started_at": datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": sys.platform,
    }
    
    with open(base_path / "run_info.json", "w") as f:
        json.dump(run_info, f, indent=2)
    
    print(f"\n📁 Evidence directory: {base_path}")
    
    return base_path


@pytest.fixture(scope="session")
def cypher_audit_log(evidence_dir: Path) -> Path:
    """Path to Cypher query audit log."""
    log_path = evidence_dir / "cypher_audit.log"
    
    # Initialize log file with header
    with open(log_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("Cypher Query Audit Log\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
    
    return log_path


# =============================================================================
# Cypher Query Capture
# =============================================================================

class CypherCapture:
    """Captures Cypher queries for audit logging."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.queries: list[dict] = []
    
    def capture(self, query: str, params: Optional[dict] = None, source: str = "unknown"):
        """Record a Cypher query."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "query": query.strip(),
            "params": params or {},
        }
        self.queries.append(entry)
        
        # Write to log file
        with open(self.log_path, "a") as f:
            f.write(f"[{entry['timestamp']}] Source: {source}\n")
            f.write(f"Query:\n{query.strip()}\n")
            if params:
                f.write(f"Params: {json.dumps(params, default=str, indent=2)}\n")
            f.write("-" * 40 + "\n\n")
    
    def get_all(self) -> list[dict]:
        return self.queries.copy()
    
    def clear(self):
        self.queries.clear()


@pytest.fixture
def cypher_capture(cypher_audit_log: Path) -> CypherCapture:
    """Fixture to capture Cypher queries during tests."""
    return CypherCapture(cypher_audit_log)


# =============================================================================
# Mock Settings
# =============================================================================

@pytest.fixture
def mock_settings():
    """Provide mock application settings for testing."""
    from config import Settings
    
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test_password_123",
        milvus_host="localhost",
        milvus_port=19530,
        milvus_collection="test_chunks",
        redis_url="redis://localhost:6379/0",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension=384,
        chunk_size_tokens=500,
        chunk_overlap_tokens=50,
        llm_model="test-model",
        llm_base_url="http://localhost:8000/v1",
    )


# =============================================================================
# Mock Database Clients
# =============================================================================

@pytest.fixture
def mock_neo4j_driver(cypher_capture: CypherCapture):
    """
    Create mock Neo4j async driver that captures Cypher queries.
    """
    driver = AsyncMock()
    session = AsyncMock()
    
    # Mock session context manager
    driver.session.return_value.__aenter__.return_value = session
    driver.session.return_value.__aexit__.return_value = None
    
    # Capture Cypher queries
    original_run = session.run
    
    async def capturing_run(query: str, **params):
        cypher_capture.capture(query, params, source="neo4j_session")
        result = AsyncMock()
        result.single.return_value = None
        result.__aiter__ = lambda self: iter([])
        return result
    
    session.run = capturing_run
    
    return driver, session, cypher_capture


@pytest.fixture
def mock_milvus_client():
    """Create mock Milvus client."""
    client = MagicMock()
    client.has_collection.return_value = True
    client.search.return_value = [[]]
    client.upsert.return_value = {"insert_count": 0}
    client.create_collection.return_value = None
    return client


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_text_chunk():
    """Sample text chunk for testing."""
    return """
    Albert Einstein developed the theory of relativity in 1905.
    This groundbreaking work revolutionized our understanding of physics.
    Einstein worked at the Swiss Patent Office while developing his theories.
    The theory includes both special and general relativity.
    """


@pytest.fixture
def sample_extraction_result():
    """Sample extraction result with known entities and relationships."""
    from schemas import ExtractionResult, GraphEntity, GraphRelationship
    
    return ExtractionResult(
        entities=[
            GraphEntity(
                name="Albert Einstein",
                type="PERSON",
                description="Physicist who developed relativity",
                chunk_ids=["chunk-001"],
            ),
            GraphEntity(
                name="Theory of Relativity",
                type="THEORY",
                description="Revolutionary physics theory from 1905",
                chunk_ids=["chunk-001"],
            ),
            GraphEntity(
                name="Swiss Patent Office",
                type="ORGANIZATION",
                description="Where Einstein worked",
                chunk_ids=["chunk-001"],
            ),
        ],
        relationships=[
            GraphRelationship(
                source="Albert Einstein",
                target="Theory of Relativity",
                type="DEVELOPED",
                weight=1.0,
                chunk_ids=["chunk-001"],
            ),
            GraphRelationship(
                source="Albert Einstein",
                target="Swiss Patent Office",
                type="WORKED_AT",
                weight=0.9,
                chunk_ids=["chunk-001"],
            ),
        ],
    )


@pytest.fixture
def sample_search_results():
    """Sample search results for RRF testing."""
    from schemas import SearchResult
    
    vector_results = [
        SearchResult(chunk_id="chunk-A", text="Vector result 1", score=0.95, source="vector"),
        SearchResult(chunk_id="chunk-B", text="Vector result 2", score=0.85, source="vector"),
        SearchResult(chunk_id="chunk-C", text="Vector result 3", score=0.75, source="vector"),
        SearchResult(chunk_id="chunk-D", text="Vector result 4", score=0.65, source="vector"),
    ]
    
    graph_results = [
        SearchResult(chunk_id="chunk-B", text="Graph result 1", score=5.0, source="graph"),
        SearchResult(chunk_id="chunk-E", text="Graph result 2", score=3.0, source="graph"),
        SearchResult(chunk_id="chunk-A", text="Graph result 3", score=2.0, source="graph"),
    ]
    
    return vector_results, graph_results


# =============================================================================
# Mock LLM Service
# =============================================================================

@pytest.fixture
def mock_llm_service(sample_extraction_result):
    """Create mock LLM service that returns known extraction results."""
    service = AsyncMock()
    service.extract_entities.return_value = sample_extraction_result
    service.generate.return_value = ("Test response", {"tokens": 10})
    return service


# =============================================================================
# HTTP Test Client
# =============================================================================

@pytest.fixture
def api_base_url() -> str:
    """Base URL for API tests."""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest_asyncio.fixture
async def http_client(api_base_url: str):
    """Async HTTP client for API testing."""
    import httpx
    
    async with httpx.AsyncClient(
        base_url=api_base_url,
        timeout=httpx.Timeout(60.0, connect=10.0),
    ) as client:
        yield client


# =============================================================================
# Evidence Helpers
# =============================================================================

@pytest.fixture
def save_artifact(evidence_dir: Path):
    """Helper to save test artifacts to evidence directory."""
    
    def _save(filename: str, content: bytes | str, subdir: str = "artifacts"):
        artifact_dir = evidence_dir / subdir
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = artifact_dir / filename
        
        if isinstance(content, bytes):
            with open(file_path, "wb") as f:
                f.write(content)
        else:
            with open(file_path, "w") as f:
                f.write(content)
        
        print(f"📎 Saved artifact: {file_path}")
        return file_path
    
    return _save


@pytest.fixture
def save_response_audio(evidence_dir: Path):
    """Helper to save audio response from E2E tests."""
    
    def _save(audio_data: bytes, filename: str = "response.mp3"):
        file_path = evidence_dir / filename
        with open(file_path, "wb") as f:
            f.write(audio_data)
        print(f"🎵 Saved audio: {file_path}")
        return file_path
    
    return _save


# =============================================================================
# Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
