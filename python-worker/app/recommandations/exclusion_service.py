"""
Product Exclusion Service
Handles logic for excluding products from recommendations based on purchase history and cart interactions
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any, Dict

from app.shared.helpers.datetime_utils import now_utc

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.logging import get_logger
from app.core.database.models.product_data import ProductData
from app.recommandations.purchase_history import PurchaseHistoryService

logger = get_logger(__name__)


class ProductExclusionService:
    """Service for managing product exclusions from recommendations"""

    async def get_purchase_exclusions(
        self,
        session: AsyncSession,
        shop_id: str,
        user_id: Optional[str],
        context: str,
    ) -> List[str]:
        """
        Get product IDs to exclude based on purchase history.

        Args:
            session: Database session
            shop_id: Shop ID
            user_id: User/Customer ID
            context: Recommendation context

        Returns:
            List of product IDs to exclude from recommendations
        """
        if not user_id:
            return []

        try:
            # Different exclusion strategies based on context
            if context in ["order_history", "order_status"]:
                # For order-related contexts, be less aggressive with exclusions
                # Only exclude very recent purchases (last 30 days)
                exclude_ids = (
                    await PurchaseHistoryService.get_recently_purchased_product_ids(
                        session=session,
                        shop_id=shop_id,
                        customer_id=user_id,
                        days=30,
                    )
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} recent purchases (30 days) for context '{context}'"
                )

            elif context in ["product_page", "homepage", "profile"]:
                # For main browsing contexts, exclude all-time purchases
                # This prevents showing already-owned products
                exclude_ids = await PurchaseHistoryService.get_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                    exclude_refunded=True,
                    exclude_cancelled=True,
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} all-time purchases for context '{context}'"
                )

            elif context == "cart":
                # For cart, only exclude very recent purchases (last 14 days)
                exclude_ids = (
                    await PurchaseHistoryService.get_recently_purchased_product_ids(
                        session=session,
                        shop_id=shop_id,
                        customer_id=user_id,
                        days=14,
                    )
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} recent purchases (14 days) for context '{context}'"
                )

            elif context == "collection_page":
                # For collection page, exclude all-time purchases to show fresh products
                exclude_ids = await PurchaseHistoryService.get_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                    exclude_refunded=True,
                    exclude_cancelled=True,
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} all-time purchases for context '{context}'"
                )

            elif context == "post_purchase":
                # For post-purchase, we should NOT exclude historical purchases
                # Only exclude products from the CURRENT order (handled via request.product_ids)
                # This allows cross-sell/upsell recommendations to show through
                # Return empty list - current order products are excluded separately
                exclude_ids = []
                logger.debug(
                    "📦 Post-purchase context: Only excluding current order products (not historical purchases)"
                )

            else:
                # Default: exclude all-time purchases
                exclude_ids = await PurchaseHistoryService.get_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} all-time purchases for context '{context}'"
                )

            return exclude_ids

        except Exception as e:
            logger.error(f"⚠️ Failed to get purchase exclusions for user {user_id}: {e}")
            return []

    async def get_smart_purchase_exclusions(
        self,
        session: AsyncSession,
        shop_id: str,
        user_id: Optional[str],
        context: str,
        product_ids_to_check: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Smart purchase exclusions that consider product type.

        - Durable goods: Always exclude if purchased
        - Consumables: Only exclude recent purchases (last 60 days)
        - For post_purchase context: Only exclude very recent purchases (7 days)
        """
        if not user_id:
            return []

        try:
            # For post_purchase context, use context-aware exclusions (only recent purchases)
            if context == "post_purchase":
                logger.debug(
                    "🎯 Using context-aware exclusions for post_purchase (7 days only)"
                )
                return await self.get_purchase_exclusions(
                    session, shop_id, user_id, context
                )

            # Get all purchased products
            all_purchases = await PurchaseHistoryService.get_purchased_product_ids(
                session=session,
                shop_id=shop_id,
                customer_id=user_id,
            )

            # If we need to check specific products, fetch their types
            if product_ids_to_check:
                result = await session.execute(
                    select(ProductData.product_id, ProductData.product_type).where(
                        and_(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id.in_(product_ids_to_check),
                        )
                    )
                )
                product_types = {row.product_id: row.product_type for row in result}

                # Smart filtering
                exclude_ids = []
                for product_id in all_purchases:
                    product_type = product_types.get(product_id, "")
                    should_exclude = (
                        await PurchaseHistoryService.should_exclude_product(
                            session=session,
                            shop_id=shop_id,
                            customer_id=user_id,
                            product_id=product_id,
                            product_type=product_type,
                        )
                    )
                    if should_exclude:
                        exclude_ids.append(product_id)

                logger.debug(
                    f"🧠 Smart exclusions: {len(exclude_ids)}/{len(all_purchases)} products excluded"
                )
                return exclude_ids

            # Default: exclude all purchases
            return all_purchases

        except Exception as e:
            logger.error(f"⚠️ Smart exclusions failed: {e}")
            # Fallback to basic exclusion
            return await self.get_purchase_exclusions(
                session, shop_id, user_id, context
            )

