"""
FBT Status API endpoints
Provides endpoints to check FBT model status and training results
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

from app.recommandations.frequently_bought_together import (
    FrequentlyBoughtTogetherService,
)
from app.recommandations.fp_growth_engine import FPGrowthEngine
from app.core.redis_client import get_redis_client
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/fbt", tags=["fbt-status"])


class FBTStatusResponse(BaseModel):
    """FBT status response model"""

    shop_id: str
    status: str  # Renamed from model_status to avoid protected namespace conflict
    last_training: Optional[str] = None
    association_rules_count: int = 0
    training_success: bool = False
    error_message: Optional[str] = None
    cache_status: str = "unknown"
    recommendations_available: bool = False


@router.get("/status/{shop_id}", response_model=FBTStatusResponse)
async def get_fbt_status(shop_id: str):
    """
    Get FBT model status for a shop

    Returns:
        - Model training status
        - Number of association rules
        - Last training timestamp
        - Cache status
        - Recommendations availability
    """
    try:
        logger.info(f"🔍 Checking FBT status for shop {shop_id}")

        # Initialize services
        fbt_service = FrequentlyBoughtTogetherService()
        fp_engine = FPGrowthEngine()

        # Check Redis cache for FBT rules
        redis_client = await get_redis_client()
        cache_key = f"fp_growth_rules:{shop_id}"

        # Get cached rules
        cached_rules = await redis_client.get(cache_key)
        cache_status = "available" if cached_rules else "empty"

        # Check if rules exist in cache
        rules_count = 0
        if cached_rules:
            try:
                import json

                rules_data = json.loads(cached_rules)
                # Rules are cached as a list of rule dictionaries, not a dict with "rules" key
                if isinstance(rules_data, list):
                    rules_count = len(rules_data)
                else:
                    rules_count = len(rules_data.get("rules", []))
            except Exception as e:
                logger.warning(f"Failed to parse cached rules: {e}")

        # Determine model status
        if rules_count > 0:
            status = "trained"
            recommendations_available = True
        else:
            status = "not_trained"
            recommendations_available = False

        # Get last training timestamp from cache metadata
        last_training = None
        if cached_rules:
            try:
                import json

                rules_data = json.loads(cached_rules)
                last_training = rules_data.get("training_timestamp")
            except Exception:
                pass

        return FBTStatusResponse(
            shop_id=shop_id,
            status=status,
            last_training=last_training,
            association_rules_count=rules_count,
            training_success=rules_count > 0,
            cache_status=cache_status,
            recommendations_available=recommendations_available,
        )

    except Exception as e:
        logger.error(f"Failed to get FBT status for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/{shop_id}")
async def trigger_fbt_training(shop_id: str):
    """
    Manually trigger FBT model training for a shop
    """
    try:
        logger.info(f"🧠 Manually triggering FBT training for shop {shop_id}")

        fbt_service = FrequentlyBoughtTogetherService()
        result = await fbt_service.train_fp_growth_model(shop_id)

        return {
            "shop_id": shop_id,
            "training_triggered": True,
            "result": result,
            "timestamp": now_utc(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger FBT training for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/{shop_id}")
async def test_fbt_recommendations(shop_id: str, product_id: str = "10050278228282"):
    """
    Test FBT recommendations for a specific product
    """
    try:
        logger.info(
            f"🧪 Testing FBT recommendations for shop {shop_id}, product {product_id}"
        )

        fbt_service = FrequentlyBoughtTogetherService()
        result = await fbt_service.get_frequently_bought_together(
            shop_id=shop_id, product_id=product_id, limit=5
        )

        return {
            "shop_id": shop_id,
            "product_id": product_id,
            "test_result": result,
            "timestamp": now_utc(),
        }

    except Exception as e:
        logger.error(f"Failed to test FBT recommendations for shop {shop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_fbt_health():
    """
    Get FBT system health status
    """
    try:
        # Check Redis connection
        redis_client = await get_redis_client()
        redis_status = "connected" if redis_client else "disconnected"

        # Check FBT service availability
        fbt_service = FrequentlyBoughtTogetherService()
        service_status = "available"

        return {
            "fbt_system": "operational",
            "redis_status": redis_status,
            "service_status": service_status,
            "timestamp": now_utc(),
        }

    except Exception as e:
        logger.error(f"FBT health check failed: {e}")
        return {"fbt_system": "error", "error": str(e), "timestamp": now_utc()}
