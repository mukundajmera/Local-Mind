"""
Sovereign Cognitive Engine - LLM Gateway
=========================================
Config-driven gateway for LLM providers (OpenAI, vLLM, etc.)
using the Adapter pattern and Factory pattern.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Tuple
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import httpx
from pydantic import BaseModel

from config import get_settings, Settings
# We can import logging from existing config or standard logging
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class LLMServiceError(Exception):
    pass

class LLMBusyError(LLMServiceError):
    pass

class LLMProvider(ABC):
    """Abstract Base Class for LLM Providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> Tuple[str, dict]:
        """
        Generate text from the LLM.
        Returns: (generated_text, usage_stats)
        """
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        pass

class GenericOpenAIProvider(LLMProvider):
    """
    Adapter for OpenAI-compatible APIs (vLLM, Ollama, OpenAI).
    """
    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url
        self._api_key = api_key
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(120.0, connect=10.0)
        )

    @property
    def base_url(self) -> str:
        return str(self.client.base_url)

    async def close(self):
        await self.client.aclose()

    @retry(
        retry=retry_if_exception_type((LLMBusyError, httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, **kwargs) -> Tuple[str, dict]:
        system_prompt = kwargs.get("system_prompt")
        max_tokens = kwargs.get("max_tokens", 2048)
        temperature = kwargs.get("temperature", 0.7)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }

        if kwargs.get("json_mode"):
             payload["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.post("/chat/completions", json=payload)
            
            if response.status_code == 503:
                raise LLMBusyError("Server is busy")
            
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return content, usage

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise LLMBusyError("Server is busy") from e
            logger.error(f"LLM request failed: {e}")
            raise LLMServiceError(f"Request failed: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM connection error: {e}")
            raise LLMServiceError(f"Connection error: {e}") from e

def get_llm_client(settings: Optional[Settings] = None) -> LLMProvider:
    """Factory to create the configured LLM client."""
    if not settings:
        settings = get_settings()
    
    # We could have a switch here for different providers if their APIs differ significantly
    # beyond base_url (e.g. Anthropic). For now, we use a GenericOpenAIProvider
    # as mostly everything (Proprietary & Open Source) supports OpenAI API format.
    
    return GenericOpenAIProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model
    )
