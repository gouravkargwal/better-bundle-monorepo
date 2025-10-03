"""
User Interaction Models for Unified Analytics

Handles tracking of user interactions across all extensions with proper
categorization and metadata.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum

from .extension import ExtensionType


class InteractionType(str, Enum):
    """Types of user interactions"""

    # Standard Shopify events (tracked by Atlas)
    PAGE_VIEWED = "page_viewed"
    PRODUCT_VIEWED = "product_viewed"
    PRODUCT_ADDED_TO_CART = "product_added_to_cart"
    PRODUCT_REMOVED_FROM_CART = "product_removed_from_cart"
    CART_VIEWED = "cart_viewed"
    COLLECTION_VIEWED = "collection_viewed"
    SEARCH_SUBMITTED = "search_submitted"
    CHECKOUT_STARTED = "checkout_started"
    CHECKOUT_COMPLETED = "checkout_completed"
    CUSTOMER_LINKED = "customer_linked"

    # Custom recommendation events (tracked by Phoenix, Venus, Apollo)
    RECOMMENDATION_VIEWED = "recommendation_viewed"
    RECOMMENDATION_CLICKED = "recommendation_clicked"
    RECOMMENDATION_ADD_TO_CART = "recommendation_add_to_cart"


class UserInteraction(BaseModel):
    """User interaction model for unified analytics tracking"""

    id: str = Field(..., description="Unique interaction identifier")
    session_id: str = Field(..., description="Session identifier")
    extension_type: ExtensionType = Field(
        ..., description="Extension that generated this interaction"
    )
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    interaction_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Interaction timestamp"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class InteractionCreate(BaseModel):
    """Model for creating a new user interaction"""

    session_id: str = Field(..., description="Session identifier")
    extension_type: ExtensionType = Field(..., description="Extension type")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    interaction_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )


class InteractionQuery(BaseModel):
    """Model for querying user interactions"""

    session_id: Optional[str] = Field(None, description="Filter by session identifier")
    customer_id: Optional[str] = Field(
        None, description="Filter by customer identifier"
    )
    shop_id: Optional[str] = Field(None, description="Filter by shop identifier")
    extension_type: Optional[ExtensionType] = Field(
        None, description="Filter by extension type"
    )
    interaction_type: Optional[InteractionType] = Field(
        None, description="Filter by interaction type"
    )
    product_id: Optional[str] = Field(None, description="Filter by product identifier")
    created_after: Optional[datetime] = Field(
        None, description="Filter interactions after this time"
    )
    created_before: Optional[datetime] = Field(
        None, description="Filter interactions before this time"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
