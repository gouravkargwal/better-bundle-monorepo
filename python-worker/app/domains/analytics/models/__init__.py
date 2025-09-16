"""
Unified Analytics Models for BetterBundle

This module contains all the data models for the unified analytics system
that tracks user interactions across all extensions (Venus, Atlas, Phoenix, Apollo).
"""

from .session import (
    UserSession,
    SessionCreate,
    SessionUpdate,
    SessionQuery,
    SessionStatus,
)
from .interaction import UserInteraction, InteractionCreate, InteractionType
from .attribution import PurchaseAttribution, AttributionCreate, AttributionWeight
from .extension import ExtensionType, ExtensionContext

__all__ = [
    # Session models
    "UserSession",
    "SessionCreate",
    "SessionUpdate",
    "SessionQuery",
    "SessionStatus",
    # Interaction models
    "UserInteraction",
    "InteractionCreate",
    "InteractionType",
    # Attribution models
    "PurchaseAttribution",
    "AttributionCreate",
    "AttributionWeight",
    # Extension models
    "ExtensionType",
    "ExtensionContext",
]
