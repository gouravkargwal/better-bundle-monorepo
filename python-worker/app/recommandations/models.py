from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class RecommendationRequest(BaseModel):
    """Request model for recommendations"""

    shop_domain: Optional[str] = Field(
        None,
        description="Shop domain (optional - will be looked up from user_id if not provided)",
    )
    context: str = Field(
        ...,
        description="Context: product_page, homepage, cart, collection_page, profile, checkout, order_history, order_status",
    )
    product_ids: Optional[List[str]] = Field(
        None,
        description="Product IDs for recommendations (single or multiple products)",
    )
    product_id: Optional[str] = Field(
        None,
        description="Single product ID for product page recommendations",
    )
    collection_id: Optional[str] = Field(
        None,
        description="Collection ID for collection page recommendations",
    )
    user_id: Optional[str] = Field(
        None, description="User ID for personalized recommendations"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID for session-based recommendations"
    )
    category: Optional[str] = Field(None, description="Category filter")
    limit: int = Field(default=6, ge=1, le=20, description="Number of recommendations")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""

    success: bool
    recommendations: List[Dict[str, Any]]
    count: int
    source: str  # "gorse", "fallback", "database"
    context: str
    timestamp: datetime
