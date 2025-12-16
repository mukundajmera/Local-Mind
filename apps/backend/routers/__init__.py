"""
API Routers
===========
FastAPI routers for Local Mind backend.
"""

from .system import router as system_router
from .projects import router as projects_router

__all__ = ["system_router", "projects_router"]
