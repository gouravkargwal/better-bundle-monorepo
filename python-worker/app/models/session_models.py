from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
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


class SessionRequest(BaseModel):
    """Request model for session creation"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalize_customer_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize GraphQL ID to numeric ID"""
        return normalize_graphql_id(v)

    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(None, description="Shopify client ID (optional)")
    user_agent: Optional[str | bool] = Field(
        None, description="User agent string or boolean (true = extract from headers)"
    )
    ip_address: Optional[str | bool] = Field(
        None, description="IP address or boolean (true = extract from headers)"
    )
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")
    extension_type: Optional[str] = Field(
        None,
        description="Extension type (phoenix, apollo, venus, atlas, mercury). Defaults to 'unknown' if not provided.",
    )


class SessionResponse(BaseModel):
    """Response model for session management"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    session_recovery: Optional[Dict[str, Any]] = Field(
        None, description="Session recovery details"
    )


class SessionAndRecommendationsRequest(BaseModel):
    """Request model for session and recommendations"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalize_customer_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize GraphQL ID to numeric ID"""
        return normalize_graphql_id(v)

    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(None, description="Shopify client ID (optional)")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")

    # Recommendation parameters
    order_id: Optional[str] = Field(
        None, description="Order ID for post-purchase context"
    )
    purchased_products: Optional[list] = Field(
        None, description="List of purchased products"
    )
    limit: int = Field(
        default=3,
        ge=1,
        le=3,
        description="Number of recommendations (max 3 for post-purchase)",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )
    extension_type: Optional[str] = Field(
        None,
        description="Extension type (phoenix, apollo, venus, atlas, mercury). Defaults to 'unknown' if not provided.",
    )


class SessionAndRecommendationsResponse(BaseModel):
    """Response model for session and recommendations"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    session_data: Optional[Dict[str, Any]] = Field(
        None, description="Session information"
    )
    recommendations: Optional[list] = Field(None, description="Product recommendations")
    recommendation_count: int = Field(
        default=0, description="Number of recommendations returned"
    )
