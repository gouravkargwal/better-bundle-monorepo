"""
Gorse Integration Service: Connects our computed features with Gorse ML training.

This service:
1. Exports computed features from our database
2. Formats data for Gorse ingestion
3. Trains recommendation models
4. Manages model deployment
"""

import asyncio
import json
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.core.config import settings
from app.core.database import get_database
from app.core.logging import get_logger, log_error

logger = get_logger(__name__)


class GorseIntegrationService:
    """Service to integrate BetterBundle features with Gorse ML training."""

    def __init__(self):
        self.gorse_master_url = "http://localhost:8088"
        self.gorse_server_url = "http://localhost:8087"
        self.gorse_worker_url = "http://localhost:8089"

    async def export_features_for_gorse(self, shop_id: str) -> Dict[str, Any]:
        """Export computed features and format them for Gorse ingestion."""
        db = await get_database()

        try:
            logger.info(f"Exporting features for shop {shop_id} to Gorse format")

            # Fetch all computed features
            user_features = await db.userfeatures.find_many(where={"shopId": shop_id})

            product_features = await db.productfeatures.find_many(
                where={"shopId": shop_id}
            )

            interaction_features = await db.interactionfeatures.find_many(
                where={"shopId": shop_id}
            )

            # Format data for Gorse
            gorse_data = {"users": [], "items": [], "feedback": []}

            # Convert user features to Gorse users
            for user_feature in user_features:
                gorse_data["users"].append(
                    {
                        "UserId": user_feature.customerId,
                        "Labels": [
                            f"total_purchases_{user_feature.totalPurchases}",
                            f"recency_days_{user_feature.recencyDays}",
                            f"total_spent_{user_feature.totalSpent}",
                            f"shop_{shop_id}",
                        ],
                        "Comment": f"Customer with {user_feature.totalPurchases} purchases, {user_feature.recencyDays} days since last order",
                    }
                )

            # Convert product features to Gorse items
            for product_feature in product_features:
                gorse_data["items"].append(
                    {
                        "ItemId": product_feature.productId,
                        "Labels": [
                            f"category_{product_feature.category or 'unknown'}",
                            f"price_tier_{product_feature.priceTier}",
                            f"popularity_{product_feature.popularity}",
                            f"shop_{shop_id}",
                        ],
                        "Comment": f"Product with {product_feature.popularity} total orders, {product_feature.priceTier} price tier",
                    }
                )

            # Convert interaction features to Gorse feedback
            for interaction_feature in interaction_features:
                gorse_data["feedback"].append(
                    {
                        "FeedbackType": "star",  # Positive feedback for purchases
                        "UserId": interaction_feature.customerId,
                        "ItemId": interaction_feature.productId,
                        "Timestamp": (
                            interaction_feature.lastPurchaseDate.isoformat()
                            if interaction_feature.lastPurchaseDate
                            else datetime.now().isoformat()
                        ),
                        "Comment": f"Customer purchased {interaction_feature.purchaseCount} times",
                    }
                )

            logger.info(
                f"Exported {len(gorse_data['users'])} users, {len(gorse_data['items'])} items, {len(gorse_data['feedback'])} interactions"
            )

            return gorse_data

        except Exception as e:
            logger.error(f"Error exporting features for shop {shop_id}: {e}")
            raise

    async def ingest_data_to_gorse(
        self, shop_id: str, gorse_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ingest the formatted data into Gorse."""
        try:
            async with httpx.AsyncClient() as client:
                # Ingest users
                if gorse_data["users"]:
                    user_response = await client.post(
                        f"{self.gorse_master_url}/api/user", json=gorse_data["users"]
                    )
                    logger.info(
                        f"Ingested {len(gorse_data['users'])} users: {user_response.status_code}"
                    )

                # Ingest items
                if gorse_data["items"]:
                    item_response = await client.post(
                        f"{self.gorse_master_url}/api/item", json=gorse_data["items"]
                    )
                    logger.info(
                        f"Ingested {len(gorse_data['items'])} items: {item_response.status_code}"
                    )

                # Ingest feedback
                if gorse_data["feedback"]:
                    feedback_response = await client.post(
                        f"{self.gorse_master_url}/api/feedback",
                        json=gorse_data["feedback"],
                    )
                    logger.info(
                        f"Ingested {len(gorse_data['feedback'])} feedback records: {feedback_response.status_code}"
                    )

                return {
                    "success": True,
                    "users_ingested": len(gorse_data["users"]),
                    "items_ingested": len(gorse_data["items"]),
                    "feedback_ingested": len(gorse_data["feedback"]),
                }

        except Exception as e:
            logger.error(f"Error ingesting data to Gorse: {e}")
            raise

    async def train_model(self, shop_id: str) -> Dict[str, Any]:
        """Trigger model training for a specific shop."""
        try:
            async with httpx.AsyncClient() as client:
                # Trigger training
                response = await client.post(
                    f"{self.gorse_master_url}/api/training",
                    json={
                        "name": f"shop_{shop_id}_model",
                        "description": f"Recommendation model for shop {shop_id}",
                    },
                )

                if response.status_code == 200:
                    logger.info(f"Model training triggered for shop {shop_id}")
                    return {"success": True, "training_triggered": True}
                else:
                    logger.error(f"Failed to trigger training: {response.status_code}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Error triggering model training: {e}")
            raise

    async def get_recommendations(
        self, shop_id: str, user_id: str, n: int = 10
    ) -> List[str]:
        """Get product recommendations for a user."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.gorse_server_url}/api/recommend/{user_id}", params={"n": n}
                )

                if response.status_code == 200:
                    recommendations = response.json()
                    logger.info(
                        f"Got {len(recommendations)} recommendations for user {user_id}"
                    )
                    return recommendations
                else:
                    logger.error(
                        f"Failed to get recommendations: {response.status_code}"
                    )
                    return []

        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []

    async def get_model_status(self, shop_id: str) -> Dict[str, Any]:
        """Get the status of the trained model."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.gorse_master_url}/api/status")

                if response.status_code == 200:
                    status = response.json()
                    return {"success": True, "status": status, "shop_id": shop_id}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Error getting model status: {e}")
            return {"success": False, "error": str(e)}


async def run_gorse_training_pipeline(shop_id: str) -> Dict[str, Any]:
    """Complete pipeline: export features → ingest to Gorse → train model."""
    service = GorseIntegrationService()

    try:
        logger.info(f"Starting Gorse training pipeline for shop {shop_id}")

        # Step 1: Export features
        gorse_data = await service.export_features_for_gorse(shop_id)

        # Step 2: Ingest to Gorse
        ingestion_result = await service.ingest_data_to_gorse(shop_id, gorse_data)

        # Step 3: Train model
        training_result = await service.train_model(shop_id)

        # Step 4: Get model status
        model_status = await service.get_model_status(shop_id)

        return {
            "success": True,
            "shop_id": shop_id,
            "pipeline_steps": {
                "feature_export": gorse_data,
                "data_ingestion": ingestion_result,
                "model_training": training_result,
                "model_status": model_status,
            },
        }

    except Exception as e:
        logger.error(f"Error in Gorse training pipeline: {e}")
        return {"success": False, "error": str(e)}
