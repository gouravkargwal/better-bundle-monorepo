"""
Gorse integration API endpoints for testing and manual operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.services.gorse_service import gorse_service
from app.core.config import settings

router = APIRouter()


class GorseTrainingRequest(BaseModel):
    """Gorse training request model"""

    shop_id: str
    shop_domain: str


class GorseRecommendationRequest(BaseModel):
    """Gorse recommendation request model"""

    shop_id: str
    user_id: Optional[str] = None
    item_id: Optional[str] = None
    category: Optional[str] = None
    limit: Optional[int] = 10


@router.post("/train")
async def train_gorse_model(request: GorseTrainingRequest) -> Dict[str, Any]:
    """Manually trigger Gorse model training for a shop"""
    if not settings.ENABLE_GORSE_SYNC:
        raise HTTPException(status_code=400, detail="Gorse integration is not enabled")

    try:
        # Initialize Gorse service
        await gorse_service.initialize()

        # Start training
        result = await gorse_service.train_model_for_shop(
            shop_id=request.shop_id, shop_domain=request.shop_domain
        )

        if result["success"]:
            return {
                "success": True,
                "message": "Gorse training initiated successfully",
                "result": result,
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gorse training error: {str(e)}")


@router.get("/recommendations/{shop_id}")
async def get_gorse_recommendations(
    shop_id: str,
    user_id: Optional[str] = None,
    item_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: Optional[int] = 10,
) -> Dict[str, Any]:
    """Get recommendations from Gorse"""
    if not settings.ENABLE_GORSE_SYNC:
        raise HTTPException(status_code=400, detail="Gorse integration is not enabled")

    try:
        # Initialize Gorse service
        await gorse_service.initialize()

        # Get recommendations
        result = await gorse_service.get_recommendations(
            shop_id=shop_id, user_id=user_id, item_id=item_id, category=category
        )

        if result["success"]:
            # Limit recommendations if specified
            recommendations = result["recommendations"][:limit]

            return {
                "success": True,
                "shop_id": shop_id,
                "user_id": user_id,
                "item_id": item_id,
                "category": category,
                "recommendations": recommendations,
                "total_count": len(recommendations),
                "limit": limit,
                "confidence_threshold": result["confidence_threshold"],
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")


@router.get("/gorse-health")
async def gorse_health_check() -> Dict[str, Any]:
    """Check Gorse service health"""
    if not settings.ENABLE_GORSE_SYNC:
        return {
            "success": False,
            "message": "Gorse integration is not enabled",
            "enabled": False,
        }

    try:
        # Initialize Gorse service
        await gorse_service.initialize()

        # Check health
        health_result = await gorse_service.check_gorse_health()

        return {
            "success": True,
            "enabled": True,
            "gorse_health": health_result,
            "gorse_url": settings.GORSE_BASE_URL,
        }

    except Exception as e:
        return {
            "success": False,
            "enabled": True,
            "error": str(e),
            "gorse_url": settings.GORSE_BASE_URL,
        }


@router.get("/status/{shop_id}")
async def get_gorse_model_status(shop_id: str) -> Dict[str, Any]:
    """Get Gorse model status for a shop"""
    if not settings.ENABLE_GORSE_SYNC:
        raise HTTPException(status_code=400, detail="Gorse integration is not enabled")

    try:
        # Initialize Gorse service
        await gorse_service.initialize()

        # Get model status
        status = await gorse_service.get_model_status(shop_id)

        if status["success"]:
            return status
        else:
            raise HTTPException(status_code=400, detail=status.get("error"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")


@router.post("/feedback")
async def submit_gorse_feedback(
    shop_id: str,
    user_id: str,
    item_id: str,
    feedback_type: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit feedback to Gorse"""
    if not settings.ENABLE_GORSE_SYNC:
        raise HTTPException(status_code=400, detail="Gorse integration is not enabled")

    try:
        # Initialize Gorse service
        await gorse_service.initialize()

        # Submit feedback
        result = await gorse_service.submit_feedback(
            shop_id=shop_id,
            user_id=user_id,
            item_id=item_id,
            feedback_type=feedback_type,
            comment=comment,
        )

        if result["success"]:
            return {
                "success": True,
                "message": "Feedback submitted successfully",
                "result": result,
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error"))

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Feedback submission error: {str(e)}"
        )
