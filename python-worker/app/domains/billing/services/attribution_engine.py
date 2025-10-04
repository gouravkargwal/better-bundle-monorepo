"""
Attribution Engine for Billing System

This service calculates attribution for purchases based on customer interactions
with recommendations across different extensions.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import UserInteraction, UserSession, PurchaseAttribution
from app.core.database.session import get_session_context

from ..models.attribution_models import (
    AttributionResult,
    AttributionBreakdown,
    AttributionRule,
    AttributionConfig,
    UserInteraction as AttributionUserInteraction,
    PurchaseEvent,
    AttributionType,
    AttributionStatus,
    ExtensionType,
    InteractionType,
    AttributionMetrics,
)
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory

logger = logging.getLogger(__name__)


@dataclass
class AttributionContext:
    """Context for attribution calculation"""

    shop_id: str
    customer_id: Optional[str]
    session_id: Optional[str]
    order_id: str
    purchase_amount: Decimal
    purchase_products: List[Dict[str, Any]]
    purchase_time: datetime


class AttributionEngine:
    """
    Core attribution engine that calculates which extensions should get credit
    for driving purchases.
    """

    def __init__(self, session: AsyncSession = None):
        self.session = session
        self.adapter_factory = InteractionEventAdapterFactory()
        self.default_rules = self._get_default_attribution_rules()

    async def calculate_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """
        Calculate attribution for a purchase event.

        Args:
            context: Attribution context with purchase and customer data

        Returns:
            AttributionResult with detailed breakdown
        """
        try:
            logger.info(
                f"🔍 Starting attribution calculation for order {context.order_id}"
            )
            logger.info(
                f"🔍 Context: shop_id={context.shop_id}, customer_id={context.customer_id}, session_id={context.session_id}"
            )
            logger.info(
                f"🔍 Purchase amount: {context.purchase_amount}, Products: {len(context.purchase_products)}"
            )

            # 1. Get all interactions for this customer/session
            interactions = await self._get_relevant_interactions(context)
            logger.info(
                f"📊 Found {len(interactions)} interactions for order {context.order_id}"
            )

            if not interactions:
                logger.warning(f"⚠️ No interactions found for order {context.order_id}")
                return self._create_empty_attribution(context)

            # 3. Calculate attribution breakdown
            logger.info(
                f"🧮 Calculating attribution breakdown for {len(interactions)} interactions"
            )
            attribution_breakdown = self._calculate_attribution_breakdown(
                context, interactions
            )
            logger.info(
                f"💰 Generated {len(attribution_breakdown)} attribution breakdown items"
            )

            # 4. Create attribution result
            # Calculate total attributed revenue (should be 0 if no attribution-eligible interactions)
            total_attributed_revenue = sum(
                breakdown.attributed_amount for breakdown in attribution_breakdown
            )

            # If no attribution found, still count the total purchase amount for revenue tracking
            if total_attributed_revenue == 0 and attribution_breakdown:
                # This means attribution was calculated but resulted in 0
                total_attributed_revenue = Decimal("0.00")
            elif total_attributed_revenue == 0 and not attribution_breakdown:
                # No attribution-eligible interactions found, but still count total revenue
                total_attributed_revenue = context.purchase_amount
                logger.info(
                    f"💰 No attribution-eligible interactions found, counting total purchase amount: ${total_attributed_revenue}"
                )

            result = AttributionResult(
                order_id=context.order_id,
                shop_id=context.shop_id,
                customer_id=context.customer_id,
                session_id=context.session_id,
                total_attributed_revenue=total_attributed_revenue,
                attribution_breakdown=attribution_breakdown,
                attribution_type=AttributionType.DIRECT_CLICK,
                status=AttributionStatus.CALCULATED,
                calculated_at=datetime.utcnow(),
                metadata={
                    "interaction_count": len(interactions),
                    "calculation_method": "multi_touch_attribution",
                },
            )

            # 5. Store attribution result
            logger.info(f"💾 Storing attribution result for order {context.order_id}")
            await self._store_attribution_result(result)
            logger.info(
                f"✅ Attribution calculation completed for order {context.order_id}"
            )
            logger.info(
                f"💰 Final attribution for order {context.order_id}: "
                f"${result.total_attributed_revenue} across {len(result.attribution_breakdown)} items"
            )

            return result

        except Exception as e:
            logger.error(
                f"Error calculating attribution for order {context.order_id}: {e}"
            )
            return self._create_error_attribution(context, str(e))

    async def _get_relevant_interactions(
        self, context: AttributionContext
    ) -> List[Dict[str, Any]]:
        """Get all relevant interactions for attribution calculation."""
        # Time window for attribution (30 days)
        time_window = timedelta(hours=720)
        start_time = context.purchase_time - time_window

        logger.info(
            f"Searching interactions from {start_time} to {context.purchase_time}"
        )

        try:
            # Use provided session or create new context
            if self.session:
                return await self._fetch_interactions(self.session, context, start_time)
            else:
                async with get_session_context() as session:
                    return await self._fetch_interactions(session, context, start_time)

        except Exception as e:
            logger.error(f"Error fetching interactions: {str(e)}")
            return []

    async def _fetch_interactions(
        self, session: AsyncSession, context: AttributionContext, start_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch interactions from database using provided session."""
        # Build query
        query = select(UserInteraction).where(
            and_(
                UserInteraction.shop_id == context.shop_id,
                UserInteraction.created_at >= start_time,
                UserInteraction.created_at <= context.purchase_time,
            )
        )

        # Add customer or session filter
        if context.customer_id:
            query = query.where(UserInteraction.customer_id == context.customer_id)
            logger.info(f"Filtering by customer_id: {context.customer_id}")
        elif context.session_id:
            query = query.where(UserInteraction.session_id == context.session_id)
            logger.info(f"Filtering by session_id: {context.session_id}")

        # Execute query
        result = await session.execute(
            query.order_by(UserInteraction.created_at.desc())
        )
        interactions = result.scalars().all()

        logger.info(f"Retrieved {len(interactions)} interactions from database")

        # Convert SQLAlchemy models to dicts for compatibility
        return [
            {
                "id": i.id,
                "shop_id": i.shop_id,
                "customer_id": i.customer_id,
                "session_id": i.session_id,
                "interaction_type": i.interaction_type,
                "extension_type": i.extension_type,
                "created_at": i.created_at,
                "metadata": i.interaction_metadata or {},
            }
            for i in interactions
        ]

    def _calculate_attribution_breakdown(
        self, context: AttributionContext, interactions: List[Dict[str, Any]]
    ) -> List[AttributionBreakdown]:
        """
        Calculate attribution breakdown based on interactions.

        Args:
            context: Attribution context
            interactions: List of relevant interactions

        Returns:
            List of attribution breakdowns
        """
        logger.info(
            f"🧮 Starting attribution breakdown calculation for {len(interactions)} interactions"
        )
        breakdowns = []

        # Group interactions by product
        product_interactions = self._group_interactions_by_product(interactions)
        logger.info(
            f"📦 Grouped interactions into {len(product_interactions)} product buckets"
        )

        # Calculate attribution for each product in the purchase
        logger.info(
            f"🛒 Processing {len(context.purchase_products)} products from purchase"
        )
        logger.info(f"🔍 Purchase products data: {context.purchase_products}")
        for product in context.purchase_products:
            product_id = product.get("id")
            unit_price = Decimal(str(product.get("price", 0)))
            quantity = int(product.get("quantity", 1))
            product_amount = (
                unit_price * quantity
            )  # ✅ FIX: Use total amount (unit_price × quantity)

            logger.info(
                f"🔍 Processing product {product_id} with unit price ${unit_price}, quantity {quantity}, total amount ${product_amount}"
            )

            if not product_id or product_amount <= 0:
                logger.warning(
                    f"⚠️ Skipping product {product_id} - invalid ID or amount"
                )
                continue

            # Find interactions for this product
            product_interaction_list = product_interactions.get(product_id, [])

            if not product_interaction_list:
                continue

            # Calculate attribution for this product
            product_attribution = self._calculate_product_attribution(
                product_id, product_amount, product_interaction_list
            )

            if product_attribution:
                breakdowns.extend(product_attribution)

        return breakdowns

    def _group_interactions_by_product(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group interactions by product ID, filtering for attribution-eligible extensions.

        Args:
            interactions: List of interactions

        Returns:
            Dictionary mapping product_id to list of interactions
        """
        product_interactions = {}

        # Filter for extensions that can track attribution
        attribution_eligible_extensions = {
            ExtensionType.PHOENIX.value,  # Recommendation engine
            ExtensionType.VENUS.value,  # Customer account extensions
            ExtensionType.APOLLO.value,  # Post-purchase extensions
        }

        # Filter for interaction types that can track attribution
        attribution_eligible_interactions = {
            "recommendation_add_to_cart",  # Only add_to_cart events get attribution
            "recommendation_clicked",  # Click events can also get attribution
        }

        for interaction in interactions:

            # Skip ATLAS interactions (web pixel) - they don't drive conversions
            if interaction["extension_type"] == ExtensionType.ATLAS.value:
                continue

            # Only process interactions from attribution-eligible extensions
            if interaction["extension_type"] not in attribution_eligible_extensions:
                continue

            # Only process interaction types that can track attribution
            if interaction["interaction_type"] not in attribution_eligible_interactions:
                continue

            # Extract product_id using adapter factory
            product_id = None
            try:
                # Convert interaction dict format for adapter
                interaction_dict = {
                    "interactionType": interaction["interaction_type"],
                    "metadata": interaction["metadata"],
                    "customerId": interaction["customer_id"],
                    "sessionId": interaction["session_id"],
                    "shopId": interaction["shop_id"],
                    "createdAt": interaction["created_at"],
                }

                # Extract product ID using adapter factory for all extensions
                product_id = self.adapter_factory.extract_product_id(interaction_dict)

                # Debug: Log Phoenix interaction structure if no product_id found
                if (
                    interaction["extension_type"] == ExtensionType.PHOENIX.value
                    and not product_id
                ):
                    logger.info(f"🔍 PHOENIX DEBUG - Interaction {interaction['id']}:")
                    logger.info(
                        f"🔍 PHOENIX DEBUG - interaction_type: {interaction['interaction_type']}"
                    )
                    logger.info(
                        f"🔍 PHOENIX DEBUG - metadata keys: {list(interaction['metadata'].keys())}"
                    )
                    logger.info(
                        f"🔍 PHOENIX DEBUG - metadata: {interaction['metadata']}"
                    )
                    logger.info(
                        f"🔍 PHOENIX DEBUG - interaction_dict: {interaction_dict}"
                    )

                logger.info(
                    f"🔍 Extracted product_id: {product_id} for {interaction['extension_type']} interaction {interaction['id']}"
                )

                if product_id:
                    if product_id not in product_interactions:
                        product_interactions[product_id] = []
                    product_interactions[product_id].append(interaction)
                    logger.info(
                        f"✅ Added {interaction['extension_type']} interaction for product {product_id}"
                    )
                else:
                    logger.info(
                        f"❌ No product_id extracted for {interaction['extension_type']} interaction {interaction['id']}"
                    )

            except Exception as e:
                logger.warning(
                    f"Error extracting product_id from interaction {interaction['id']}: {e}"
                )
                continue

        return product_interactions

    def _calculate_product_attribution(
        self,
        product_id: str,
        product_amount: Decimal,
        interactions: List[Dict[str, Any]],
    ) -> List[AttributionBreakdown]:
        """
        Calculate attribution for a specific product.

        Args:
            product_id: Product ID
            product_amount: Product amount
            interactions: List of interactions for this product

        Returns:
            List of attribution breakdowns
        """
        if not interactions:
            return []

        # Sort interactions by time (most recent first)
        interactions.sort(key=lambda x: x["created_at"], reverse=True)

        # Apply attribution rules
        if len(interactions) == 1:
            # Single interaction - direct attribution
            return self._create_direct_attribution(
                product_id, product_amount, interactions[0]
            )
        else:
            # Multiple interactions - cross-extension attribution
            return self._create_cross_extension_attribution(
                product_id, product_amount, interactions
            )

    def _create_direct_attribution(
        self, product_id: str, product_amount: Decimal, interaction: Dict[str, Any]
    ) -> List[AttributionBreakdown]:
        """
        Create direct attribution for a single interaction.

        Args:
            product_id: Product ID
            product_amount: Product amount
            interaction: The interaction

        Returns:
            List with single attribution breakdown
        """
        return [
            AttributionBreakdown(
                extension_type=ExtensionType(interaction["extension_type"]),
                product_id=product_id,
                attributed_amount=product_amount,
                attribution_weight=1.0,
                attribution_type=AttributionType.DIRECT_CLICK,
                interaction_id=interaction["id"],
                metadata={
                    "interaction_type": interaction["interaction_type"],
                    "recommendation_position": interaction["metadata"].get(
                        "recommendation_position"
                    ),
                    "created_at": interaction["created_at"].isoformat(),
                },
            )
        ]

    def _create_cross_extension_attribution(
        self,
        product_id: str,
        product_amount: Decimal,
        interactions: List[Dict[str, Any]],
    ) -> List[AttributionBreakdown]:
        """
        Create cross-extension attribution for multiple interactions.

        Args:
            product_id: Product ID
            product_amount: Product amount
            interactions: List of interactions (sorted by time)

        Returns:
            List of attribution breakdowns
        """
        breakdowns = []

        # Primary interaction (most recent click)
        primary_interaction = interactions[0]
        primary_amount = product_amount * Decimal("0.7")  # 70% to primary

        breakdowns.append(
            AttributionBreakdown(
                extension_type=ExtensionType(primary_interaction["extension_type"]),
                product_id=product_id,
                attributed_amount=primary_amount,
                attribution_weight=0.7,
                attribution_type=AttributionType.CROSS_EXTENSION,
                interaction_id=primary_interaction["id"],
                metadata={
                    "interaction_type": primary_interaction["interaction_type"],
                    "recommendation_position": primary_interaction["metadata"].get(
                        "recommendation_position"
                    ),
                    "created_at": primary_interaction["created_at"].isoformat(),
                    "attribution_role": "primary",
                },
            )
        )

        # Secondary interactions (30% distributed among others)
        secondary_interactions = interactions[1:]
        if secondary_interactions:
            secondary_amount = product_amount * Decimal("0.3")
            amount_per_interaction = secondary_amount / len(secondary_interactions)

            for interaction in secondary_interactions:
                breakdowns.append(
                    AttributionBreakdown(
                        extension_type=ExtensionType(interaction["extension_type"]),
                        product_id=product_id,
                        attributed_amount=amount_per_interaction,
                        attribution_weight=0.3 / len(secondary_interactions),
                        attribution_type=AttributionType.CROSS_EXTENSION,
                        interaction_id=interaction["id"],
                        metadata={
                            "interaction_type": interaction["interaction_type"],
                            "recommendation_position": interaction["metadata"].get(
                                "recommendation_position"
                            ),
                            "created_at": interaction["created_at"].isoformat(),
                            "attribution_role": "secondary",
                        },
                    )
                )

        return breakdowns

    async def _store_attribution_result(self, result: AttributionResult) -> None:
        """
        Store attribution result in database.

        Args:
            result: Attribution result to store
        """
        try:
            # Prepare attribution data
            contributing_extensions = [
                {
                    "extension_type": breakdown.extension_type.value,
                    "product_id": breakdown.product_id,
                    "attributed_amount": float(breakdown.attributed_amount),
                    "attribution_weight": breakdown.attribution_weight,
                }
                for breakdown in result.attribution_breakdown
            ]

            attribution_weights = {
                breakdown.extension_type.value: breakdown.attribution_weight
                for breakdown in result.attribution_breakdown
            }

            attributed_revenue = {
                breakdown.extension_type.value: float(breakdown.attributed_amount)
                for breakdown in result.attribution_breakdown
            }

            interactions_by_extension = {
                breakdown.extension_type.value: 1
                for breakdown in result.attribution_breakdown
            }

            # Use provided session or create new context
            if self.session:
                await self._save_attribution(
                    self.session,
                    result,
                    contributing_extensions,
                    attribution_weights,
                    attributed_revenue,
                    interactions_by_extension,
                )
            else:
                async with get_session_context() as session:
                    await self._save_attribution(
                        session,
                        result,
                        contributing_extensions,
                        attribution_weights,
                        attributed_revenue,
                        interactions_by_extension,
                    )

            logger.info(f"Stored attribution result for order {result.order_id}")

        except Exception as e:
            if (
                "Unique constraint failed" in str(e)
                or "duplicate key" in str(e).lower()
            ):
                logger.info(
                    f"Attribution already exists for order {result.order_id}, skipping storage"
                )
                return
            logger.error(
                f"Error storing attribution result for order {result.order_id}: {e}"
            )
            raise

    async def _save_attribution(
        self,
        session: AsyncSession,
        result: AttributionResult,
        contributing_extensions: List[Dict],
        attribution_weights: Dict,
        attributed_revenue: Dict,
        interactions_by_extension: Dict,
    ) -> None:
        """Save attribution to database using provided session."""
        # Check if attribution already exists
        stmt = select(PurchaseAttribution).where(
            and_(
                PurchaseAttribution.shop_id == result.shop_id,
                PurchaseAttribution.order_id == str(result.order_id),
            )
        )
        result_check = await session.execute(stmt)
        existing_attribution = result_check.scalar_one_or_none()

        if existing_attribution:
            logger.info(
                f"Attribution already exists for order {result.order_id}, skipping storage"
            )
            return

        # Create new attribution record
        attribution = PurchaseAttribution(
            session_id=result.session_id or "",
            order_id=str(result.order_id),
            customer_id=result.customer_id,
            shop_id=result.shop_id,
            contributing_extensions=contributing_extensions,
            attribution_weights=attribution_weights,
            total_revenue=float(result.total_attributed_revenue),
            attributed_revenue=attributed_revenue,
            total_interactions=len(result.attribution_breakdown),
            interactions_by_extension=interactions_by_extension,
            purchase_at=result.calculated_at,
            attribution_algorithm=result.attribution_type.value,
            attribution_metadata=result.metadata,
        )

        session.add(attribution)
        await session.commit()

    def _create_empty_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """Create empty attribution result when no interactions found."""
        return AttributionResult(
            order_id=context.order_id,
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.CALCULATED,
            calculated_at=datetime.utcnow(),
            metadata={"reason": "no_interactions_found"},
        )

    def _create_error_attribution(
        self, context: AttributionContext, error_message: str
    ) -> AttributionResult:
        """Create attribution result for error cases."""
        return AttributionResult(
            order_id=context.order_id,
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.REJECTED,
            calculated_at=datetime.utcnow(),
            metadata={"error": error_message},
        )

    def _get_default_attribution_rules(self) -> List[AttributionRule]:
        """Get default attribution rules."""
        return [
            AttributionRule(
                name="Direct Click Attribution",
                description="100% attribution to the extension that received the direct click",
                rule_type=AttributionType.DIRECT_CLICK,
                time_window_hours=720,  # 30 days
                minimum_order_value=Decimal("10.00"),
            ),
            AttributionRule(
                name="Cross Extension Attribution",
                description="70% to primary extension, 30% to secondary extensions",
                rule_type=AttributionType.CROSS_EXTENSION,
                time_window_hours=720,  # 30 days
                minimum_order_value=Decimal("10.00"),
                cross_extension_weight_primary=0.7,
                cross_extension_weight_secondary=0.3,
            ),
        ]
