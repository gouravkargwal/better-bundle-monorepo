"""
Session Management API

Lightweight endpoints for session updates
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.models.session import SessionUpdate
from app.core.logging.logger import get_logger
from app.domains.analytics.services.shop_resolver import shop_resolver

logger = get_logger(__name__)

router = APIRouter(prefix="/api/session", tags=["Session Management"])

session_service = UnifiedSessionService()


class UpdateClientIdRequest(BaseModel):
    """Request to update client_id for a session"""

    session_id: str = Field(..., description="Session identifier")
    client_id: str = Field(..., description="Shopify client ID")
    shop_domain: str = Field(..., description="Shop domain for validation")


class SessionResponse(BaseModel):
    """Response for session operations"""

    success: bool
    message: str


@router.post("/update-client-id", response_model=SessionResponse)
async def update_client_id(request: UpdateClientIdRequest):
    """
    Update client_id for an existing session (background update)

    This is called when a cached session is reused but we have a new client_id
    """
    try:
        # Validate shop
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(status_code=400, detail="Invalid shop domain")

        # Get session to verify it exists and belongs to this shop
        session = await session_service.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.shop_id != shop_id:
            raise HTTPException(
                status_code=403, detail="Session does not belong to this shop"
            )

        # Update client_id if it's different
        if session.client_id != request.client_id:
            await session_service.update_session(
                request.session_id, SessionUpdate(client_id=request.client_id)
            )
            logger.info(f"Updated client_id for session {request.session_id}")

        return SessionResponse(success=True, message="Client ID updated successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client_id: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
