"""
Sovereign Cognitive Engine - LLM Factory
=========================================
Async client for vLLM-compatible inference servers with structured output support.
"""

import json
import time
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import Settings, get_settings
from schemas import ExtractionResult, GraphEntity, GraphRelationship

# Structured logging with loguru
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# Type variable for Pydantic model generics
T = TypeVar("T", bound=BaseModel)


# =============================================================================
# Custom Exceptions
# =============================================================================

class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMBusyError(LLMServiceError):
    """Raised when LLM server returns 503 (busy/overloaded)."""
    pass


class LLMValidationError(LLMServiceError):
    """Raised when LLM response fails Pydantic validation."""
    pass


# =============================================================================
# LLM Service Client
# =============================================================================

class LLMService:
    """
    Async client for vLLM-compatible OpenAI API servers.
    
    Features:
    - Structured output via JSON mode enforcement
    - Automatic retry with exponential backoff
    - Token usage and latency tracking
    
    Example:
        ```python
        async with LLMService() as llm:
            result = await llm.extract_entities("Albert Einstein developed...")
        ```
    """
    
    # Entity extraction system prompt
    EXTRACTION_SYSTEM_PROMPT = """You are a precise data extraction engine specialized in knowledge graph construction.

Your task: Extract ALL entities (people, concepts, organizations, locations, events) and their relationships from the given text.

CRITICAL RULES:
1. Entity names should be normalized (proper capitalization, no abbreviations)
2. Entity types must be one of: PERSON, CONCEPT, ORGANIZATION, LOCATION, EVENT, TECHNOLOGY, THEORY
3. Relationships should capture semantic connections with descriptive types like DEVELOPED, WORKS_AT, LOCATED_IN, RELATED_TO
4. Include the chunk_id in chunk_ids array for provenance tracking
5. Weight relationships by confidence (0.0-1.0)

Output MUST be valid JSON adhering to this exact schema:
{schema}

Return ONLY the JSON object, no markdown formatting or explanations."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        """
        Initialize LLM service.
        
        Args:
            base_url: vLLM server URL (default from settings)
            model: Model name to use
            settings: Application settings
        """
        self.settings = settings or get_settings()
        # Default to Ollama local endpoint if not specified
        self.base_url = base_url or self.settings.llm_base_url or "http://localhost:11434/v1"
        self.model = model or self.settings.llm_model
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Initialize async HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),  # Long timeout for generation
            headers={"Content-Type": "application/json"},
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client
    
    @retry(
        retry=retry_if_exception_type(LLMBusyError),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=1, max=30),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM busy, retrying in {retry_state.next_action.sleep}s "
            f"(attempt {retry_state.attempt_number}/5)"
        ),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> tuple[str, dict]:
        """
        Generate text completion from LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (lower = more deterministic)
            json_mode: Force JSON output format
            
        Returns:
            Tuple of (generated_text, usage_stats)
            
        Raises:
            LLMBusyError: Server overloaded (will retry)
            LLMServiceError: Other server errors
        """
        start_time = time.perf_counter()
        client = self._get_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        
        # Enable JSON mode if supported by vLLM
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}
        
        try:
            response = await client.post("/chat/completions", json=request_body)
            
            if response.status_code == 503:
                raise LLMBusyError("LLM server is busy")
            
            response.raise_for_status()
            data = response.json()
            
            # Extract response
            generated_text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                "LLM generation complete",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=round(latency_ms, 2),
                model=self.model,
            )
            
            return generated_text, usage
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                raise LLMBusyError("LLM server is busy") from e
            logger.error(f"LLM request failed: {e}")
            raise LLMServiceError(f"LLM request failed: {e}") from e
        except httpx.RequestError as e:
            logger.error(f"LLM connection error: {e}")
            raise LLMServiceError(f"LLM connection error: {e}") from e
    
    async def generate_structured(
        self,
        prompt: str,
        pydantic_model: Type[T],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> T:
        """
        Generate structured output validated against a Pydantic model.
        
        The JSON schema is injected into the system prompt to enforce output format.
        
        Args:
            prompt: User prompt with content to process
            pydantic_model: Pydantic model class for validation
            system_prompt: Base system prompt (schema will be appended)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Validated Pydantic model instance
            
        Raises:
            LLMValidationError: Response failed Pydantic validation
        """
        # Get JSON schema from Pydantic model
        schema = pydantic_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)
        
        # Build system prompt with embedded schema
        if system_prompt:
            full_system_prompt = system_prompt.format(schema=schema_str)
        else:
            full_system_prompt = (
                f"You are a data extraction engine. "
                f"Output MUST be valid JSON adhering to this schema:\n{schema_str}\n"
                f"Return ONLY the JSON object, no other text."
            )
        
        # Generate with JSON mode
        generated_text, _ = await self.generate(
            prompt=prompt,
            system_prompt=full_system_prompt,
            max_tokens=max_tokens,
            temperature=0.1,  # Low temperature for deterministic structure
            json_mode=True,
        )
        
        # Parse and validate JSON
        try:
            # Clean up response (remove markdown code blocks if present)
            clean_text = generated_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            # Parse JSON and validate with Pydantic
            parsed = json.loads(clean_text)
            return pydantic_model.model_validate(parsed)
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}\nResponse: {generated_text[:500]}")
            raise LLMValidationError(f"Invalid JSON from LLM: {e}") from e
        except Exception as e:
            logger.error(f"Pydantic validation failed: {e}")
            raise LLMValidationError(f"Schema validation failed: {e}") from e
    
    async def extract_entities(
        self,
        text_chunk: str,
        chunk_id: str,
    ) -> ExtractionResult:
        """
        Extract entities and relationships from a text chunk.
        
        This is the primary method used by IngestionPipeline.
        
        Args:
            text_chunk: Text content to analyze
            chunk_id: ID of the source chunk for provenance
            
        Returns:
            ExtractionResult containing entities and relationships
        """
        prompt = f"""Analyze the following text and extract all entities and their relationships.
Include chunk_id "{chunk_id}" in the chunk_ids array for each entity and relationship.

TEXT:
{text_chunk}

Extract entities and relationships following the schema exactly."""
        
        try:
            result = await self.generate_structured(
                prompt=prompt,
                pydantic_model=ExtractionResult,
                system_prompt=self.EXTRACTION_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            
            logger.info(
                "Entity extraction complete",
                chunk_id=chunk_id,
                entity_count=len(result.entities),
                relationship_count=len(result.relationships),
            )
            
            return result
            
        except LLMValidationError:
            # Return empty result on validation failure (pipeline handles gracefully)
            logger.warning(f"Extraction failed validation for chunk {chunk_id}, returning empty")
            return ExtractionResult(entities=[], relationships=[])
    
    async def chat(
        self,
        user_message: str,
        context: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """
        Simple chat completion for conversational use.
        
        Args:
            user_message: User's question or message
            context: Optional context from RAG retrieval
            history: Optional conversation history
            
        Returns:
            Assistant's response text
        """
        system_prompt = "You are a helpful AI assistant with access to a knowledge base."
        
        if context:
            system_prompt += f"\n\nUse the following context to answer:\n{context}"
        
        prompt = user_message
        if history:
            # Format history into prompt (simplified)
            history_text = "\n".join(
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in history[-5:]  # Last 5 messages
            )
            prompt = f"Conversation history:\n{history_text}\n\nUser: {user_message}"
        
        response, _ = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1024,
            temperature=0.7,
        )
        
        return response
