from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.domains.analytics.models.extension import ExtensionType


class SessionRequest(BaseModel):
    """Request model for session creation"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(None, description="Shopify client ID (optional)")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
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
