from typing import Dict, Any, List
from fastapi import HTTPException, Request

from app.models.recommendation_models import (
    RecommendationRequest,
    RecommendationResponse,
)
from app.domains.analytics.models.extension import ExtensionType
from app.services.session_service import SessionService
from app.services.interaction_service import InteractionService
from app.domains.analytics.models.interaction import InteractionType
from app.recommandations.models import RecommendationRequest
from app.models.session_models import (
    SessionAndRecommendationsRequest,
    SessionAndRecommendationsResponse,
)
from app.api.v1.recommendations import (
    fetch_recommendations_logic,
    services as recommendation_services,
)
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class RecommendationController:
    def __init__(self):
        self.session_service = SessionService()
        self.interaction_service = InteractionService()

    async def get_recommendations(
        self, request: RecommendationRequest, shop_info: Dict[str, Any]
    ) -> RecommendationResponse:
        """Handle standard recommendation retrieval (session must exist)"""

        # Use shop_id from JWT token (already validated)
        shop_id = shop_info["shop_id"]

        # Validate session exists
        session = await self.session_service.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {request.session_id} not found. Create session first.",
            )

        # Create RecommendationRequest from unified request
        rec_request = RecommendationRequest(
            shop_domain=request.shop_domain,
            context=request.context,
            user_id=request.user_id,
            session_id=request.session_id,
            product_ids=request.product_ids,
            product_id=request.product_id,
            collection_id=request.collection_id,
            limit=request.limit,
            metadata={
                **request.metadata,
                "extension_type": request.extension_type.value,
            },
        )

        # Fetch recommendations using existing logic
        result_data = await fetch_recommendations_logic(
            request=rec_request, services=recommendation_services
        )

        # Track recommendation_ready interaction
        try:
            await self.interaction_service.track_interaction(
                session_id=request.session_id,
                extension_type=request.extension_type,
                interaction_type=InteractionType.RECOMMENDATION_READY,
                shop_id=shop_id,
                customer_id=request.user_id,
                interaction_metadata={
                    "extension_type": request.extension_type.value,
                    "context": request.context,
                    "recommendation_count": result_data.get("count", 0),
                    "source": result_data.get("source", "unknown"),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track recommendation_ready interaction: {e}")

        return RecommendationResponse(
            success=True,
            message="Recommendations fetched successfully",
            recommendations=result_data.get("recommendations", []),
            count=result_data.get("count", 0),
            source=result_data.get("source", "unknown"),
        )

    async def get_recommendations_with_session(
        self,
        http_request: Request,
        request: SessionAndRecommendationsRequest,
        shop_info: Dict[str, Any],
    ) -> RecommendationResponse:
        """Handle combined session creation + recommendations (Apollo use case)"""

        # Use shop_id from JWT token (already validated)
        shop_id = shop_info["shop_id"]

        # Step 1: Create session
        session = await self.session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            user_agent=request.user_agent,
            client_id=request.client_id,
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add extension to session
        extension_type_str = request.extension_type or "unknown"
        await self.session_service.add_extension_to_session(
            session.id, extension_type_str
        )

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        logger.info(f"✅ Session created for {extension_type_str}: {session.id}")

        # Step 2: Get recommendations
        # Apollo-specific: use purchased products as context
        rec_request = RecommendationRequest(
            shop_domain=request.shop_domain,
            context="post_purchase",  # Hardcode for Apollo
            user_id=request.customer_id,
            product_ids=request.purchased_products,
            limit=request.limit,
            session_id=session.id,
            metadata={
                **request.metadata,
                "extension_type": extension_type_str,
                "order_id": request.order_id,
            },
        )

        result_data = await fetch_recommendations_logic(
            request=rec_request, services=recommendation_services
        )

        # Step 3: Track interaction
        try:
            # Convert string extension_type to ExtensionType enum
            from app.domains.analytics.models.extension import ExtensionType as ExtType

            # Only track if we can convert to a valid ExtensionType enum
            if extension_type_str:
                try:
                    extension_type_enum = ExtType(extension_type_str.lower())
                    await self.interaction_service.track_interaction(
                        session_id=session.id,
                        extension_type=extension_type_enum,
                        interaction_type=InteractionType.RECOMMENDATION_READY,
                        shop_id=shop_id,
                        customer_id=request.customer_id,
                        interaction_metadata={
                            "extension_type": extension_type_str,
                            "order_id": request.order_id,
                            "recommendation_count": result_data.get("count", 0),
                            "source": result_data.get("source", "unknown"),
                            "context": "post_purchase",
                        },
                    )
                except ValueError:
                    logger.warning(
                        f"Invalid extension_type: {extension_type_str}, skipping interaction tracking"
                    )
        except Exception as e:
            logger.warning(f"Failed to track interaction: {e}")

        return RecommendationResponse(
            success=True,
            message=f"{extension_type_str} session and recommendations retrieved successfully",
            recommendations=result_data.get("recommendations", []),
            count=result_data.get("count", 0),
            source=result_data.get("source", "unknown"),
            session_data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "client_id": session.client_id,
                "browser_session_id": session.browser_session_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
            },
        )


# Create singleton instance
recommendation_controller = RecommendationController()
