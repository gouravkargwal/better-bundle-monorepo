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
    """
    Service for getting frequently bought together products with multiple images support
    """

    def _extract_images_from_media(
        self, media_data: Any, fallback_title: str
    ) -> List[Dict[str, str]] | None:
        """Extract all image URLs and alt text from media JSON data"""
        if not media_data or not isinstance(media_data, list) or len(media_data) == 0:
            return None

        images = []
        for i, media_item in enumerate(media_data):
            if isinstance(media_item, dict):
                # Check for direct image properties
                if "image" in media_item and isinstance(media_item["image"], dict):
                    image_data = media_item["image"]
                    images.append(
                        {
                            "url": image_data.get("url", ""),
                            "alt_text": image_data.get(
                                "altText", f"{fallback_title} - Image {i+1}"
                            ),
                            "type": "main" if i == 0 else "additional",
                            "position": i,
                        }
                    )
                # Check for direct URL properties
                elif "url" in media_item:
                    images.append(
                        {
                            "url": media_item.get("url", ""),
                            "alt_text": media_item.get(
                                "altText", f"{fallback_title} - Image {i+1}"
                            ),
                            "type": "main" if i == 0 else "additional",
                            "position": i,
                        }
                    )

        return images if images else None

    def _extract_image_from_media(
        self, media_data: Any, fallback_title: str
    ) -> Dict[str, str] | None:
        """Extract first image URL and alt text from media JSON data (backward compatibility)"""
        images = self._extract_images_from_media(media_data, fallback_title)
        return images[0] if images else None

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
            # Since order_id and product_id are stored in interaction_metadata JSON
            result = await session.execute(
                select(UserInteraction.interaction_metadata).where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.interaction_type == "checkout_completed",
                    )
                )
            )

            order_ids = []
            for row in result.fetchall():
                metadata = row[0] or {}
                # Check if this order contains the target product
                if self._order_contains_product(metadata, product_id):
                    order_id = metadata.get("order_id")
                    if order_id:
                        order_ids.append(str(order_id))

            return list(set(order_ids))  # Remove duplicates

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
            # Get all checkout completed events for the shop
            result = await session.execute(
                select(UserInteraction.interaction_metadata).where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.interaction_type == "checkout_completed",
                    )
                )
            )

            # Count co-occurrences of products in the same orders
            product_co_occurrences = {}

            for row in result.fetchall():
                metadata = row[0] or {}
                order_id = metadata.get("order_id")

                if order_id and str(order_id) in order_ids:
                    # Extract products from this order
                    products = self._extract_products_from_order(metadata)

                    for product_id in products:
                        if product_id != target_product_id:
                            if product_id not in product_co_occurrences:
                                product_co_occurrences[product_id] = 0
                            product_co_occurrences[product_id] += 1

            # Filter by minimum co-occurrences and sort
            co_purchased = []
            for product_id, count in product_co_occurrences.items():
                if count >= min_co_occurrences:
                    co_purchased.append(
                        {
                            "product_id": product_id,
                            "co_occurrences": count,
                        }
                    )

            # Sort by co-occurrences (descending)
            co_purchased.sort(key=lambda x: x["co_occurrences"], reverse=True)
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
                select(ProductData).where(
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
                    recommendations.append(
                        {
                            "id": product_id,
                            "title": product.title,
                            "handle": product.handle,
                            "price": {
                                "amount": str(product.price),
                            },
                            "image": self._extract_image_from_media(
                                product.media, product.title
                            ),
                            "images": self._extract_images_from_media(
                                product.media, product.title
                            ),
                            "available": product.available,
                            "url": f"/products/{product.handle}",
                            "co_occurrences": item["co_occurrences"],
                        }
                    )

            return recommendations

        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return []

    def _order_contains_product(
        self, metadata: Dict[str, Any], product_id: str
    ) -> bool:
        """Check if an order contains a specific product"""
        try:
            # Look for product in order line items
            line_items = metadata.get("line_items", [])
            for item in line_items:
                if isinstance(item, dict):
                    item_product_id = item.get("product_id")
                    if item_product_id == product_id:
                        return True
            return False
        except Exception:
            return False

    def _extract_products_from_order(self, metadata: Dict[str, Any]) -> List[str]:
        """Extract product IDs from order metadata"""
        try:
            products = []
            line_items = metadata.get("line_items", [])
            for item in line_items:
                if isinstance(item, dict):
                    product_id = item.get("product_id")
                    if product_id:
                        products.append(str(product_id))
            return products
        except Exception:
            return []
