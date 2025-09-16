"""
User Interaction Models for Unified Analytics

Handles tracking of user interactions across all extensions with proper
categorization and metadata.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum

from .extension import ExtensionType, ExtensionContext


class InteractionType(str, Enum):
    """Types of user interactions"""

    # Behavioral interactions (Atlas)
    PAGE_VIEW = "page_view"
    PRODUCT_VIEW = "product_view"
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"
    SCROLL = "scroll"
    TIME_ON_PAGE = "time_on_page"

    # Recommendation interactions (Phoenix, Venus, Apollo)
    RECOMMENDATION_VIEW = "recommendation_view"
    RECOMMENDATION_CLICK = "recommendation_click"
    RECOMMENDATION_ADD_TO_CART = "recommendation_add_to_cart"
    RECOMMENDATION_PURCHASE = "recommendation_purchase"

    # Cart interactions (Phoenix)
    CART_VIEW = "cart_view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    CART_UPDATE = "cart_update"
    CART_ABANDON = "cart_abandon"

    # Customer account interactions (Venus)
    PROFILE_VIEW = "profile_view"
    ORDER_VIEW = "order_view"
    ORDER_STATUS_VIEW = "order_status_view"

    # Post-purchase interactions (Apollo)
    POST_PURCHASE_VIEW = "post_purchase_view"
    POST_PURCHASE_CLICK = "post_purchase_click"
    POST_PURCHASE_PURCHASE = "post_purchase_purchase"

    # Generic interactions
    CLICK = "click"
    HOVER = "hover"
    FOCUS = "focus"
    BLUR = "blur"


class UserInteraction(BaseModel):
    """User interaction model for unified analytics tracking"""

    id: str = Field(..., description="Unique interaction identifier")
    session_id: str = Field(..., description="Session identifier")
    extension_type: ExtensionType = Field(
        ..., description="Extension that generated this interaction"
    )
    context: ExtensionContext = Field(
        ..., description="Context where interaction occurred"
    )
    interaction_type: InteractionType = Field(..., description="Type of interaction")

    # User and session info
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    # Interaction details
    product_id: Optional[str] = Field(
        None, description="Product involved in interaction"
    )
    collection_id: Optional[str] = Field(
        None, description="Collection involved in interaction"
    )
    order_id: Optional[str] = Field(None, description="Order involved in interaction")

    # Recommendation specific
    recommendation_id: Optional[str] = Field(
        None, description="Recommendation identifier"
    )
    recommendation_position: Optional[int] = Field(
        None, description="Position of recommendation"
    )
    recommendation_algorithm: Optional[str] = Field(
        None, description="Algorithm used for recommendation"
    )

    # Interaction metadata
    value: Optional[float] = Field(None, description="Monetary value of interaction")
    quantity: Optional[int] = Field(None, description="Quantity involved")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Interaction timestamp"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class InteractionCreate(BaseModel):
    """Model for creating a new user interaction"""

    session_id: str = Field(..., description="Session identifier")
    extension_type: ExtensionType = Field(..., description="Extension type")
    context: ExtensionContext = Field(
        ..., description="Context where interaction occurred"
    )
    interaction_type: InteractionType = Field(..., description="Type of interaction")

    # User and session info
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")

    # Interaction details
    product_id: Optional[str] = Field(
        None, description="Product involved in interaction"
    )
    collection_id: Optional[str] = Field(
        None, description="Collection involved in interaction"
    )
    order_id: Optional[str] = Field(None, description="Order involved in interaction")

    # Recommendation specific
    recommendation_id: Optional[str] = Field(
        None, description="Recommendation identifier"
    )
    recommendation_position: Optional[int] = Field(
        None, description="Position of recommendation"
    )
    recommendation_algorithm: Optional[str] = Field(
        None, description="Algorithm used for recommendation"
    )

    # Interaction metadata
    value: Optional[float] = Field(None, description="Monetary value of interaction")
    quantity: Optional[int] = Field(None, description="Quantity involved")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )

    @validator("recommendation_position")
    def validate_recommendation_position(cls, v):
        if v is not None and v < 1:
            raise ValueError("Recommendation position must be >= 1")
        return v

    @validator("value")
    def validate_value(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be >= 0")
        return v

    @validator("quantity")
    def validate_quantity(cls, v):
        if v is not None and v < 1:
            raise ValueError("Quantity must be >= 1")
        return v


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
    context: Optional[ExtensionContext] = Field(None, description="Filter by context")
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
