from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from app.core.dependencies import get_shop_authorization

from app.models.session_models import (
    SessionRequest,
    SessionResponse,
    SessionAndRecommendationsRequest,
    SessionAndRecommendationsResponse,
)
from app.controllers.session_controller import session_controller
from app.controllers.recommendation_controller import recommendation_controller
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/session", tags=["Session Management"])


def extract_ip_address(request: Request) -> str | None:
    """Extract IP address from request headers"""
    # Check X-Forwarded-For (for proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip

    # Check X-Real-IP (for nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client host
    if request.client and request.client.host:
        return request.client.host

    return None


def extract_user_agent(request: Request) -> str | None:
    """Extract User-Agent from request headers"""
    return request.headers.get("User-Agent")


@router.post("/get-or-create-session", response_model=SessionResponse)
async def get_or_create_session(
    http_request: Request,
    request: SessionRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    try:
        # ✅ Extract IP address from headers if flag is True
        if request.ip_address is True:
            request.ip_address = extract_ip_address(http_request)

        # ✅ Extract User-Agent from headers if flag is True
        if request.user_agent is True:
            request.user_agent = extract_user_agent(http_request)

        session_data = await session_controller.get_or_create_session(
            request, shop_info
        )

        response = SessionResponse(
            success=True,
            message="Session created successfully",
            data=session_data,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create session: {str(e)}"
        )


@router.post(
    "/get-session-and-recommendations", response_model=SessionAndRecommendationsResponse
)
async def get_session_and_recommendations(
    http_request: Request,
    request: SessionAndRecommendationsRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    """
    Get or create session and fetch recommendations in a single API call

    This optimized endpoint combines session creation and recommendation retrieval
    to minimize API calls and improve performance for Apollo post-purchase extension.
    """
    try:

        return await recommendation_controller.get_recommendations_with_session(
            http_request, request, shop_info
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 from suspension check) without modification
        raise
    except Exception as e:
        logger.error(f"Error in Apollo combined request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session and recommendations: {str(e)}",
        )
