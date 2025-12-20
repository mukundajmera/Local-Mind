import os
import pytest
from unittest.mock import patch

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "LLM_BASE_URL": "http://localhost:9999/v1",
        "LLM_API_KEY": "sk-fake-key-123",
        "LLM_PROVIDER": "openai"
    }):
        yield

def test_llm_gateway_config(mock_env):
    """
    Verify that get_llm_client returns a client configured with
    the environment variables, specifically the base_url.
    """
    try:
        from apps.backend.services.llm import get_llm_client
    except ImportError:
        pytest.fail("Module apps.backend.services.llm not found. Task logic not implemented yet.")

    # Action
    provider = get_llm_client()
    
    # Assert
    # We check if the provider utilizes the correct base_url from environment
    if hasattr(provider, "base_url"):
        # httpx.URL string representation might include trailing slash
        assert str(provider.base_url).rstrip("/") == "http://localhost:9999/v1"
    elif hasattr(provider, "client") and hasattr(provider.client, "base_url"):
        assert str(provider.client.base_url).rstrip("/") == "http://localhost:9999/v1"
    else:
        pytest.fail(f"Provider {provider} does not expose base_url or client.base_url")
