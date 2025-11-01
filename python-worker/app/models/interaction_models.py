from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.domains.analytics.models.extension import ExtensionType
from app.domains.analytics.models.interaction import InteractionType


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
