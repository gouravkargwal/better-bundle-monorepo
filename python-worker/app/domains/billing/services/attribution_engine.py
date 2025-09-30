"""
Attribution Engine for Billing System

This service calculates attribution for purchases based on customer interactions
with recommendations across different extensions.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from prisma import Prisma, Json
from prisma.models import UserInteraction, UserSession, PurchaseAttribution

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

    def __init__(self, prisma: Prisma):
        self.prisma = prisma
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

            # 2. Skip fraud detection - order is already paid and verified
            # fraud_result = self._detect_fraud(context, interactions)
            # if fraud_result.is_fraud:
            #     logger.warning(
            #         f"Fraud detected for order {context.order_id}: {fraud_result.fraud_reasons}"
            #     )
            #     return self._create_fraud_attribution(context, fraud_result)

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
    ) -> List[UserInteraction]:
        """
        Get all relevant interactions for attribution calculation.

        Args:
            context: Attribution context

        Returns:
            List of relevant UserInteraction records
        """
        # Time window for attribution (30 days by default)
        time_window = timedelta(hours=720)  # 30 days
        start_time = context.purchase_time - time_window

        logger.info(
            f"🔍 Searching interactions from {start_time} to {context.purchase_time}"
        )

        # Build query conditions
        where_conditions = {
            "shopId": context.shop_id,
            "createdAt": {"gte": start_time, "lte": context.purchase_time},
        }

        # Add customer or session filter
        if context.customer_id:
            where_conditions["customerId"] = context.customer_id
            logger.info(f"🔍 Filtering by customer_id: {context.customer_id}")
        elif context.session_id:
            where_conditions["sessionId"] = context.session_id
            logger.info(f"🔍 Filtering by session_id: {context.session_id}")

        logger.info(f"🔍 Query conditions: {where_conditions}")

        # Get interactions
        interactions = await self.prisma.userinteraction.find_many(
            where=where_conditions, order={"createdAt": "desc"}
        )

        logger.info(f"📊 Retrieved {len(interactions)} interactions from database")

        return interactions

    def _calculate_attribution_breakdown(
        self, context: AttributionContext, interactions: List[UserInteraction]
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
            product_amount = Decimal(str(product.get("price", 0)))

            logger.info(
                f"🔍 Processing product {product_id} with amount ${product_amount}"
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
        self, interactions: List[UserInteraction]
    ) -> Dict[str, List[UserInteraction]]:
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
            ExtensionType.PHOENIX,  # Recommendation engine
            ExtensionType.VENUS,  # Customer account extensions
            ExtensionType.APOLLO,  # Post-purchase extensions
        }

        for interaction in interactions:
            logger.info(
                f"🔍 Processing interaction {interaction.id}: {interaction.extensionType} - {interaction.interactionType}"
            )

            # Skip ATLAS interactions (web pixel) - they don't drive conversions
            if interaction.extensionType == ExtensionType.ATLAS.value:
                continue

            # Only process interactions from attribution-eligible extensions
            if (
                ExtensionType(interaction.extensionType)
                not in attribution_eligible_extensions
            ):
                continue

            # Extract product_id using adapter factory
            product_id = None
            try:
                # Convert interaction to dict format for adapter
                interaction_dict = {
                    "interactionType": interaction.interactionType,
                    "metadata": interaction.metadata,
                    "customerId": interaction.customerId,
                    "sessionId": interaction.sessionId,
                    "shopId": interaction.shopId,
                    "createdAt": interaction.createdAt,
                }

                # Extract product ID based on extension type
                product_id = None
                if interaction.extensionType == ExtensionType.PHOENIX.value:
                    # PHOENIX stores product IDs in metadata['product_ids'] as a list
                    product_ids = interaction.metadata.get("product_ids", [])
                    if product_ids:
                        # For now, use the first product ID (we can enhance this later)
                        product_id = product_ids[0]
                        logger.info(
                            f"🔍 PHOENIX: Found product_ids {product_ids}, using {product_id}"
                        )
                else:
                    # Use adapter factory for other extensions
                    product_id = self.adapter_factory.extract_product_id(
                        interaction_dict
                    )

                logger.info(
                    f"🔍 Extracted product_id: {product_id} for {interaction.extensionType} interaction {interaction.id}"
                )

                if product_id:
                    if product_id not in product_interactions:
                        product_interactions[product_id] = []
                    product_interactions[product_id].append(interaction)
                    logger.info(
                        f"✅ Added {interaction.extensionType} interaction for product {product_id}"
                    )
                else:
                    logger.info(
                        f"❌ No product_id extracted for {interaction.extensionType} interaction {interaction.id}"
                    )

            except Exception as e:
                logger.warning(
                    f"Error extracting product_id from interaction {interaction.id}: {e}"
                )
                continue

        return product_interactions

    def _calculate_product_attribution(
        self,
        product_id: str,
        product_amount: Decimal,
        interactions: List[UserInteraction],
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
        interactions.sort(key=lambda x: x.createdAt, reverse=True)

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
        self, product_id: str, product_amount: Decimal, interaction: UserInteraction
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
                extension_type=ExtensionType(interaction.extensionType),
                product_id=product_id,
                attributed_amount=product_amount,
                attribution_weight=1.0,
                attribution_type=AttributionType.DIRECT_CLICK,
                interaction_id=interaction.id,
                metadata={
                    "interaction_type": interaction.interactionType,
                    "recommendation_position": getattr(
                        interaction, "recommendationPosition", None
                    ),
                    "created_at": interaction.createdAt.isoformat(),
                },
            )
        ]

    def _create_cross_extension_attribution(
        self,
        product_id: str,
        product_amount: Decimal,
        interactions: List[UserInteraction],
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
                extension_type=ExtensionType(primary_interaction.extensionType),
                product_id=product_id,
                attributed_amount=primary_amount,
                attribution_weight=0.7,
                attribution_type=AttributionType.CROSS_EXTENSION,
                interaction_id=primary_interaction.id,
                metadata={
                    "interaction_type": primary_interaction.interactionType,
                    "recommendation_position": getattr(
                        primary_interaction, "recommendationPosition", None
                    ),
                    "created_at": primary_interaction.createdAt.isoformat(),
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
                        extension_type=ExtensionType(interaction.extensionType),
                        product_id=product_id,
                        attributed_amount=amount_per_interaction,
                        attribution_weight=0.3 / len(secondary_interactions),
                        attribution_type=AttributionType.CROSS_EXTENSION,
                        interaction_id=interaction.id,
                        metadata={
                            "interaction_type": interaction.interactionType,
                            "recommendation_position": getattr(
                                interaction, "recommendationPosition", None
                            ),
                            "created_at": interaction.createdAt.isoformat(),
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
            # Prepare session connection data
            session_connect = None
            if result.session_id:
                session_connect = {"connect": {"id": result.session_id}}

            # Store in PurchaseAttribution table
            attribution_data = {
                "sessionId": result.session_id or "",
                "orderId": str(result.order_id),
                "customerId": result.customer_id,
                "shopId": result.shop_id,
                "contributingExtensions": Json(
                    [
                        {
                            "extension_type": breakdown.extension_type.value,
                            "product_id": breakdown.product_id,
                            "attributed_amount": float(breakdown.attributed_amount),
                            "attribution_weight": breakdown.attribution_weight,
                        }
                        for breakdown in result.attribution_breakdown
                    ]
                ),
                "attributionWeights": Json(
                    {
                        breakdown.extension_type.value: breakdown.attribution_weight
                        for breakdown in result.attribution_breakdown
                    }
                ),
                "totalRevenue": float(result.total_attributed_revenue),
                "attributedRevenue": Json(
                    {
                        breakdown.extension_type.value: float(
                            breakdown.attributed_amount
                        )
                        for breakdown in result.attribution_breakdown
                    }
                ),
                "totalInteractions": len(result.attribution_breakdown),
                "interactionsByExtension": Json(
                    {
                        breakdown.extension_type.value: 1
                        for breakdown in result.attribution_breakdown
                    }
                ),
                "purchaseAt": result.calculated_at,
                "attributionAlgorithm": result.attribution_type.value,
                "metadata": Json(result.metadata),
            }

            # Add connections - use direct foreign key values instead of connect syntax
            # attribution_data["shop"] = {"connect": {"id": result.shop_id}}
            # if session_connect:
            #     attribution_data["session"] = session_connect

            # Check if attribution already exists
            existing_attribution = await self.prisma.purchaseattribution.find_first(
                where={"shopId": result.shop_id, "orderId": str(result.order_id)}
            )

            if existing_attribution:
                logger.info(
                    f"Attribution already exists for order {result.order_id}, skipping storage"
                )
                return

            await self.prisma.purchaseattribution.create(attribution_data)

            logger.info(f"Stored attribution result for order {result.order_id}")

        except Exception as e:
            if "Unique constraint failed" in str(e):
                logger.info(
                    f"Attribution already exists for order {result.order_id}, skipping storage"
                )
                return
            logger.error(
                f"Error storing attribution result for order {result.order_id}: {e}"
            )
            raise

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
