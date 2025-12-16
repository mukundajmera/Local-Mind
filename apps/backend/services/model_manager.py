"""
Model Manager Service
=====================
Singleton service for safe LLM model lifecycle management with VRAM safety.

This service ensures:
1. Only one model is loaded at a time (Singleton pattern)
2. Safe model unloading with proper memory cleanup
3. Thread-safe model switching with locking
"""

import gc
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton Model Manager with VRAM-safe operations.
    
    Usage:
        manager = ModelManager.get_instance()
        await manager.switch_model("llama3.2:3b")
        model = manager.get_current_model()
    """
    
    _instance: Optional['ModelManager'] = None
    _initialized: bool = False
    _lock: asyncio.Lock = asyncio.Lock()
    
    def __init__(self):
        """Private constructor. Use get_instance() instead."""
        if ModelManager._initialized:
            return
        
        self.current_model_name: Optional[str] = None
        self.current_model: Optional[Any] = None
        self.model_metadata: Dict[str, Any] = {}
        self.load_timestamp: Optional[datetime] = None
        
        # Instance-level lock for model operations
        self._operation_lock = asyncio.Lock()
        
        logger.info("ModelManager initialized")
        ModelManager._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'ModelManager':
        """Get singleton instance of ModelManager."""
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance
    
    async def load_model(self, model_name: str, **kwargs) -> Any:
        """
        Load a model with memory checks.
        
        Args:
            model_name: Name of the model to load (e.g., "llama3.2:3b")
            **kwargs: Additional model configuration
            
        Returns:
            Loaded model instance
            
        Raises:
            RuntimeError: If model loading fails
        """
        async with self._operation_lock:
            try:
                logger.info(f"Loading model: {model_name}")
                
                # Import here to avoid circular dependencies
                from services.llm_factory import LLMService
                
                # Create new LLM service instance
                # Note: This is a simplified version. In production, you'd want to
                # integrate with the existing LLMService more carefully
                llm_service = LLMService()
                await llm_service.__aenter__()
                
                self.current_model = llm_service
                self.current_model_name = model_name
                self.load_timestamp = datetime.utcnow()
                self.model_metadata = {
                    "model_name": model_name,
                    "loaded_at": self.load_timestamp.isoformat(),
                    **kwargs
                }
                
                logger.info(f"Model loaded successfully: {model_name}")
                return self.current_model
                
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}", exc_info=True)
                raise RuntimeError(f"Model loading failed: {str(e)}")
    
    async def unload_model(self) -> None:
        """
        Safely unload the current model with proper VRAM cleanup.
        
        This implements the VRAM-safe sequence:
        1. Delete model reference
        2. Force garbage collection
        3. Clear GPU cache (CUDA or MPS)
        """
        async with self._operation_lock:
            if self.current_model is None:
                logger.debug("No model to unload")
                return
            
            try:
                logger.info(f"Unloading model: {self.current_model_name}")
                
                # Step 1: Close the LLM service if it has cleanup
                if hasattr(self.current_model, '__aexit__'):
                    try:
                        await self.current_model.__aexit__(None, None, None)
                    except Exception as e:
                        logger.warning(f"Error during model cleanup: {e}")
                
                # Step 2: Delete model reference
                model_name = self.current_model_name
                del self.current_model
                self.current_model = None
                self.current_model_name = None
                self.model_metadata = {}
                self.load_timestamp = None
                
                # Step 3: Force garbage collection
                gc.collect()
                
                # Step 4: Clear GPU cache based on available backend
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        logger.debug("CUDA cache cleared")
                    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                        torch.mps.empty_cache()
                        logger.debug("MPS cache cleared")
                except ImportError:
                    logger.debug("PyTorch not available, skipping GPU cache clear")
                except Exception as e:
                    logger.warning(f"Failed to clear GPU cache: {e}")
                
                logger.info(f"Model unloaded successfully: {model_name}")
                
            except Exception as e:
                logger.error(f"Error during model unload: {e}", exc_info=True)
                # Continue anyway to ensure cleanup
    
    async def switch_model(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """
        Atomically switch to a different model with locking.
        
        This ensures thread-safety when multiple requests attempt to switch models.
        
        Args:
            model_name: Name of the model to switch to
            **kwargs: Additional model configuration
            
        Returns:
            Dict with switch status and model info
        """
        async with self._operation_lock:
            previous_model = self.current_model_name
            
            try:
                logger.info(f"Switching model from {previous_model} to {model_name}")
                
                # Unload current model
                await self.unload_model()
                
                # Load new model
                await self.load_model(model_name, **kwargs)
                
                return {
                    "status": "success",
                    "previous_model": previous_model,
                    "current_model": model_name,
                    "switched_at": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Model switch failed: {e}", exc_info=True)
                
                # Attempt to reload previous model if switch failed
                if previous_model:
                    try:
                        logger.info(f"Attempting to reload previous model: {previous_model}")
                        await self.load_model(previous_model)
                    except Exception as reload_error:
                        logger.error(f"Failed to reload previous model: {reload_error}")
                
                raise RuntimeError(f"Model switch failed: {str(e)}")
    
    def get_current_model(self) -> Optional[Any]:
        """
        Get the currently loaded model.
        
        Returns:
            Current model instance or None if no model is loaded
        """
        return self.current_model
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the currently loaded model.
        
        Returns:
            Dict with model metadata
        """
        if self.current_model is None:
            return {
                "status": "no_model_loaded",
                "current_model": None
            }
        
        return {
            "status": "loaded",
            "current_model": self.current_model_name,
            "metadata": self.model_metadata,
            "loaded_at": self.load_timestamp.isoformat() if self.load_timestamp else None
        }
    
    async def get_available_models(self) -> list[str]:
        """
        Get list of available models.
        
        This is a placeholder - in production, you'd query Ollama or your model registry.
        
        Returns:
            List of available model names
        """
        # TODO: Query Ollama API for available models
        # For now, return common models
        return [
            "llama3.2:3b",
            "llama3.2:1b",
            "mistral:7b",
            "phi3:mini",
            "qwen2.5:7b"
        ]
