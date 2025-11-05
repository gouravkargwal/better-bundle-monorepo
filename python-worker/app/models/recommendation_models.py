from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from app.domains.analytics.models.extension import ExtensionType


def normalize_graphql_id(value: Optional[str]) -> Optional[str]:
    """
    Normalize Shopify GraphQL ID to numeric ID.

    Converts: gid://shopify/Customer/8830605820155 -> 8830605820155
    Returns the original value if it's not a GraphQL ID format.
    """
    if not value:
        return value

    # Check if it's a GraphQL ID format (gid://shopify/Entity/123456)
    if value.startswith("gid://shopify/"):
        # Extract the numeric ID (last part after final /)
        parts = value.split("/")
        if len(parts) >= 4:
            return parts[-1]  # Return the numeric ID

    # Return as-is if not a GraphQL ID
    return value


class RecommendationRequest(BaseModel):
    """Unified request model for recommendations across all extensions"""

    shop_domain: str = Field(..., description="Shop domain")
    extension_type: ExtensionType = Field(..., description="Extension type")

    # Session info (required for standard endpoint)
    session_id: str = Field(..., description="Unified session identifier")

    # Recommendation parameters
    context: str = Field(
        ..., description="Context: product_page, homepage, cart, post_purchase, etc."
    )
    user_id: Optional[str] = Field(None, description="Customer identifier")

    @field_validator("user_id", mode="before")
    @classmethod
    def normalize_user_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize GraphQL ID to numeric ID"""
        return normalize_graphql_id(v)

    product_ids: Optional[List[str]] = Field(
        None, description="Product IDs for recommendations"
    )
    product_id: Optional[str] = Field(None, description="Single product ID")
    collection_id: Optional[str] = Field(None, description="Collection ID")
    limit: int = Field(default=6, ge=1, le=20, description="Number of recommendations")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class CombinedRecommendationRequest(BaseModel):
    """Combined request for Apollo: session creation + recommendations"""

    # Session creation fields
    shop_domain: str = Field(..., description="Shop domain")
    extension_type: ExtensionType = Field(
        default=ExtensionType.APOLLO, description="Extension type"
    )
    customer_id: Optional[str] = Field(None, description="Customer identifier")

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalize_customer_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize GraphQL ID to numeric ID"""
        return normalize_graphql_id(v)

    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(None, description="Shopify client ID")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")

    # Recommendation parameters (Apollo-specific)
    order_id: Optional[str] = Field(
        None, description="Order ID for post-purchase context"
    )
    purchased_products: Optional[List[str]] = Field(
        None, description="List of purchased products"
    )
    limit: int = Field(default=3, ge=1, le=3, description="Number of recommendations")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    recommendations: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of recommendations"
    )
    count: int = Field(0, description="Number of recommendations returned")
    source: Optional[str] = Field(None, description="Recommendation source/algorithm")
    session_data: Optional[Dict[str, Any]] = Field(
        None, description="Session data (only for combined endpoint)"
    )
