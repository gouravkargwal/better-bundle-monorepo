"""
Customer Identity API

Industry-standard API for customer identity resolution and cross-session linking
using privacy-compliant methods and industry best practices.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.domains.analytics.services.customer_identity_resolution_service import (
    CustomerIdentityResolutionService,
)
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

# Create router for Customer Identity API
router = APIRouter(prefix="/api/customer-identity", tags=["Customer Identity"])

# Initialize services
identity_resolution_service = CustomerIdentityResolutionService()
cross_session_linking_service = CrossSessionLinkingService()
session_service = UnifiedSessionService()


class CustomerIdentificationRequest(BaseModel):
    """Request model for customer identification"""

    session_id: str = Field(..., description="Current session identifier")
    customer_id: str = Field(..., description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")
    customer_data: Optional[Dict[str, Any]] = Field(
        None, description="Optional customer data for enhanced matching"
    )
    trigger_event: str = Field(
        default="login",
        description="Event that triggered identification (login, purchase, etc.)",
    )


class CustomerLinkingRequest(BaseModel):
    """Request model for cross-session linking"""

    customer_id: str = Field(..., description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")
    trigger_session_id: Optional[str] = Field(
        None, description="Optional session that triggered the linking"
    )


class CustomerJourneyRequest(BaseModel):
    """Request model for customer journey analysis"""

    customer_id: str = Field(..., description="Customer identifier")
    shop_id: str = Field(..., description="Shop identifier")
    include_anonymous: bool = Field(
        default=True, description="Include anonymous sessions in journey"
    )


class CustomerIdentityResponse(BaseModel):
    """Response model for customer identity operations"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/identify-customer", response_model=CustomerIdentityResponse)
async def identify_customer(request: CustomerIdentificationRequest):
    """
    Identify a customer and link related anonymous sessions

    This endpoint implements industry-standard customer identity resolution
    using privacy-compliant methods to link anonymous sessions to identified customers.

    Use cases:
    - Customer logs in
    - Customer completes a purchase
    - Customer provides email/phone
    - Customer creates an account
    """
    try:
        logger.info(
            f"Customer identification request for customer {request.customer_id}"
        )

        # Step 1: Resolve customer identity and link related sessions
        resolution_result = await identity_resolution_service.resolve_customer_identity(
            customer_id=request.customer_id,
            current_session_id=request.session_id,
            shop_id=request.shop_id,
            customer_data=request.customer_data,
        )

        if not resolution_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Identity resolution failed: {resolution_result.get('error')}",
            )

        # Step 2: Perform cross-session linking for complete journey
        linking_result = await cross_session_linking_service.link_customer_sessions(
            customer_id=request.customer_id,
            shop_id=request.shop_id,
            trigger_session_id=request.session_id,
        )

        if not linking_result.get("success"):
            logger.warning(
                f"Cross-session linking failed: {linking_result.get('error')}"
            )
            # Don't fail the request, just log the warning

        # Combine results
        combined_result = {
            "identity_resolution": resolution_result,
            "cross_session_linking": linking_result,
            "trigger_event": request.trigger_event,
            "total_sessions_linked": (
                resolution_result.get("total_sessions", 0)
                + linking_result.get("linked_sessions", 0)
            ),
        }

        logger.info(
            f"Customer identification completed: {combined_result['total_sessions_linked']} sessions linked"
        )

        return CustomerIdentityResponse(
            success=True,
            message="Customer identification completed successfully",
            data=combined_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in customer identification: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Customer identification failed: {str(e)}"
        )


@router.post("/link-sessions", response_model=CustomerIdentityResponse)
async def link_customer_sessions(request: CustomerLinkingRequest):
    """
    Link all sessions for a customer using cross-session linking

    This endpoint performs comprehensive cross-session linking to reconstruct
    the complete customer journey using industry-standard methods.
    """
    try:
        logger.info(f"Cross-session linking request for customer {request.customer_id}")

        # Perform cross-session linking
        linking_result = await cross_session_linking_service.link_customer_sessions(
            customer_id=request.customer_id,
            shop_id=request.shop_id,
            trigger_session_id=request.trigger_session_id,
        )

        if not linking_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Cross-session linking failed: {linking_result.get('error')}",
            )

        logger.info(
            f"Cross-session linking completed: {linking_result.get('linked_sessions', 0)} sessions linked"
        )

        return CustomerIdentityResponse(
            success=True,
            message="Cross-session linking completed successfully",
            data=linking_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cross-session linking: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Cross-session linking failed: {str(e)}"
        )


