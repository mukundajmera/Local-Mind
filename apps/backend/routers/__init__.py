"""
API Routers
===========
FastAPI routers for Local Mind backend.
"""

from .system import router as system_router
from .projects import router as projects_router
from .ingestion import router as ingestion_router

__all__ = ["system_router", "projects_router", "ingestion_router"]
