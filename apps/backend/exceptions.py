"""
Sovereign Cognitive Engine - Custom Exceptions
===============================================
Centralized exception hierarchy for structured error handling.
"""

from typing import Optional, Dict, Any


class LocalMindBaseException(Exception):
    """Base exception for all Local Mind errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context,
        }
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result


# =============================================================================
# Database Connection Errors
# =============================================================================

class DatabaseConnectionError(LocalMindBaseException):
    """Base class for database connection failures."""
    pass


class Neo4jConnectionError(DatabaseConnectionError):
    """Neo4j connection or query failure."""
    
    def __init__(
        self,
        message: str = "Failed to connect to Neo4j",
        uri: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {"uri": uri} if uri else {}
        super().__init__(message, context, original_error)


class MilvusConnectionError(DatabaseConnectionError):
    """Milvus connection or operation failure."""
    
    def __init__(
        self,
        message: str = "Failed to connect to Milvus",
        uri: Optional[str] = None,
        collection: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if uri:
            context["uri"] = uri
        if collection:
            context["collection"] = collection
        super().__init__(message, context, original_error)


class RedisConnectionError(DatabaseConnectionError):
    """Redis connection failure."""
    
    def __init__(
        self,
        message: str = "Failed to connect to Redis",
        uri: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {"uri": uri} if uri else {}
        super().__init__(message, context, original_error)


# =============================================================================
# Service Errors
# =============================================================================

class IngestionError(LocalMindBaseException):
    """Document ingestion pipeline failure."""
    
    def __init__(
        self,
        message: str,
        doc_id: Optional[str] = None,
        filename: Optional[str] = None,
        stage: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if doc_id:
            context["doc_id"] = doc_id
        if filename:
            context["filename"] = filename
        if stage:
            context["stage"] = stage
        super().__init__(message, context, original_error)


class LLMServiceError(LocalMindBaseException):
    """LLM service failure (extraction, chat, etc.)."""
    
    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        chunk_id: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if model:
            context["model"] = model
        if chunk_id:
            context["chunk_id"] = chunk_id
        super().__init__(message, context, original_error)


class SearchError(LocalMindBaseException):
    """Search/retrieval failure."""
    
    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        search_type: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if query:
            context["query"] = query[:100]  # Truncate long queries
        if search_type:
            context["search_type"] = search_type
        super().__init__(message, context, original_error)


# =============================================================================
# Validation Errors
# =============================================================================

class ValidationError(LocalMindBaseException):
    """Input validation failure."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)[:100]  # Truncate
        super().__init__(message, context)
