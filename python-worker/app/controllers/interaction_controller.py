from typing import Dict, Any
from fastapi import HTTPException

from app.models.interaction_models import InteractionRequest, InteractionResponse
from app.services.interaction_service import InteractionService
from app.services.session_service import SessionService
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class InteractionController:
    def __init__(self):
        self.interaction_service = InteractionService()
        self.session_service = SessionService()

    async def track_interaction(
        self, request: InteractionRequest, shop_info: Dict[str, Any]
    ) -> InteractionResponse:
        """Handle interaction tracking business logic"""

        # Use shop_id from JWT token (already validated)
        shop_id = shop_info["shop_id"]

        # Add extension type to metadata if not already present
        enhanced_metadata = {
            **request.metadata,
            "extension_type": request.extension_type.value,
        }

        # Try to track interaction with the original session
        interaction = await self.interaction_service.track_interaction(
            session_id=request.session_id,
            extension_type=request.extension_type,
            interaction_type=request.interaction_type,
            shop_id=shop_id,
            customer_id=request.customer_id,
            interaction_metadata=enhanced_metadata,
        )

        # Check if session recovery is needed
        session_recovery_info = None
        if not interaction:
            logger.warning(
                f"Session {request.session_id} not found, attempting recovery..."
            )

            # Try to find recent session for same customer
            if request.customer_id:
                recent_session = (
                    await self.session_service._find_recent_customer_session(
                        request.customer_id, shop_id, minutes_back=30
                    )
                )

                if recent_session:
                    logger.info(f"✅ Recovered recent session: {recent_session.id}")
                    session_recovery_info = {
                        "original_session_id": request.session_id,
                        "new_session_id": recent_session.id,
                        "recovery_reason": "recent_session_found",
                        "recovered_at": recent_session.last_active.isoformat(),
                    }

                    # Retry interaction tracking with recovered session
                    interaction = await self.interaction_service.track_interaction(
                        session_id=recent_session.id,
                        extension_type=request.extension_type,
                        interaction_type=request.interaction_type,
                        shop_id=shop_id,
                        customer_id=request.customer_id,
                        interaction_metadata=enhanced_metadata,
                    )

            if not interaction:
                logger.error(
                    f"Failed to track interaction - session {request.session_id} not found and recovery failed"
                )
                return InteractionResponse(
                    success=False,
                    message=f"Session {request.session_id} not found and could not be recovered",
                )

        # Add extension to session's extensions_used list
        await self.session_service.add_extension_to_session(
            interaction.session_id, request.extension_type.value
        )

        return InteractionResponse(
            success=True,
            message="Interaction tracked successfully",
            interaction_id=interaction.id,
            session_recovery=session_recovery_info,
        )


# Create a singleton instance
interaction_controller = InteractionController()
