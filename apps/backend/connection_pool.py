"""
Sovereign Cognitive Engine - Connection Pooling
================================================
Centralized connection pool management for database clients (Milvus only).
"""

from typing import Optional
from pymilvus import MilvusClient
try:
    from .config import Settings, get_settings
    from .logging_config import get_logger
    from .circuit_breaker import CircuitBreaker
except ImportError:
    # Fallback for direct script execution
    from config import Settings, get_settings
    from logging_config import get_logger
    from circuit_breaker import CircuitBreaker
import asyncio

logger = get_logger(__name__)


class ConnectionPool:
    """
    Singleton connection pool for database clients.
    
    Manages Milvus connections with proper lifecycle management.
    
    Example:
        ```python
        pool = ConnectionPool.get_instance()
        await pool.initialize()
        
        # Use connections
        milvus_client = await pool.get_milvus_client()
        
        # Cleanup on shutdown
        await pool.close()
        ```
    """
    
    _instance: Optional["ConnectionPool"] = None
    _lock = asyncio.Lock()
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize pool (use get_instance() instead)."""
        if ConnectionPool._instance is not None:
            raise RuntimeError("Use ConnectionPool.get_instance() instead of direct instantiation")
        
        self.settings = settings or get_settings()
        self._milvus_client: Optional[MilvusClient] = None
        self._initialized = False
        
        # Circuit breaker for Milvus
        self.milvus_breaker = CircuitBreaker(
            name="milvus",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
    
    @classmethod
    async def get_instance(cls, settings: Optional[Settings] = None) -> "ConnectionPool":
        """
        Get or create singleton instance.
        
        Thread-safe singleton pattern with async support.
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = ConnectionPool(settings)
                    await cls._instance.initialize()
        
        return cls._instance
    
    async def initialize(self):
        """Initialize all database connections."""
        if self._initialized:
            logger.warning("ConnectionPool already initialized")
            return
        
        logger.info("Initializing ConnectionPool")
        
        try:
            # Initialize Milvus client
            await self._init_milvus()
            
            self._initialized = True
            logger.info("ConnectionPool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ConnectionPool: {e}", exc_info=True)
            await self.close()
            raise
    
    async def _init_milvus(self):
        """Initialize Milvus client."""
        try:
            logger.info(f"Connecting to Milvus at {self.settings.milvus_uri}")
            
            # Note: MilvusClient is synchronous but thread-safe
            # We wrap it in executor for async compatibility
            loop = asyncio.get_event_loop()
            self._milvus_client = await loop.run_in_executor(
                None,
                lambda: MilvusClient(uri=self.settings.milvus_uri)
            )
            
            # Verify connection
            collections = await loop.run_in_executor(
                None,
                self._milvus_client.list_collections
            )
            logger.info(f"Milvus connection established ({len(collections)} collections)")
            
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    async def get_milvus_client(self) -> MilvusClient:
        """
        Get Milvus client instance.
        
        Returns:
            Milvus client
            
        Raises:
            RuntimeError: If pool not initialized
        """
        if not self._initialized or self._milvus_client is None:
            raise RuntimeError(
                "ConnectionPool not initialized. Use ConnectionPool.get_instance() to get initialized pool."
            )
        
        return self._milvus_client
    
    async def close(self):
        """Close all database connections."""
        logger.info("Closing ConnectionPool")
        
        if self._milvus_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._milvus_client.close)
                logger.info("Milvus client closed")
            except Exception as e:
                logger.error(f"Error closing Milvus client: {e}")
        
        self._milvus_client = None
        self._initialized = False
    
    async def health_check(self) -> dict:
        """
        Check health of all database connections.
        
        Returns:
            Dictionary with health status for each service
        """
        health = {
            "milvus": "unknown",
        }
        
        # Check Milvus
        if self._milvus_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._milvus_client.list_collections)
                health["milvus"] = "healthy"
            except Exception as e:
                logger.warning(f"Milvus health check failed: {e}")
                health["milvus"] = "unhealthy"
        
        return health
    
    @classmethod
    async def reset_instance(cls):
        """Reset singleton instance (primarily for testing)."""
        async with cls._lock:
            if cls._instance:
                await cls._instance.close()
                cls._instance = None
