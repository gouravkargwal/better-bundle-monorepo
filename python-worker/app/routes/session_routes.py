from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.core.dependencies import get_shop_authorization

from app.models.session_models import SessionRequest, SessionResponse
from app.controllers.session_controller import session_controller
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/session", tags=["Session Management"])


@router.post("/get-or-create-session", response_model=SessionResponse)
async def get_or_create_session(
    request: SessionRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    try:
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
