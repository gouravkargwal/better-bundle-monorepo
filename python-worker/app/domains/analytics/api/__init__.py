"""
Unified Analytics API Endpoints

This module contains all the API endpoints for the unified analytics system,
organized by extension type for clean separation of concerns.
"""

from .venus_api import router as venus_router
from .atlas_api import router as atlas_router
from .phoenix_api import router as phoenix_router
from .apollo_api import router as apollo_router
from .customer_identity_api import router as customer_identity_router

__all__ = [
    "venus_router",
    "atlas_router",
    "phoenix_router",
    "apollo_router",
    "customer_identity_router",
]
