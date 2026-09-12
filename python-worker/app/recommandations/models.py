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
    # No default on purpose. `fetch_recommendations_logic` does
    # `request.limit or RETURN_LIMIT[surface]`, so any default here silently
    # overrides the per-surface limits — a default of 6 meant the checkout
    # asked for 3 and got 6, and RETURN_LIMIT was dead code.
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of recommendations; defaults to the surface's limit",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )
    # Set by the storefront when the page is not a real shopper visit — a theme
    # customiser session or a shareable theme preview link. Recommendations are
    # still served (the merchant is trying to see the widget) but no impression
    # is written, because a merchant previewing their own theme is not an offer
    # shown to a shopper and counting it drags the conversion rate down.
    preview: bool = Field(
        default=False,
        description="Theme editor or preview render; serve but do not record",
    )
    # Diagnostics from the storefront's theme sniffer (theme-adapt.js). Not used
    # to serve anything — it is recorded on the request span so we can answer
    # "which real themes do our CSS probe lists fail on", which is not knowable
    # from this side. Typed rather than left to pydantic's extra-ignore so the
    # shape is documented and a malformed payload is rejected at the edge.
    theme_adapt: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Which theme-adaptation selectors matched on the storefront",
    )


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""

    success: bool
    recommendations: List[Dict[str, Any]]
    count: int
    source: str  # "gorse", "fallback", "database"
    context: str
    timestamp: datetime
