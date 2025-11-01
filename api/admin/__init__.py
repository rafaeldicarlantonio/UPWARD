"""
Admin API endpoints.
"""

from .roles import router as roles_router

__all__ = ["roles_router"]
