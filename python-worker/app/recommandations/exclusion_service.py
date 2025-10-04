"""
Product Exclusion Service
Handles logic for excluding products from recommendations based on purchase history and cart interactions
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.logging import get_logger
from app.core.database.models.user_interaction import UserInteraction
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
                # Customer might want to buy again for someone else
                exclude_ids = (
                    await PurchaseHistoryService.get_recently_purchased_product_ids(
                        session=session,
                        shop_id=shop_id,
                        customer_id=user_id,
                        days=14,
                    )
                )
                logger.debug(
                    f"📦 Excluding {len(exclude_ids)} recent purchases (14 days) for cart context"
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
        """
        if not user_id:
            return []

        try:
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

    def apply_time_decay_filtering(
        self, cart_interactions: List[Any], user_id: str
    ) -> List[str]:
        """
        Apply time decay logic to determine which products to exclude from recommendations

        Time Decay Rules:
        - Last 2 hours: Always exclude (weight = 1.0)
        - Last 6 hours: Usually exclude (weight = 0.8)
        - Last 24 hours: Maybe exclude (weight = 0.5)
        - Last 48 hours: Rarely exclude (weight = 0.2)

        Args:
            cart_interactions: List of cart interactions from database
            user_id: User ID for logging

        Returns:
            List of product IDs to exclude from recommendations
        """
        try:
            now = datetime.now(timezone.utc)
            product_interactions = {}  # product_id -> list of interactions

            # Group interactions by product ID
            for interaction in cart_interactions:
                # Extract product ID from metadata
                metadata = interaction.metadata or {}
                product_id = None

                # Try different metadata structures for product ID
                if "product_id" in metadata:
                    product_id = metadata.get("product_id")
                elif "data" in metadata and "cartLine" in metadata["data"]:
                    cart_line = metadata["data"]["cartLine"]
                    if (
                        "merchandise" in cart_line
                        and "product" in cart_line["merchandise"]
                    ):
                        product_id = cart_line["merchandise"]["product"].get("id")
                elif "productId" in metadata:
                    product_id = metadata.get("productId")

                if not product_id:
                    continue

                if product_id not in product_interactions:
                    product_interactions[product_id] = []

                # Ensure timestamp is timezone-aware
                timestamp = interaction.createdAt
                if timestamp.tzinfo is None:
                    # If timestamp is naive, assume it's UTC
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                elif timestamp.tzinfo != timezone.utc:
                    # Convert to UTC if it's in a different timezone
                    timestamp = timestamp.astimezone(timezone.utc)

                product_interactions[product_id].append(
                    {
                        "timestamp": timestamp,
                        "session_id": interaction.sessionId,
                    }
                )

            logger.debug(
                f"🔍 Time decay analysis for {len(product_interactions)} unique products"
            )

            excluded_products = []

            for product_id, interactions in product_interactions.items():
                # Get the most recent interaction for this product
                most_recent = max(interactions, key=lambda x: x["timestamp"])
                hours_ago = (now - most_recent["timestamp"]).total_seconds() / 3600

                # Count total interactions for this product
                interaction_count = len(interactions)

                # Apply industry-standard time decay logic
                # Industry best practice: Only exclude items currently in cart or very recently purchased
                should_exclude = False
                reason = ""

                # Industry standard: Only exclude items that are currently in cart (very recent)
                if hours_ago < 0.01:  # Last ~36 seconds - likely current cart item
                    should_exclude = True
                    reason = f"current_cart_item_{hours_ago:.1f}h"
                else:
                    # Don't exclude recently interacted items; handle recency in ranking, not filtering
                    reason = f"included_{hours_ago:.1f}h"

                if should_exclude:
                    excluded_products.append(product_id)
                    logger.debug(
                        f"🚫 Excluding product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
                    )
                else:
                    logger.debug(
                        f"✅ Including product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
                    )

            return excluded_products

        except Exception as e:
            logger.error(f"💥 Time decay filtering failed: {str(e)}")
            # Fallback: exclude all products from last 24 hours
            fallback_exclusions = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            for interaction in cart_interactions:
                if interaction.productId:
                    # Ensure timestamp is timezone-aware for comparison
                    timestamp = interaction.createdAt
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    elif timestamp.tzinfo != timezone.utc:
                        timestamp = timestamp.astimezone(timezone.utc)

                    if timestamp >= cutoff_time:
                        fallback_exclusions.append(interaction.productId)
            return list(set(fallback_exclusions))

    async def get_cart_time_decay_exclusions(
        self, session: AsyncSession, shop_id: str, user_id: str
    ) -> List[str]:
        """
        Get cart-based exclusions using time decay filtering
        """
        try:
            # Get cart interactions from the last 48 hours for time decay analysis
            cart_interactions_result = await session.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.customer_id == user_id,
                        UserInteraction.interaction_type.in_(
                            [
                                "product_added_to_cart",
                                "product_removed_from_cart",
                            ]
                        ),
                        UserInteraction.created_at
                        >= datetime.utcnow() - timedelta(hours=48),
                    )
                )
                .order_by(desc(UserInteraction.created_at))
                .limit(100)
            )
            cart_interactions = cart_interactions_result.scalars().all()

            # Apply time decay logic to determine which products to exclude
            return self.apply_time_decay_filtering(cart_interactions, user_id)

        except Exception as e:
            logger.warning(f"⚠️ Failed to get cart contents for user {user_id}: {e}")
            return []
