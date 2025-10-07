from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from app.shared.helpers.datetime_utils import now_utc

from app.core.redis_client import get_redis_client
from app.core.database.session import get_transaction_context
from app.core.database.models.product_data import ProductData
from app.core.database.models.order_data import OrderData
from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.config.settings import settings
from sqlalchemy import select, and_, or_

logger = get_logger(__name__)

gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


class UserNeighborsService:
    """Service to handle user neighbors and their purchase data for collaborative filtering"""

    def __init__(self):
        self.gorse_client = gorse_client
        self.redis_client = None

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
            # Query recent orders from neighbor users
            # We'll look at orders from the last 90 days to get recent purchases
            cutoff_date = now_utc() - timedelta(days=90)

            async with get_transaction_context() as session:
                # Get orders from neighbor users
                orders_result = await session.execute(
                    select(OrderData)
                    .where(
                        and_(
                            OrderData.shop_id == shop_id,
                            OrderData.customer_id.in_(neighbor_user_ids),
                            OrderData.created_at >= cutoff_date,
                        )
                    )
                    .order_by(OrderData.created_at.desc())
                    .limit(limit * 2)
                )
                orders = orders_result.scalars().all()

                # Extract product IDs from order line items
                product_ids = []
                for order in orders:
                    if order.line_items:
                        for line_item in order.line_items:
                            if isinstance(line_item, dict) and line_item.get(
                                "productId"
                            ):
                                product_ids.append(line_item["productId"])
                            elif isinstance(line_item, str):
                                # Handle case where lineItems might be stored differently
                                product_ids.append(line_item)

                # If we have category filter, filter products by category within the same session
                if category and product_ids:
                    filtered_products = (
                        await self._filter_products_by_category_in_session(
                            session, product_ids, shop_id, category
                        )
                    )
                    return filtered_products[:limit]

                return product_ids[:limit]

        except Exception as e:
            logger.error(f"Failed to get neighbor purchases: {str(e)}")
            return []

    async def _filter_products_by_category_in_session(
        self, session, product_ids: List[str], shop_id: str, category: str
    ) -> List[str]:
        """
        Filter products by category using an existing session

        Args:
            session: Existing database session
            product_ids: List of product IDs to filter
            shop_id: Shop ID
            category: Category to filter by

        Returns:
            List of product IDs matching the category
        """
        try:
            # Get products and filter by category
            products_result = await session.execute(
                select(ProductData).where(
                    and_(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(product_ids),
                        or_(
                            ProductData.product_type.ilike(f"%{category}%"),
                            ProductData.collections.contains([category]),
                        ),
                    )
                )
            )
            products = products_result.scalars().all()

            return [product.product_id for product in products]

        except Exception as e:
            logger.error(f"Failed to filter products by category: {str(e)}")
            return product_ids  # Return original list if filtering fails

    async def _filter_products_by_category(
        self, product_ids: List[str], shop_id: str, category: str
    ) -> List[str]:
        """
        Filter products by category (standalone method for backward compatibility)

        Args:
            product_ids: List of product IDs to filter
            shop_id: Shop ID
            category: Category to filter by

        Returns:
            List of product IDs matching the category
        """
        try:
            async with get_transaction_context() as session:
                return await self._filter_products_by_category_in_session(
                    session, product_ids, shop_id, category
                )

        except Exception as e:
            logger.error(f"Failed to filter products by category: {str(e)}")
            return product_ids  # Return original list if filtering fails
