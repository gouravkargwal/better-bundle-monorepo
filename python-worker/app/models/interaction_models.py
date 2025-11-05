from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from app.domains.analytics.models.extension import ExtensionType
from app.domains.analytics.models.interaction import InteractionType


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


# New Interaction Models
class InteractionRequest(BaseModel):
    """Unified request model for tracking interactions across all extensions"""

    session_id: str = Field(..., description="Unified session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    extension_type: ExtensionType = Field(
        ..., description="Extension type (venus, atlas, phoenix, apollo, mercury)"
    )
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(
        None, description="Customer identifier (optional)"
    )

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalize_customer_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize GraphQL ID to numeric ID"""
        return normalize_graphql_id(v)

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )


class InteractionResponse(BaseModel):
    """Response model for interaction tracking"""

    success: bool = Field(
        ..., description="Whether the interaction was tracked successfully"
    )
    message: str = Field(..., description="Response message")
    interaction_id: Optional[str] = Field(None, description="Created interaction ID")
    session_recovery: Optional[Dict[str, Any]] = Field(
        None, description="Session recovery details if session was recovered"
    )
