"""
System Management Router
========================
API endpoints for system-level operations including model management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ModelSwitchRequest(BaseModel):
    """Request schema for switching models."""
    model_name: str = Field(..., description="Name of the model to switch to")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional model configuration")


class ModelSwitchResponse(BaseModel):
    """Response schema for model switch operations."""
    status: str
    previous_model: Optional[str]
    current_model: str
    switched_at: str


class ModelInfoResponse(BaseModel):
    """Response schema for current model information."""
    status: str
    current_model: Optional[str]
    metadata: Optional[Dict[str, Any]] = None
    loaded_at: Optional[str] = None


@router.post("/models/switch", response_model=ModelSwitchResponse)
async def switch_model(request: ModelSwitchRequest):
    """
    Switch the active LLM model.
    
    This endpoint safely unloads the current model and loads the requested model.
    Uses locking to prevent concurrent switches.
    
    **Warning**: In-flight requests using the old model may fail during the switch.
    """
    try:
        from services.model_manager import ModelManager
        
        manager = ModelManager.get_instance()
        
        # Perform the switch
        result = await manager.switch_model(
            request.model_name,
            **(request.config or {})
        )
        
        logger.info(f"Model switched: {result['previous_model']} -> {result['current_model']}")
        
        return ModelSwitchResponse(**result)
        
    except Exception as e:
        logger.error(f"Model switch failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch model: {str(e)}"
        )


@router.get("/models/current", response_model=ModelInfoResponse)
async def get_current_model():
    """
    Get information about the currently loaded model.
    
    Returns model name, metadata, and load timestamp.
    """
    try:
        from services.model_manager import ModelManager
        
        manager = ModelManager.get_instance()
        info = manager.get_model_info()
        
        return ModelInfoResponse(**info)
        
    except Exception as e:
        logger.error(f"Failed to get model info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model information: {str(e)}"
        )


@router.get("/models/available", response_model=List[str])
async def get_available_models():
    """
    Get list of available models.
    
    Returns model names that can be loaded via the switch endpoint.
    """
    try:
        from services.model_manager import ModelManager
        
        manager = ModelManager.get_instance()
        models = await manager.get_available_models()
        
        return models
        
    except Exception as e:
        logger.error(f"Failed to get available models: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available models: {str(e)}"
        )


@router.post("/models/unload")
async def unload_model():
    """
    Unload the current model to free VRAM.
    
    This is useful for freeing up GPU memory when the model is not needed.
    """
    try:
        from services.model_manager import ModelManager
        
        manager = ModelManager.get_instance()
        await manager.unload_model()
        
        logger.info("Model unloaded successfully")
        
        return {
            "status": "success",
            "message": "Model unloaded successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to unload model: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unload model: {str(e)}"
        )
