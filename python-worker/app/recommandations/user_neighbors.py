from typing import Any, Dict, List, Optional
from app.core.redis_client import get_redis_client
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.config.settings import settings

logger = get_logger(__name__)

gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


class UserNeighborsService:
    """Service to handle user neighbors and their purchase data for collaborative filtering"""

    def __init__(self):
        self.gorse_client = gorse_client
        self.db = None
        self.redis_client = None

    async def get_database(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def get_neighbor_recommendations(
        self, user_id: str, shop_id: str, limit: int = 6, category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recommendations based on similar users' purchases

        Args:
            user_id: User ID to find neighbors for
            shop_id: Shop ID
            limit: Number of recommendations to return
            category: Category filter

        Returns:
            Dict with neighbor-based recommendations
        """
        try:
            # Apply shop prefix for multi-tenancy (same as other services)
            prefixed_user_id = f"shop_{shop_id}_{user_id}"
            logger.debug(
                f"🔍 Getting user neighbors for prefixed user: {prefixed_user_id}"
            )

            # Get user neighbors from Gorse
            neighbors_result = await self.gorse_client.get_user_neighbors(
                prefixed_user_id, n=10
            )

            if not neighbors_result["success"] or not neighbors_result["neighbors"]:
                logger.warning(f"No user neighbors found for user {user_id}")
                return {
                    "success": False,
                    "items": [],
                    "source": "user_neighbors_empty",
                    "error": "No user neighbors found",
                }

            # Extract neighbor user IDs
            neighbor_user_ids = [
                neighbor.get("Id", neighbor)
                for neighbor in neighbors_result["neighbors"]
            ]
            logger.debug(f"Found {len(neighbor_user_ids)} neighbors for user {user_id}")

            # Get recent purchases from neighbor users
            neighbor_items = await self._get_neighbor_purchases(
                neighbor_user_ids, shop_id, category, limit * 2  # Get more to filter
            )

            if not neighbor_items:
                logger.warning(f"No neighbor purchases found for user {user_id}")
                return {
                    "success": False,
                    "items": [],
                    "source": "user_neighbors_no_purchases",
                    "error": "No neighbor purchases found",
                }

            # Remove duplicates and limit results
            unique_items = list(
                dict.fromkeys(neighbor_items)
            )  # Preserve order, remove duplicates
            final_items = unique_items[:limit]

            logger.info(
                f"Generated {len(final_items)} neighbor-based recommendations for user {user_id}"
            )

            return {
                "success": True,
                "items": final_items,
                "source": "user_neighbors",
                "neighbor_count": len(neighbor_user_ids),
                "purchase_count": len(neighbor_items),
            }

        except Exception as e:
            logger.error(f"Failed to get neighbor recommendations: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "user_neighbors_error",
                "error": str(e),
            }

    async def _get_neighbor_purchases(
        self,
        neighbor_user_ids: List[str],
        shop_id: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[str]:
        """
        Get recent purchases from neighbor users

        Args:
            neighbor_user_ids: List of neighbor user IDs
            shop_id: Shop ID
            category: Category filter
            limit: Maximum number of items to return

        Returns:
            List of product IDs from neighbor purchases
        """
        try:
            db = await self.get_database()

            # Query recent orders from neighbor users
            # We'll look at orders from the last 90 days to get recent purchases
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=90)

            # Get orders from neighbor users
            orders = await db.orderdata.find_many(
                where={
                    "shopId": shop_id,
                    "customerId": {"in": neighbor_user_ids},
                    "createdAt": {"gte": cutoff_date},
                },
                take=limit * 2,  # Get more orders to ensure we have enough items
                order={"createdAt": "desc"},
            )

            # Extract product IDs from order line items
            product_ids = []
            for order in orders:
                if order.get("lineItems"):
                    for line_item in order["lineItems"]:
                        if isinstance(line_item, dict) and line_item.get("productId"):
                            product_ids.append(line_item["productId"])
                        elif isinstance(line_item, str):
                            # Handle case where lineItems might be stored differently
                            product_ids.append(line_item)

            # If we have category filter, filter products by category
            if category and product_ids:
                filtered_products = await self._filter_products_by_category(
                    product_ids, shop_id, category
                )
                return filtered_products[:limit]

            return product_ids[:limit]

        except Exception as e:
            logger.error(f"Failed to get neighbor purchases: {str(e)}")
            return []

    async def _filter_products_by_category(
        self, product_ids: List[str], shop_id: str, category: str
    ) -> List[str]:
        """
        Filter products by category

        Args:
            product_ids: List of product IDs to filter
            shop_id: Shop ID
            category: Category to filter by

        Returns:
            List of product IDs matching the category
        """
        try:
            db = await self.get_database()

            # Get products and filter by category
            products = await db.productdata.find_many(
                where={
                    "shopId": shop_id,
                    "productId": {"in": product_ids},
                    "OR": [
                        {"productType": {"contains": category, "mode": "insensitive"}},
                        {"collections": {"has": category}},
                    ],
                },
                select={"productId": True},
            )

            return [product["productId"] for product in products]

        except Exception as e:
            logger.error(f"Failed to filter products by category: {str(e)}")
            return product_ids  # Return original list if filtering fails
