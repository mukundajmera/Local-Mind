"""
Sovereign Cognitive Engine - Configuration
===========================================
Environment-based settings using pydantic-settings.
"""

from functools import lru_cache
from typing import Optional
import sys

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ==========================================================================
    # Neo4j Configuration
    # ==========================================================================
    neo4j_uri: str = Field(
        default="bolt://cognitive-brain:7687",
        description="Neo4j Bolt URI"
    )
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(..., description="Neo4j password (required)")
    
    # ==========================================================================
    # Milvus Configuration
    # ==========================================================================
    milvus_host: str = Field(default="memory-bank")
    milvus_port: int = Field(default=19530)
    milvus_collection: str = Field(
        default="sce_chunks",
        description="Default collection name for text chunks"
    )
    
    # ==========================================================================
    # Redis Configuration
    # ==========================================================================
    redis_url: str = Field(default="redis://broker:6379/0")
    
    # ==========================================================================
    # Embedding Configuration
    # ==========================================================================
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace model ID for embeddings"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Vector dimension (must match model output)"
    )
    
    # ==========================================================================
    # Chunking Configuration
    # ==========================================================================
    chunk_size_tokens: int = Field(default=500, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=200)
    
    # ==========================================================================
    # LLM Configuration (for entity extraction)
    # ==========================================================================
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider: 'ollama', 'openai', 'anthropic'"
    )
    llm_model: str = Field(
        default="llama3.2",
        description="Model name for entity extraction"
    )
    llm_base_url: Optional[str] = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama or compatible API"
    )
    
    # ==========================================================================
    # Runtime Configuration
    # ==========================================================================
    environment: str = Field(default="production")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)
    
    @property
    def milvus_uri(self) -> str:
        """Construct Milvus URI from host and port."""
        return f"http://{self.milvus_host}:{self.milvus_port}"
    
    @field_validator("neo4j_password")
    @classmethod
    def validate_neo4j_password(cls, v: str) -> str:
        """Validate Neo4j password is not empty or default."""
        import logging
        
        if not v or v.strip() == "":
            raise ValueError("NEO4J_PASSWORD must not be empty")
        
        # Warn about weak passwords (logging not yet configured during Settings init)
        # Use standard library logging which will be captured by structlog later
        if v in ["neo4j", "password", "changeme", "localmind2024", "CHANGE_ME_IN_PRODUCTION"]:
            logger = logging.getLogger("config")
            logger.warning(
                "Using a default/weak Neo4j password. Set a strong password in production!",
                extra={"password_pattern": "weak"}
            )
            # Also print to stderr during startup for visibility
            print(
                "⚠️  WARNING: Using a default/weak Neo4j password. "
                "Set a strong password in production!",
                file=sys.stderr
            )
        return v
    
    @field_validator("embedding_dimension")
    @classmethod
    def validate_embedding_dimension(cls, v: int) -> int:
        """Validate embedding dimension is reasonable."""
        if v < 1 or v > 4096:
            raise ValueError("embedding_dimension must be between 1 and 4096")
        return v
    
    @field_validator("chunk_size_tokens")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        """Validate chunk size is reasonable."""
        if v < 100:
            raise ValueError("chunk_size_tokens must be at least 100")
        if v > 8000:
            raise ValueError("chunk_size_tokens should not exceed 8000 (context limits)")
        return v
    
    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        """Validate chunk overlap is less than chunk size."""
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                f"chunk_overlap_tokens ({self.chunk_overlap_tokens}) must be less than "
                f"chunk_size_tokens ({self.chunk_size_tokens})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to avoid re-parsing environment on every call.
    """
    return Settings()
