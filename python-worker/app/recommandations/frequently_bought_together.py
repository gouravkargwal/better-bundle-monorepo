"""
Frequently Bought Together Recommendation Service
Analyzes purchase patterns to find products commonly bought together
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from app.core.logging import get_logger
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.product_data import ProductData
from app.core.database.session import get_transaction_context

logger = get_logger(__name__)


class FrequentlyBoughtTogetherService:
    """Service to find products frequently bought together with a given product"""

    async def get_frequently_bought_together(
        self,
        shop_id: str,
        product_id: str,
        limit: int = 4,
        min_co_occurrences: int = 2,
    ) -> Dict[str, Any]:
        """
        Find products frequently bought together with the given product
        
        Args:
            shop_id: Shop ID
            product_id: Product ID to find co-purchased items for
            limit: Maximum number of recommendations
            min_co_occurrences: Minimum number of co-purchases required
            
        Returns:
            Dict with frequently bought together recommendations
        """
        try:
            async with get_transaction_context() as session:
                # Get all orders that contain the target product
                orders_with_target = await self._get_orders_with_product(
                    session, shop_id, product_id
                )
                
                if not orders_with_target:
                    logger.warning(f"No orders found containing product {product_id}")
                    return {
                        "success": False,
                        "items": [],
                        "source": "frequently_bought_together_empty",
                        "error": "No co-purchase data available",
                    }

                # Find products frequently bought together
                co_purchased_products = await self._find_co_purchased_products(
                    session, shop_id, orders_with_target, product_id, min_co_occurrences
                )

                if not co_purchased_products:
                    logger.warning(f"No co-purchased products found for {product_id}")
                    return {
                        "success": False,
                        "items": [],
                        "source": "frequently_bought_together_empty",
                        "error": "No co-purchase patterns found",
                    }

                # Get product details for recommendations
                recommendations = await self._get_product_details(
                    session, shop_id, co_purchased_products[:limit]
                )

                return {
                    "success": True,
                    "items": recommendations,
                    "source": "frequently_bought_together",
                    "count": len(recommendations),
                }

        except Exception as e:
            logger.error(f"Error getting frequently bought together: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "frequently_bought_together_error",
                "error": str(e),
            }

    async def _get_orders_with_product(
        self, session: AsyncSession, shop_id: str, product_id: str
    ) -> List[str]:
        """Get order IDs that contain the target product"""
        try:
            # Get orders where the product was purchased
            result = await session.execute(
                select(UserInteraction.order_id)
                .where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.product_id == product_id,
                        UserInteraction.interaction_type == "product_purchased",
                        UserInteraction.order_id.isnot(None),
                    )
                )
                .distinct()
            )
            return [row[0] for row in result.fetchall() if row[0]]

        except Exception as e:
            logger.error(f"Error getting orders with product: {str(e)}")
            return []

    async def _find_co_purchased_products(
        self,
        session: AsyncSession,
        shop_id: str,
        order_ids: List[str],
        target_product_id: str,
        min_co_occurrences: int,
    ) -> List[Dict[str, Any]]:
        """Find products frequently bought together in the same orders"""
        try:
            # Get all products purchased in orders that contain the target product
            # Exclude the target product itself
            result = await session.execute(
                select(
                    UserInteraction.product_id,
                    func.count(UserInteraction.product_id).label("co_occurrences"),
                )
                .where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.order_id.in_(order_ids),
                        UserInteraction.interaction_type == "product_purchased",
                        UserInteraction.product_id != target_product_id,
                        UserInteraction.product_id.isnot(None),
                    )
                )
                .group_by(UserInteraction.product_id)
                .having(func.count(UserInteraction.product_id) >= min_co_occurrences)
                .order_by(desc("co_occurrences"))
            )

            co_purchased = []
            for row in result.fetchall():
                co_purchased.append({
                    "product_id": row.product_id,
                    "co_occurrences": row.co_occurrences,
                })

            return co_purchased

        except Exception as e:
            logger.error(f"Error finding co-purchased products: {str(e)}")
            return []

    async def _get_product_details(
        self, session: AsyncSession, shop_id: str, co_purchased: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get product details for co-purchased items"""
        try:
            if not co_purchased:
                return []

            product_ids = [item["product_id"] for item in co_purchased]
            
            # Get product data
            result = await session.execute(
                select(ProductData)
                .where(
                    and_(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(product_ids),
                    )
                )
            )

            products = result.scalars().all()
            
            # Create a mapping of product_id to product data
            product_map = {p.product_id: p for p in products}
            
            # Build recommendations with co-occurrence data
            recommendations = []
            for item in co_purchased:
                product_id = item["product_id"]
                if product_id in product_map:
                    product = product_map[product_id]
                    recommendations.append({
                        "id": product_id,
                        "title": product.title,
                        "handle": product.handle,
                        "price": {
                            "amount": str(product.price),
                            "currency_code": product.currency_code or "USD",
                        },
                        "image": {
                            "url": product.image_url,
                        } if product.image_url else None,
                        "available": product.available,
                        "url": f"/products/{product.handle}",
                        "co_occurrences": item["co_occurrences"],
                    })

            return recommendations

        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return []
