"""
Sovereign Cognitive Engine - Configuration
===========================================
Environment-based settings using pydantic-settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
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


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to avoid re-parsing environment on every call.
    """
    return Settings()
