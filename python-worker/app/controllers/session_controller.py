import time
from typing import Dict, Any
from fastapi import HTTPException

from app.domains.analytics.models.extension import ExtensionType
from app.core.logging.logger import get_logger
from app.domains.analytics.services.shop_resolver import shop_resolver
from app.models.session_models import SessionRequest
from app.services.session_service import SessionService

logger = get_logger(__name__)


class SessionController:
    def __init__(self):
        self.session_service = SessionService()

    async def get_or_create_session(
        self, request: SessionRequest, authorization: str
    ) -> Dict[str, Any]:
        """Handle session creation business logic"""

        # Resolve shop domain to shop ID if needed
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve shop ID for domain: {request.shop_domain}",
            )

        # Browser session ID is now handled by backend (generated if not provided)
        browser_session_id = (
            request.browser_session_id
        )  # Can be None, backend will generate

        # Convert boolean flags to None if they weren't extracted (shouldn't happen but safety check)
        user_agent = request.user_agent if isinstance(request.user_agent, str) else None
        ip_address = request.ip_address if isinstance(request.ip_address, str) else None

        # Get or create unified session
        session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=browser_session_id,
            user_agent=user_agent,
            client_id=request.client_id,
            ip_address=ip_address,
            referrer=request.referrer,
        )

        # Use provided extension_type or default to "unknown"
        extension_type = request.extension_type or "unknown"
        await self.session_service.add_extension_to_session(session.id, extension_type)

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        return {
            "session_id": session.id,
            "customer_id": session.customer_id,
            "client_id": session.client_id,
            "browser_session_id": session.browser_session_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": (
                session.expires_at.isoformat() if session.expires_at else None
            ),
        }


# Create a singleton instance
session_controller = SessionController()
