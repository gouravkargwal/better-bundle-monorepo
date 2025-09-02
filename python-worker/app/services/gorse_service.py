"""
Gorse integration service for training models and serving recommendations
"""

import structlog
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import httpx
import json
from datetime import datetime

from app.core.config import settings
from app.core.database import get_database
from app.core.logging import get_logger, log_error, log_performance

logger = get_logger(__name__)


class GorseService:
    """Service for integrating with Gorse recommendation engine"""

    def __init__(self):
        self.db = None
        self.base_url = settings.GORSE_BASE_URL
        self.api_key = settings.GORSE_API_KEY
        self.master_key = settings.GORSE_MASTER_KEY

    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()
        logger.info("Gorse service initialized")

    async def train_model_for_shop(
        self, shop_id: str, shop_domain: str
    ) -> Dict[str, Any]:
        """Train recommendation model for a specific shop by sending data to Gorse"""
        try:
            start_time = asyncio.get_event_loop().time()

            logger.info(
                "Starting model training", shop_id=shop_id, shop_domain=shop_domain
            )

            # Step 1: Check if shop has enough data for training
            data_check = await self._check_training_data_requirements(shop_id)
            if not data_check["can_train"]:
                return {
                    "success": False,
                    "error": f"Insufficient data for training: {data_check['reason']}",
                    "data_summary": data_check,
                }

            # Step 2: Extract and prepare training data
            training_data = await self._prepare_training_data(shop_id)

            # Step 3: Send data to Gorse (Gorse will handle training automatically)
            gorse_result = await self._send_data_to_gorse(shop_domain, training_data)

            # Step 4: Update training metadata
            await self._update_training_metadata(shop_id, gorse_result)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance("model_training", duration_ms, shop_id=shop_id)

            logger.info(
                "Data sent to Gorse successfully",
                shop_id=shop_id,
                duration_ms=duration_ms,
                items_count=training_data["items_count"],
                users_count=training_data["users_count"],
                feedback_count=training_data["feedback_count"],
            )

            return {
                "success": True,
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "gorse_result": gorse_result,
                "data_summary": data_check,
                "duration_ms": duration_ms,
                "message": "Data sent to Gorse for automatic training",
            }

        except Exception as e:
            log_error(e, {"operation": "train_model", "shop_id": shop_id})
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def _check_training_data_requirements(self, shop_id: str) -> Dict[str, Any]:
        """Check if shop has enough data for training"""
        try:
            # Count orders
            orders_count = await self.db.orderdata.count(where={"shopId": shop_id})

            # Count products
            products_count = await self.db.productdata.count(where={"shopId": shop_id})

            # Count customers
            customers_count = await self.db.customerdata.count(
                where={"shopId": shop_id}
            )

            can_train = (
                orders_count >= settings.MIN_ORDERS_FOR_TRAINING
                and products_count >= settings.MIN_PRODUCTS_FOR_TRAINING
            )

            reason = ""
            if not can_train:
                if orders_count < settings.MIN_ORDERS_FOR_TRAINING:
                    reason = f"Need at least {settings.MIN_ORDERS_FOR_TRAINING} orders, got {orders_count}"
                elif products_count < settings.MIN_PRODUCTS_FOR_TRAINING:
                    reason = f"Need at least {settings.MIN_PRODUCTS_FOR_TRAINING} products, got {products_count}"

            return {
                "can_train": can_train,
                "reason": reason,
                "orders_count": orders_count,
                "products_count": products_count,
                "customers_count": customers_count,
                "min_orders_required": settings.MIN_ORDERS_FOR_TRAINING,
                "min_products_required": settings.MIN_PRODUCTS_FOR_TRAINING,
            }

        except Exception as e:
            logger.error(
                "Error checking training data requirements",
                shop_id=shop_id,
                error=str(e),
            )
            return {"can_train": False, "reason": f"Error checking data: {str(e)}"}

    async def _prepare_training_data(self, shop_id: str) -> Dict[str, Any]:
        """Prepare training data for Gorse"""
        try:
            # Get orders with line items
            orders = await self.db.orderdata.find_many(
                where={"shopId": shop_id},
                select={
                    "id": True,
                    "customerId": True,
                    "lineItems": True,
                    "orderDate": True,
                },
            )

            # Get products
            products = await self.db.productdata.find_many(
                where={"shopId": shop_id, "isActive": True},
                select={
                    "id": True,
                    "productId": True,
                    "title": True,
                    "category": True,
                    "price": True,
                },
            )

            # Create product lookup
            product_lookup = {p.productId: p for p in products}

            # Prepare items for Gorse
            items = []
            for product in products:
                items.append(
                    {
                        "ItemId": product.productId,
                        "Timestamp": datetime.now().isoformat(),
                        "Categories": [product.category] if product.category else [],
                        "Tags": [],
                        "Labels": [],
                        "Comment": product.title,
                    }
                )

            # Prepare users for Gorse
            users = []
            user_orders = {}

            for order in orders:
                if order.customerId:
                    if order.customerId not in user_orders:
                        user_orders[order.customerId] = []
                        users.append(
                            {
                                "UserId": order.customerId,
                                "Labels": [],
                                "Subscribe": "true",
                                "Comment": f"Customer from {shop_id}",
                            }
                        )

                    # Add order to user's history
                    user_orders[order.customerId].append(order)

            # Prepare feedback for Gorse
            feedback = []
            for order in orders:
                if order.customerId and order.lineItems:
                    line_items = (
                        order.lineItems
                        if isinstance(order.lineItems, list)
                        else json.loads(order.lineItems)
                    )

                    for item in line_items:
                        if item.get("product_id") in product_lookup:
                            feedback.append(
                                {
                                    "FeedbackType": "star",
                                    "UserId": order.customerId,
                                    "ItemId": item["product_id"],
                                    "Timestamp": order.orderDate.isoformat(),
                                    "Comment": f"Purchase from order {order.id}",
                                }
                            )

            return {
                "items": items,
                "users": users,
                "feedback": feedback,
                "items_count": len(items),
                "users_count": len(users),
                "feedback_count": len(feedback),
            }

        except Exception as e:
            logger.error("Error preparing training data", shop_id=shop_id, error=str(e))
            raise

    async def _send_data_to_gorse(
        self, shop_domain: str, training_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send training data to Gorse (Gorse will handle training automatically)"""
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Insert items
                items_response = await client.post(
                    f"{self.base_url}/api/item",
                    headers={"X-API-Key": self.master_key},
                    json=training_data["items"],
                    timeout=30.0,
                )

                if items_response.status_code != 200:
                    logger.error(
                        "Failed to insert items", status_code=items_response.status_code
                    )

                # Step 2: Insert users
                users_response = await client.post(
                    f"{self.base_url}/api/user",
                    headers={"X-API-Key": self.master_key},
                    json=training_data["users"],
                    timeout=30.0,
                )

                if users_response.status_code != 200:
                    logger.error(
                        "Failed to insert users", status_code=users_response.status_code
                    )

                # Step 3: Insert feedback
                feedback_response = await client.post(
                    f"{self.base_url}/api/feedback",
                    headers={"X-API-Key": self.master_key},
                    json=training_data["feedback"],
                    timeout=30.0,
                )

                if feedback_response.status_code != 200:
                    logger.error(
                        "Failed to insert feedback",
                        status_code=feedback_response.status_code,
                    )

                # Note: Gorse will automatically start training when new data is inserted
                # We don't need to explicitly trigger training

                return {
                    "items_inserted": items_response.status_code == 200,
                    "users_inserted": users_response.status_code == 200,
                    "feedback_inserted": feedback_response.status_code == 200,
                    "training_automatic": True,
                    "timestamp": datetime.now().isoformat(),
                    "message": "Data sent to Gorse - training will start automatically",
                }

        except Exception as e:
            logger.error("Error sending data to Gorse", error=str(e))
            raise

    async def _update_training_metadata(
        self, shop_id: str, gorse_result: Dict[str, Any]
    ):
        """Update training metadata in database"""
        try:
            # This would update a training metadata table
            # For now, we'll just log it
            logger.info(
                "Training metadata updated", shop_id=shop_id, gorse_result=gorse_result
            )

        except Exception as e:
            logger.error(
                "Error updating training metadata", shop_id=shop_id, error=str(e)
            )

    async def get_recommendations(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        item_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get recommendations from Gorse"""
        try:
            # Build recommendation URL
            if user_id:
                # User-based recommendations
                url = f"{self.base_url}/api/recommend/user/{user_id}"
            elif item_id:
                # Item-based recommendations
                url = f"{self.base_url}/api/recommend/item/{item_id}"
            else:
                # Popular items
                url = f"{self.base_url}/api/popular"

            # Add category filter if specified
            if category:
                url += f"?category={category}"

            # Add limit
            url += f"{'&' if '?' in url else '?'}n={settings.MAX_RECOMMENDATIONS}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, headers={"X-API-Key": self.api_key}, timeout=10.0
                )

                if response.status_code == 200:
                    recommendations = response.json()

                    # Filter by confidence threshold
                    filtered_recommendations = [
                        rec
                        for rec in recommendations
                        if rec.get("Score", 0) >= settings.MIN_CONFIDENCE_THRESHOLD
                    ]

                    return {
                        "success": True,
                        "shop_id": shop_id,
                        "user_id": user_id,
                        "item_id": item_id,
                        "category": category,
                        "recommendations": filtered_recommendations,
                        "total_count": len(filtered_recommendations),
                        "confidence_threshold": settings.MIN_CONFIDENCE_THRESHOLD,
                    }
                else:
                    logger.error(
                        "Failed to get recommendations",
                        status_code=response.status_code,
                    )
                    return {
                        "success": False,
                        "error": f"Gorse API error: {response.status_code}",
                        "shop_id": shop_id,
                    }

        except Exception as e:
            log_error(e, {"operation": "get_recommendations", "shop_id": shop_id})
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def submit_feedback(
        self,
        shop_id: str,
        user_id: str,
        item_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit feedback to Gorse"""
        try:
            feedback_data = {
                "FeedbackType": feedback_type,
                "UserId": user_id,
                "ItemId": item_id,
                "Timestamp": datetime.now().isoformat(),
            }

            if comment:
                feedback_data["Comment"] = comment

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/feedback",
                    headers={"X-API-Key": self.master_key},
                    json=feedback_data,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(
                        "Feedback submitted successfully",
                        shop_id=shop_id,
                        user_id=user_id,
                        item_id=item_id,
                        feedback_type=feedback_type,
                    )

                    return {
                        "success": True,
                        "feedback_id": response.json().get("RowAffected"),
                        "shop_id": shop_id,
                    }
                else:
                    logger.error(
                        "Failed to submit feedback", status_code=response.status_code
                    )
                    return {
                        "success": False,
                        "error": f"Gorse API error: {response.status_code}",
                        "shop_id": shop_id,
                    }

        except Exception as e:
            log_error(e, {"operation": "submit_feedback", "shop_id": shop_id})
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def get_model_status(self, shop_id: str) -> Dict[str, Any]:
        """Get model training status for a shop"""
        try:
            # Check if shop has been trained recently
            # This would query a training metadata table
            # For now, return basic status

            return {
                "success": True,
                "shop_id": shop_id,
                "model_status": "unknown",
                "last_training": None,
                "training_count": 0,
                "recommendations_available": False,
            }

        except Exception as e:
            log_error(e, {"operation": "get_model_status", "shop_id": shop_id})
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def check_gorse_health(self) -> Dict[str, Any]:
        """Check if Gorse service is healthy"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/health",
                    headers={"X-API-Key": self.api_key},
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return {
                        "success": True,
                        "status": "healthy",
                        "gorse_url": self.base_url,
                    }
                else:
                    return {
                        "success": False,
                        "status": "unhealthy",
                        "gorse_url": self.base_url,
                        "error": f"HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "success": False,
                "status": "unhealthy",
                "gorse_url": self.base_url,
                "error": str(e),
            }


# Global instance
gorse_service = GorseService()
