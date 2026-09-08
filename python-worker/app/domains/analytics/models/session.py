from __future__ import annotations

from enum import Enum
from typing import Optional, List
from datetime import datetime


class SessionStatus(str, Enum):
    """Session status enumeration"""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class UserSession:
    """User session model — minimal constructor-based class.

    Replaces the deleted Pydantic model from the old analytics domain.
    """

    def __init__(
        self,
        id: str,
        shop_id: str,
        customer_id: Optional[str] = None,
        client_id: Optional[str] = None,
        browser_session_id: Optional[str] = None,
        status: SessionStatus = SessionStatus.ACTIVE,
        created_at: Optional[datetime] = None,
        last_active: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
        extensions_used: Optional[List[str]] = None,
        total_interactions: int = 0,
    ):
        self.id = id
        self.shop_id = shop_id
        self.customer_id = customer_id
        self.client_id = client_id
        self.browser_session_id = browser_session_id
        self.status = status
        self.created_at = created_at
        self.last_active = last_active
        self.expires_at = expires_at
        self.user_agent = user_agent
        self.ip_address = ip_address
        self.referrer = referrer
        self.extensions_used = extensions_used or []
        self.total_interactions = total_interactions


class SessionUpdate:
    pass


class SessionCreate:
    pass
