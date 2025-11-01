"""
Unified Analytics API Endpoints

This module contains all the API endpoints for the unified analytics system,
organized by extension type for clean separation of concerns.
"""

from .apollo_api import router as apollo_router

__all__ = [
    "apollo_router",
]
