"""
Recently Viewed Products Service
Provides recently viewed products for returning visitors to create continuity
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.shared.helpers import now_utc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.core.logging import get_logger
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.product_data import ProductData
from app.core.database.session import get_transaction_context

logger = get_logger(__name__)


class RecentlyViewedService:
    """
    Service for getting recently viewed products with multiple images support
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

    async def get_recently_viewed_products(
        self,
        shop_id: str,
        user_id: str,
        limit: int = 6,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """
        Get recently viewed products for a returning visitor

        Args:
            shop_id: Shop ID
            user_id: User ID
            limit: Maximum number of recommendations
            days_back: How many days back to look for viewed products

        Returns:
            Dict with recently viewed product recommendations
        """
        try:
            async with get_transaction_context() as session:
                # Get recently viewed products
                recently_viewed = await self._get_recent_viewed_products(
                    session,
                    shop_id,
                    user_id,
                    days_back,
                    limit * 2,  # Get more to filter
                )

                if not recently_viewed:
                    logger.info(f"No recently viewed products found for user {user_id}")
                    return {
                        "success": False,
                        "items": [],
                        "source": "recently_viewed_empty",
                        "error": "No recently viewed products found",
                    }

                # Get product details for recommendations
                recommendations = await self._get_product_details(
                    session, shop_id, recently_viewed[:limit]
                )

                return {
                    "success": True,
                    "items": recommendations,
                    "source": "recently_viewed",
                    "count": len(recommendations),
                }

        except Exception as e:
            logger.error(f"Error getting recently viewed products: {str(e)}")
            return {
                "success": False,
                "items": [],
                "source": "recently_viewed_error",
                "error": str(e),
            }

    async def _get_recent_viewed_products(
        self,
        session: AsyncSession,
        shop_id: str,
        user_id: str,
        days_back: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Get recently viewed product IDs with timestamps"""
        try:
            cutoff_date = now_utc() - timedelta(days=days_back)

            # Get recent product views, ordered by most recent
            result = await session.execute(
                select(
                    UserInteraction.interaction_metadata,
                    UserInteraction.created_at,
                    UserInteraction.interaction_type,
                )
                .where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.customer_id == user_id,
                        UserInteraction.interaction_type == "product_viewed",
                        UserInteraction.interaction_metadata["productId"].astext.isnot(
                            None
                        ),
                        UserInteraction.created_at >= cutoff_date,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
                .limit(limit)
            )

            viewed_products = []
            seen_products = set()

            for row in result.fetchall():
                # Extract product_id from interaction metadata
                metadata = row.interaction_metadata or {}
                product_id = metadata.get("productId")
                if product_id and product_id not in seen_products:
                    viewed_products.append(
                        {
                            "product_id": product_id,
                            "viewed_at": row.created_at,
                            "interaction_type": row.interaction_type,
                        }
                    )
                    seen_products.add(product_id)

            return viewed_products

        except Exception as e:
            logger.error(f"Error getting recent viewed products: {str(e)}")
            return []

    async def _get_product_details(
        self, session: AsyncSession, shop_id: str, viewed_products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get product details for recently viewed items"""
        try:
            if not viewed_products:
                return []

            product_ids = [item["product_id"] for item in viewed_products]

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

            # Build recommendations maintaining the viewed order
            recommendations = []
            for viewed_item in viewed_products:
                product_id = viewed_item["product_id"]
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
                            "viewed_at": viewed_item["viewed_at"].isoformat(),
                        }
                    )

            return recommendations

        except Exception as e:
            logger.error(f"Error getting product details: {str(e)}")
            return []
