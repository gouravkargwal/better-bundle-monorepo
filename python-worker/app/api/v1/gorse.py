"""
Gorse integration API endpoints for testing and manual operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.gorse_service import gorse_service
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

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
        # Generate unique job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Publish training event to Redis Stream
        from app.core.redis_client import streams_manager
        await streams_manager.initialize()
        
        training_event = {
            "event_type": "ML_TRAINING_REQUESTED",
            "job_id": job_id,
            "shop_id": request.shop_id,
            "shop_domain": request.shop_domain,
            "timestamp": datetime.now().isoformat(),
            "training_type": "gorse_recommendations"
        }
        
        await streams_manager.publish_event(
            stream_name=settings.ML_TRAINING_STREAM,
            event_data=training_event
        )
        
        logger.info(
            "Gorse training event published",
            job_id=job_id,
            shop_id=request.shop_id,
            stream=settings.ML_TRAINING_STREAM
        )
        
        return {
            "success": True,
            "message": "Gorse training event published successfully",
            "job_id": job_id,
            "shop_id": request.shop_id,
            "status": "queued",
            "note": "Training will be processed asynchronously. Check status endpoint for updates."
        }

    except Exception as e:
        logger.error(f"Failed to publish training event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to publish training event: {str(e)}")


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
