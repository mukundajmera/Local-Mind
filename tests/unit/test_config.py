"""
Unit Tests - Configuration Validation
======================================
Test configuration validation and error handling.
"""

import pytest
import os
from pydantic import ValidationError


class TestConfigValidation:
    """Test configuration validation rules."""
    
    @pytest.mark.unit
    def test_valid_config_loads(self, monkeypatch):
        """Valid configuration should load successfully."""
        # Set valid environment variables
        monkeypatch.setenv("NEO4J_PASSWORD", "secure_password_123")
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("MILVUS_HOST", "localhost")
        monkeypatch.setenv("MILVUS_PORT", "19530")
        
        from apps.backend.config import Settings
        
        settings = Settings()
        assert settings.neo4j_password == "secure_password_123"
    
    @pytest.mark.unit
    def test_missing_neo4j_password_fails(self, monkeypatch):
        """Missing NEO4J_PASSWORD should raise ValidationError."""
        # Clear NEO4J_PASSWORD
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        
        from apps.backend.config import Settings
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        errors = exc_info.value.errors()
        assert any("neo4j_password" in str(e.get("loc", "")) for e in errors)
    
    @pytest.mark.unit
    def test_empty_neo4j_password_fails(self, monkeypatch):
        """Empty NEO4J_PASSWORD should raise ValidationError."""
        monkeypatch.setenv("NEO4J_PASSWORD", "")
        
        from apps.backend.config import Settings
        
        with pytest.raises(ValidationError):
            Settings()
    
    @pytest.mark.unit
    def test_embedding_dimension_validation(self, monkeypatch):
        """Embedding dimension must be in valid range."""
        monkeypatch.setenv("NEO4J_PASSWORD", "test123")
        
        from apps.backend.config import Settings
        
        # Too small
        monkeypatch.setenv("EMBEDDING_DIMENSION", "0")
        with pytest.raises(ValidationError):
            Settings()
        
        # Too large
        monkeypatch.setenv("EMBEDDING_DIMENSION", "5000")
        with pytest.raises(ValidationError):
            Settings()
        
        # Valid
        monkeypatch.setenv("EMBEDDING_DIMENSION", "384")
        settings = Settings()
        assert settings.embedding_dimension == 384
    
    @pytest.mark.unit
    def test_chunk_size_validation(self, monkeypatch):
        """Chunk size must be reasonable."""
        monkeypatch.setenv("NEO4J_PASSWORD", "test123")
        
        from apps.backend.config import Settings
        
        # Too small
        monkeypatch.setenv("CHUNK_SIZE_TOKENS", "50")
        with pytest.raises(ValidationError):
            Settings()
        
        # Too large
        monkeypatch.setenv("CHUNK_SIZE_TOKENS", "10000")
        with pytest.raises(ValidationError):
            Settings()
        
        # Valid
        monkeypatch.setenv("CHUNK_SIZE_TOKENS", "500")
        settings = Settings()
        assert settings.chunk_size_tokens == 500
    
    @pytest.mark.unit
    def test_chunk_overlap_less_than_size(self, monkeypatch):
        """Chunk overlap must be less than chunk size."""
        monkeypatch.setenv("NEO4J_PASSWORD", "test123")
        
        from apps.backend.config import Settings
        
        # Overlap >= size
        monkeypatch.setenv("CHUNK_SIZE_TOKENS", "500")
        monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "500")
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        assert "overlap" in str(exc_info.value).lower()
    
    @pytest.mark.unit
    def test_milvus_uri_construction(self, monkeypatch):
        """Milvus URI should be constructed correctly."""
        monkeypatch.setenv("NEO4J_PASSWORD", "test123")
        monkeypatch.setenv("MILVUS_HOST", "milvus.example.com")
        monkeypatch.setenv("MILVUS_PORT", "19530")
        
        from apps.backend.config import Settings
        
        settings = Settings()
        assert settings.milvus_uri == "http://milvus.example.com:19530"
    
    @pytest.mark.unit
    def test_default_values(self, monkeypatch):
        """Default values should be applied for optional settings."""
        monkeypatch.setenv("NEO4J_PASSWORD", "test123")
        
        from apps.backend.config import Settings
        
        settings = Settings()
        
        # Check defaults
        assert settings.environment == "production"
        assert settings.log_level == "INFO"
        assert settings.debug is False
        assert settings.chunk_size_tokens == 500
        assert settings.chunk_overlap_tokens == 50
