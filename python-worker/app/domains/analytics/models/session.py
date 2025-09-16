"""
User Session Models for Unified Analytics

Handles session management across all extensions with proper validation
and type safety.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class SessionStatus(str, Enum):
    """Session status enumeration"""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class UserSession(BaseModel):
    """User session model for unified analytics tracking"""

    id: str = Field(..., description="Unique session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(
        None, description="Customer identifier (null for anonymous)"
    )
    browser_session_id: str = Field(..., description="Browser's session identifier")
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE, description="Session status"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Session creation time"
    )
    last_active: datetime = Field(
        default_factory=datetime.utcnow, description="Last activity time"
    )
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")

    # Metadata
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")

    # Extension tracking
    extensions_used: List[str] = Field(
        default_factory=list, description="Extensions that used this session"
    )
    total_interactions: int = Field(
        default=0, description="Total interactions in this session"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SessionCreate(BaseModel):
    """Model for creating a new user session"""

    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: str = Field(..., description="Browser session identifier")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    session_duration_hours: int = Field(
        default=24, description="Session duration in hours"
    )

    @validator("session_duration_hours")
    def validate_session_duration(cls, v):
        if v < 1 or v > 168:  # 1 hour to 1 week
            raise ValueError("Session duration must be between 1 and 168 hours")
        return v

    def get_expires_at(self) -> datetime:
        """Calculate expiration time based on session duration"""
        return datetime.utcnow() + timedelta(hours=self.session_duration_hours)


class SessionUpdate(BaseModel):
    """Model for updating an existing user session"""

    status: Optional[SessionStatus] = Field(None, description="New session status")
    last_active: Optional[datetime] = Field(None, description="Update last active time")
    extensions_used: Optional[List[str]] = Field(
        None, description="Update extensions used"
    )
    total_interactions: Optional[int] = Field(
        None, description="Update total interactions"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SessionQuery(BaseModel):
    """Model for querying user sessions"""

    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    status: Optional[SessionStatus] = Field(None, description="Session status filter")
    created_after: Optional[datetime] = Field(
        None, description="Filter sessions created after this time"
    )
    created_before: Optional[datetime] = Field(
        None, description="Filter sessions created before this time"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
