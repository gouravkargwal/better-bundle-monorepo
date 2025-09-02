"""
Gorse Training API: Endpoints for ML model training and recommendations.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any

from app.services.gorse_integration import (
    run_gorse_training_pipeline,
    GorseIntegrationService,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/gorse", tags=["gorse-training"])


@router.post("/train/{shop_id}")
async def trigger_gorse_training(
    shop_id: str, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Trigger Gorse ML training for a specific shop.

    This endpoint:
    1. Exports computed features from our database
    2. Ingests data into Gorse
    3. Triggers model training
    4. Returns training status
    """
    try:
        logger.info(f"Triggering Gorse training for shop {shop_id}")

        # Run the complete pipeline
        result = await run_gorse_training_pipeline(shop_id)

        if result["success"]:
            logger.info(
                f"Gorse training pipeline completed successfully for shop {shop_id}"
            )
            return {
                "success": True,
                "message": "Gorse training pipeline completed successfully",
                "shop_id": shop_id,
                "pipeline_result": result,
            }
        else:
            logger.error(
                f"Gorse training pipeline failed for shop {shop_id}: {result.get('error')}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Gorse training pipeline failed: {result.get('error')}",
            )

    except Exception as e:
        logger.error(f"Error triggering Gorse training for shop {shop_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger Gorse training: {str(e)}"
        )


@router.get("/status/{shop_id}")
async def get_gorse_status(shop_id: str) -> Dict[str, Any]:
    """Get the current status of Gorse services and models."""
    try:
        service = GorseIntegrationService()
        status = await service.get_model_status(shop_id)

        return {"success": True, "shop_id": shop_id, "gorse_status": status}

    except Exception as e:
        logger.error(f"Error getting Gorse status for shop {shop_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get Gorse status: {str(e)}"
        )


@router.get("/recommendations/{shop_id}/{user_id}")
async def get_recommendations(
    shop_id: str, user_id: str, n: int = 10
) -> Dict[str, Any]:
    """
    Get product recommendations for a specific user.

    Args:
        shop_id: The shop identifier
        user_id: The customer identifier
        n: Number of recommendations to return (default: 10)
    """
    try:
        service = GorseIntegrationService()
        recommendations = await service.get_recommendations(shop_id, user_id, n)

        return {
            "success": True,
            "shop_id": shop_id,
            "user_id": user_id,
            "recommendations": recommendations,
            "count": len(recommendations),
        }

    except Exception as e:
        logger.error(
            f"Error getting recommendations for user {user_id} in shop {shop_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {str(e)}"
        )


@router.post("/export-features/{shop_id}")
async def export_features_for_gorse(shop_id: str) -> Dict[str, Any]:
    """
    Export computed features for a shop in Gorse format.

    This is useful for debugging and understanding what data will be sent to Gorse.
    """
    try:
        service = GorseIntegrationService()
        gorse_data = await service.export_features_for_gorse(shop_id)

        return {
            "success": True,
            "shop_id": shop_id,
            "export_summary": {
                "users_count": len(gorse_data["users"]),
                "items_count": len(gorse_data["items"]),
                "feedback_count": len(gorse_data["feedback"]),
            },
            "gorse_data": gorse_data,
        }

    except Exception as e:
        logger.error(f"Error exporting features for shop {shop_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to export features: {str(e)}"
        )
