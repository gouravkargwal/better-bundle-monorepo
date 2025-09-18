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

from prisma import Prisma
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
    FraudDetectionResult,
    AttributionMetrics,
)

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
            logger.info(f"Calculating attribution for order {context.order_id}")

            # 1. Get all interactions for this customer/session
            interactions = await self._get_relevant_interactions(context)

            if not interactions:
                logger.warning(f"No interactions found for order {context.order_id}")
                return self._create_empty_attribution(context)

            # 2. Apply fraud detection
            fraud_result = self._detect_fraud(context, interactions)
            if fraud_result.is_fraud:
                logger.warning(
                    f"Fraud detected for order {context.order_id}: {fraud_result.fraud_reasons}"
                )
                return self._create_fraud_attribution(context, fraud_result)

            # 3. Calculate attribution breakdown
            attribution_breakdown = self._calculate_attribution_breakdown(
                context, interactions
            )

            # 4. Create attribution result
            result = AttributionResult(
                order_id=context.order_id,
                shop_id=context.shop_id,
                customer_id=context.customer_id,
                session_id=context.session_id,
                total_attributed_revenue=sum(
                    breakdown.attributed_amount for breakdown in attribution_breakdown
                ),
                attribution_breakdown=attribution_breakdown,
                attribution_type=AttributionType.DIRECT_CLICK,
                status=AttributionStatus.CALCULATED,
                calculated_at=datetime.utcnow(),
                metadata={
                    "interaction_count": len(interactions),
                    "fraud_score": fraud_result.fraud_score,
                    "calculation_method": "multi_touch_attribution",
                },
            )

            # 5. Store attribution result
            await self._store_attribution_result(result)

            logger.info(
                f"Attribution calculated for order {context.order_id}: "
                f"${result.total_attributed_revenue}"
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

        # Build query conditions
        where_conditions = {
            "shopId": context.shop_id,
            "createdAt": {"gte": start_time, "lte": context.purchase_time},
        }

        # Add customer or session filter
        if context.customer_id:
            where_conditions["customerId"] = context.customer_id
        elif context.session_id:
            where_conditions["sessionId"] = context.session_id

        # Get interactions
        interactions = await self.prisma.userinteraction.find_many(
            where=where_conditions, order={"createdAt": "desc"}
        )

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
        breakdowns = []

        # Group interactions by product
        product_interactions = self._group_interactions_by_product(interactions)

        # Calculate attribution for each product in the purchase
        for product in context.purchase_products:
            product_id = product.get("id")
            product_amount = Decimal(str(product.get("price", 0)))

            if not product_id or product_amount <= 0:
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
        Group interactions by product ID.

        Args:
            interactions: List of interactions

        Returns:
            Dictionary mapping product_id to list of interactions
        """
        product_interactions = {}

        for interaction in interactions:
            if interaction.productId:
                if interaction.productId not in product_interactions:
                    product_interactions[interaction.productId] = []
                product_interactions[interaction.productId].append(interaction)

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
                    "recommendation_position": interaction.recommendationPosition,
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
                    "recommendation_position": primary_interaction.recommendationPosition,
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
                            "recommendation_position": interaction.recommendationPosition,
                            "created_at": interaction.createdAt.isoformat(),
                            "attribution_role": "secondary",
                        },
                    )
                )

        return breakdowns

    def _detect_fraud(
        self, context: AttributionContext, interactions: List[UserInteraction]
    ) -> FraudDetectionResult:
        """
        Detect potential fraud in attribution.

        Args:
            context: Attribution context
            interactions: List of interactions

        Returns:
            FraudDetectionResult
        """
        fraud_reasons = []
        fraud_score = 0.0

        # Check for excessive interactions
        if len(interactions) > 100:
            fraud_reasons.append("Excessive interactions in time window")
            fraud_score += 0.3

        # Check for rapid-fire interactions
        if len(interactions) > 1:
            time_diffs = []
            for i in range(1, len(interactions)):
                diff = (
                    interactions[i - 1].createdAt - interactions[i].createdAt
                ).total_seconds()
                time_diffs.append(diff)

            if any(
                diff < 1 for diff in time_diffs
            ):  # Less than 1 second between interactions
                fraud_reasons.append("Rapid-fire interactions detected")
                fraud_score += 0.4

        # Check for unusual conversion rates
        if len(interactions) > 0:
            conversion_rate = 1.0 / len(interactions)  # 1 purchase / interactions
            if conversion_rate > 0.5:  # More than 50% conversion rate
                fraud_reasons.append("Unusually high conversion rate")
                fraud_score += 0.2

        # Check for minimum order value
        if context.purchase_amount < Decimal("10.00"):
            fraud_reasons.append("Order below minimum value threshold")
            fraud_score += 0.1

        is_fraud = fraud_score > 0.5 or len(fraud_reasons) > 2

        return FraudDetectionResult(
            shop_id=context.shop_id,
            order_id=context.order_id,
            is_fraud=is_fraud,
            fraud_score=fraud_score,
            fraud_reasons=fraud_reasons,
            detected_at=datetime.utcnow(),
            metadata={
                "interaction_count": len(interactions),
                "purchase_amount": float(context.purchase_amount),
                "detection_rules_applied": len(fraud_reasons),
            },
        )

    async def _store_attribution_result(self, result: AttributionResult) -> None:
        """
        Store attribution result in database.

        Args:
            result: Attribution result to store
        """
        try:
            # Store in PurchaseAttribution table
            await self.prisma.purchaseattribution.create(
                {
                    "sessionId": result.session_id or "",
                    "orderId": result.order_id,
                    "customerId": result.customer_id,
                    "shopId": result.shop_id,
                    "contributingExtensions": [
                        {
                            "extension_type": breakdown.extension_type.value,
                            "product_id": breakdown.product_id,
                            "attributed_amount": float(breakdown.attributed_amount),
                            "attribution_weight": breakdown.attribution_weight,
                        }
                        for breakdown in result.attribution_breakdown
                    ],
                    "attributionWeights": {
                        breakdown.extension_type.value: breakdown.attribution_weight
                        for breakdown in result.attribution_breakdown
                    },
                    "totalRevenue": float(result.total_attributed_revenue),
                    "attributedRevenue": {
                        breakdown.extension_type.value: float(
                            breakdown.attributed_amount
                        )
                        for breakdown in result.attribution_breakdown
                    },
                    "totalInteractions": len(result.attribution_breakdown),
                    "interactionsByExtension": {
                        breakdown.extension_type.value: 1
                        for breakdown in result.attribution_breakdown
                    },
                    "purchaseAt": result.calculated_at,
                    "attributionAlgorithm": result.attribution_type.value,
                    "metadata": result.metadata,
                }
            )

            logger.info(f"Stored attribution result for order {result.order_id}")

        except Exception as e:
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

    def _create_fraud_attribution(
        self, context: AttributionContext, fraud_result: FraudDetectionResult
    ) -> AttributionResult:
        """Create attribution result for fraud cases."""
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
            metadata={
                "fraud_detected": True,
                "fraud_score": fraud_result.fraud_score,
                "fraud_reasons": fraud_result.fraud_reasons,
            },
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