@router.get("/journey/{customer_id}", response_model=CustomerIdentityResponse)
async def get_customer_journey(
    customer_id: str, shop_id: str, include_anonymous: bool = True
):
    """
    Get complete customer journey including all linked sessions

    This endpoint provides a comprehensive view of the customer's journey
    across all sessions and touchpoints.
    """
    try:
        logger.info(f"Customer journey request for customer {customer_id}")

        # Get all sessions for the customer
        sessions = await session_service.query_sessions(
            session_service.SessionQuery(customer_id=customer_id, shop_id=shop_id)
        )

        if not sessions:
            return CustomerIdentityResponse(
                success=True,
                message="No sessions found for customer",
                data={"customer_id": customer_id, "sessions": []},
            )

        # Sort sessions by creation time
        sessions.sort(key=lambda x: x.created_at)

        # Calculate journey metrics
        journey_start = sessions[0].created_at
        journey_end = sessions[-1].last_active
        journey_duration = (journey_end - journey_start).days

        total_interactions = sum(s.total_interactions for s in sessions)
        unique_extensions = set()
        for session in sessions:
            unique_extensions.update(session.extensions_used)

        # Get session details
        session_details = []
        for session in sessions:
            session_details.append(
                {
                    "session_id": session.id,
                    "created_at": session.created_at.isoformat(),
                    "last_active": session.last_active.isoformat(),
                    "extensions_used": session.extensions_used,
                    "total_interactions": session.total_interactions,
                    "status": session.status,
                    "is_anonymous": session.customer_id is None,
                }
            )

        journey_data = {
            "customer_id": customer_id,
            "shop_id": shop_id,
            "journey_start": journey_start.isoformat(),
            "journey_end": journey_end.isoformat(),
            "journey_duration_days": journey_duration,
            "total_sessions": len(sessions),
            "total_interactions": total_interactions,
            "unique_extensions": list(unique_extensions),
            "sessions": session_details,
            "journey_summary": {
                "avg_interactions_per_session": round(
                    total_interactions / len(sessions), 2
                ),
                "session_frequency": round(len(sessions) / max(journey_duration, 1), 2),
                "extensions_used": list(unique_extensions),
            },
        }

        return CustomerIdentityResponse(
            success=True,
            message="Customer journey retrieved successfully",
            data=journey_data,
        )

    except Exception as e:
        logger.error(f"Error getting customer journey: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get customer journey: {str(e)}"
        )


@router.get("/sessions/{customer_id}", response_model=CustomerIdentityResponse)
async def get_customer_sessions(customer_id: str, shop_id: str):
    """
    Get all sessions for a customer

    This endpoint returns all sessions associated with a customer,
    including both identified and previously anonymous sessions.
    """
    try:
        logger.info(f"Customer sessions request for customer {customer_id}")

        # Get all sessions for the customer
        sessions = await session_service.query_sessions(
            session_service.SessionQuery(customer_id=customer_id, shop_id=shop_id)
        )

        # Convert to response format
        session_list = []
        for session in sessions:
            session_list.append(
                {
                    "session_id": session.id,
                    "created_at": session.created_at.isoformat(),
                    "last_active": session.last_active.isoformat(),
                    "expires_at": (
                        session.expires_at.isoformat() if session.expires_at else None
                    ),
                    "extensions_used": session.extensions_used,
                    "total_interactions": session.total_interactions,
                    "status": session.status,
                    "browser_session_id": session.browser_session_id,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                }
            )

        return CustomerIdentityResponse(
            success=True,
            message="Customer sessions retrieved successfully",
            data={
                "customer_id": customer_id,
                "shop_id": shop_id,
                "total_sessions": len(sessions),
                "sessions": session_list,
            },
        )

    except Exception as e:
        logger.error(f"Error getting customer sessions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get customer sessions: {str(e)}"
        )


@router.post("/resolve-identity", response_model=CustomerIdentityResponse)
async def resolve_customer_identity(request: CustomerIdentificationRequest):
    """
    Resolve customer identity using industry-standard methods

    This endpoint implements the core identity resolution functionality
    used by the identify-customer endpoint but can be called independently.
    """
    try:
        logger.info(f"Identity resolution request for customer {request.customer_id}")

        # Perform identity resolution
        resolution_result = await identity_resolution_service.resolve_customer_identity(
            customer_id=request.customer_id,
            current_session_id=request.session_id,
            shop_id=request.shop_id,
            customer_data=request.customer_data,
        )

        if not resolution_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Identity resolution failed: {resolution_result.get('error')}",
            )

        logger.info(
            f"Identity resolution completed: {resolution_result.get('total_sessions', 0)} sessions linked"
        )

        return CustomerIdentityResponse(
            success=True,
            message="Identity resolution completed successfully",
            data=resolution_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in identity resolution: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Identity resolution failed: {str(e)}"
        )
