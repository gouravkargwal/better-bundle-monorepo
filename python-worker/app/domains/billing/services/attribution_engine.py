"""
Attribution Engine for Billing System

This service calculates attribution for purchases based on customer interactions
with recommendations across different extensions.
"""

import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.shared.helpers import now_utc

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import UserInteraction, UserSession, PurchaseAttribution
from app.core.database.session import get_session_context
from app.domains.analytics.services.cross_session_linking_service import (
    CrossSessionLinkingService,
)
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
from app.domains.billing.services.commission_service import CommissionService
from app.core.database.models.enums import BillingPhase

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
        """
        Initialize the attribution engine.

        ✅ SCENARIO 9: Configurable Attribution Windows
        """
        self.session = session
        self.adapter_factory = InteractionEventAdapterFactory()
        self.commission_service = CommissionService(session)
        # ✅ SCENARIO 9: Configurable attribution windows
        self.attribution_windows = {
            "default": timedelta(hours=24),  # 24 hours default
            "short": timedelta(hours=2),  # 2 hours for quick purchases
            "medium": timedelta(days=3),  # 3 days for consideration
            "long": timedelta(days=30),  # 30 days for long consideration
            "extended": timedelta(days=90),  # 90 days for high-value items
        }

    async def calculate_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """
        Calculate attribution for a purchase event.

        ✅ SCENARIO 14: Payment Failure Attribution

        Story: Sarah sees a recommendation, adds to cart, but payment fails.
        She retries and succeeds. We should only attribute successful payments,
        not failed attempts.

        Args:
            context: Attribution context with purchase and customer data

        Returns:
            AttributionResult with detailed breakdown
        """
        try:
            # ✅ SCENARIO 14: Check for payment failure before processing attribution
            if await self._is_payment_failed(context):
                logger.warning(
                    f"⚠️ Payment failed for order {context.order_id} - skipping attribution"
                )
                result = self._create_payment_failed_attribution(context)
                await self._store_attribution_result(result)  # ✅ Store rejected
                return result

            logger.info(
                f"🔍 Starting attribution calculation for order {context.order_id}"
            )
            logger.info(
                f"🔍 Context: shop_id={context.shop_id}, customer_id={context.customer_id}, session_id={context.session_id}"
            )
            logger.info(
                f"🔍 Purchase amount: {context.purchase_amount}, Products: {len(context.purchase_products)}"
            )

            # ✅ SCENARIO 15: Check for subscription cancellation
            if await self._is_subscription_cancelled(context):
                logger.warning(
                    f"📋 Subscription cancelled for order {context.order_id}"
                )
                result = self._create_subscription_cancelled_attribution(context)
                await self._store_attribution_result(result)  # ✅ Store rejected
                return result

            # ✅ SCENARIO 22: Check for recommendation timing
            timing_analysis = await self._analyze_recommendation_timing(context)
            if timing_analysis["requires_adjustment"]:
                logger.info(
                    f"⏰ Recommendation timing adjustment needed for order {context.order_id}"
                )
                result = await self._handle_timing_adjustment(context, timing_analysis)
                await self._store_attribution_result(result)  # ✅ Store rejected
                return result

            # ✅ SCENARIO 9: Get all interactions for this customer/session with configurable window
            attribution_window = self._determine_attribution_window(context)
            interactions = await self._get_relevant_interactions(
                context, attribution_window
            )
            logger.info(
                f"📊 Found {len(interactions)} interactions for order {context.order_id}"
            )

            if not interactions:
                logger.warning(f"⚠️ No interactions found for order {context.order_id}")
                result = self._create_empty_attribution(context)
                await self._store_attribution_result(result)  # ✅ Store rejected
                return result

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
                calculated_at=now_utc(),
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

            # ========================================
            # 🆕 NEW: Step 5 - CREATE COMMISSION RECORD
            # ========================================
            # Store returns created attribution id (or existing one)
            attribution_id = await self._store_attribution_result(result)

            if attribution_id:
                await self._create_commission_for_attribution(
                    attribution_id=attribution_id, shop_id=context.shop_id
                )

            return result

        except Exception as e:
            logger.error(
                f"Error calculating attribution for order {context.order_id}: {e}"
            )
            return self._create_error_attribution(context, str(e))

    async def _create_commission_for_attribution(
        self, attribution_id: str, shop_id: str
    ) -> None:
        """
        Create commission record for a purchase attribution.
        This is called automatically after attribution is created.

        Args:
            attribution_id: Purchase attribution ID
            shop_id: Shop ID
        """
        try:
            logger.info(f"💰 Creating commission for attribution {attribution_id}")

            # Create commission record (handles both trial and paid phases)
            commission = await self.commission_service.create_commission_record(
                purchase_attribution_id=attribution_id, shop_id=shop_id
            )

            if not commission:
                logger.error(
                    f"❌ Failed to create commission for attribution {attribution_id}"
                )
                return

            logger.info(
                f"✅ Commission created: ${commission.commission_earned} "
                f"(phase: {commission.billing_phase.value}, status: {commission.status.value})"
            )

            # Check if we need to handle trial threshold or cap limits
            await self._handle_post_commission_checks(commission, shop_id)

        except Exception as e:
            logger.error(f"❌ Error creating commission: {e}")
            # Don't fail the entire attribution if commission creation fails
            # Commission can be created later via reconciliation

    async def _handle_post_commission_checks(self, commission, shop_id: str) -> None:
        """
        Handle checks after commission is created:
        - Trial threshold check
        - Cap limit check
        - Warnings

        Args:
            commission: Created commission record
            shop_id: Shop ID
        """
        try:

            if commission.billing_phase == BillingPhase.TRIAL:
                # Check if trial threshold reached
                trial_status = (
                    await self.commission_service.handle_trial_threshold_check(shop_id)
                )

                if trial_status.get("threshold_reached"):
                    logger.warning(
                        f"🎯 Trial threshold reached for shop {shop_id}! "
                        f"${trial_status.get('total_trial_revenue')} >= "
                        f"${trial_status.get('trial_threshold')}"
                    )

                    # Lazy import to avoid circular dependency with BillingService
                    from app.domains.billing.services.billing_service import (
                        BillingService,
                    )

                    billing_service = BillingService(self.session)
                    # Note: _handle_trial_purchase signature expects
                    # (shop_id, billing_plan, attributed_revenue, purchase_event)
                    # We pass attributed_revenue using commission.cycle_usage_after and
                    # no purchase_event context is available here.
                    await billing_service._handle_trial_purchase(  # type: ignore[attr-defined]
                        shop_id,
                        commission.billing_plan,
                        commission.cycle_usage_after,
                        None,
                    )

            elif commission.billing_phase == BillingPhase.PAID:
                # Check usage percentage
                usage_percentage = (
                    commission.cycle_usage_after / commission.capped_amount * 100
                )

                # Warning at 75%
                if usage_percentage >= 75 and usage_percentage < 90:
                    logger.warning(
                        f"⚠️ Usage at {usage_percentage:.1f}% of cap for shop {shop_id}"
                    )
                    # TODO: Send notification to merchant

                # Urgent warning at 90%
                elif usage_percentage >= 90 and usage_percentage < 100:
                    logger.warning(
                        f"🚨 Usage at {usage_percentage:.1f}% of cap for shop {shop_id}! "
                        f"Approaching limit."
                    )
                    # TODO: Send urgent notification to merchant

                # Cap reached - log warning (suspension handled by billing service)
                elif usage_percentage >= 100:
                    logger.error(
                        f"🛑 Cap reached for shop {shop_id}! "
                        f"${commission.cycle_usage_after} >= ${commission.capped_amount}"
                    )
                    # Note: Service suspension will be handled by the billing service
                    # when it processes the commission with CAPPED status

        except Exception as e:
            logger.error(f"❌ Error in post-commission checks: {e}")

    async def _get_relevant_interactions(
        self, context: AttributionContext, attribution_window: timedelta = None
    ) -> List[Dict[str, Any]]:
        """
        ✅ SCENARIO 9: Get all relevant interactions for attribution calculation with configurable window.
        """
        # Use provided attribution window or default
        if attribution_window is None:
            attribution_window = self.attribution_windows["default"]

        start_time = context.purchase_time - attribution_window

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
            product_amount = unit_price * quantity

            logger.info(
                f"🔍 Processing product {product_id} with unit price ${unit_price}, "
                f"quantity {quantity}, total amount ${product_amount}"
            )

            if not product_id or product_amount <= 0:
                logger.warning(
                    f"⚠️ Skipping product {product_id} - invalid ID or amount"
                )
                continue

            # Find interactions for this product
            product_interaction_list = product_interactions.get(product_id, [])

            # 🆕 NEW: If no recommendation interactions found, try journey-based matching
            if not product_interaction_list:
                logger.info(
                    f"🔍 No direct recommendation interactions for {product_id}, "
                    f"attempting journey-based matching"
                )

                # Use journey-based matching to find attribution
                journey = self._build_product_journey(
                    product_id=product_id,
                    customer_id=context.customer_id or "",
                    purchase_time=context.purchase_time,
                    all_interactions=interactions,  # Pass ALL interactions
                )

                if journey:
                    logger.info(
                        f"✅ Journey-based match found for {product_id}! "
                        f"Extension: {journey['interaction']['extension_type']}, "
                        f"Confidence: {journey['confidence']:.2%}"
                    )

                    # Create attribution from journey
                    product_interaction_list = [journey["interaction"]]

                    # Add confidence score to metadata
                    journey["interaction"]["metadata"]["journey_confidence"] = journey[
                        "confidence"
                    ]
                    journey["interaction"]["metadata"]["journey_steps"] = journey[
                        "journey_steps"
                    ]
                    journey["interaction"]["metadata"]["time_to_purchase_hours"] = (
                        journey["time_to_purchase"].total_seconds() / 3600
                    )
                else:
                    logger.info(
                        f"❌ No attribution found for {product_id} via journey matching"
                    )
                    continue

            # Calculate attribution for this product
            if product_interaction_list:
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
        Group interactions by product ID using JOURNEY-BASED MATCHING.

        OLD LOGIC (Broken):
        - Only looked for recommendation_add_to_cart and recommendation_clicked
        - Missed multi-step journeys

        NEW LOGIC (Proper):
        - Finds ANY recommendation interaction (click/view/add)
        - Tracks complete customer journey
        - Links purchases that happen DAYS later

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

        # 🆕 NEW: Accept ALL recommendation interaction types
        attribution_eligible_interactions = {
            "recommendation_add_to_cart",  # Direct add-to-cart
            "recommendation_clicked",  # Click on recommendation
            "recommendation_viewed",  # View recommendation (weaker signal)
        }

        for interaction in interactions:
            # Skip ATLAS interactions (web pixel doesn't drive conversions)
            if interaction["extension_type"] == ExtensionType.ATLAS.value:
                continue

            # Only process interactions from attribution-eligible extensions
            if interaction["extension_type"] not in attribution_eligible_extensions:
                continue

            # 🆕 NEW: Process ALL recommendation interaction types
            if interaction["interaction_type"] not in attribution_eligible_interactions:
                continue

            # Extract product_id using adapter factory
            product_id = None
            try:
                interaction_dict = {
                    "interactionType": interaction["interaction_type"],
                    "metadata": interaction["metadata"],
                    "customerId": interaction["customer_id"],
                    "sessionId": interaction["session_id"],
                    "shopId": interaction["shop_id"],
                    "createdAt": interaction["created_at"],
                }

                product_id = self.adapter_factory.extract_product_id(interaction_dict)

                if not product_id:
                    logger.warning(
                        f"⚠️ Could not extract product_id from {interaction['extension_type']} "
                        f"interaction {interaction['id']}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Error extracting product_id: {e}")
                continue

            # Group by product_id
            if product_id not in product_interactions:
                product_interactions[product_id] = []

            product_interactions[product_id].append(interaction)

            logger.debug(
                f"✅ Grouped {interaction['extension_type']} "
                f"{interaction['interaction_type']} for product {product_id}"
            )

        logger.info(
            f"📦 Grouped {len(interactions)} interactions into "
            f"{len(product_interactions)} product buckets"
        )

        return product_interactions

    def _extract_product_id_from_interaction(
        self, interaction: Dict[str, Any]
    ) -> Optional[str]:
        """
        Helper to extract product_id from interaction.
        """
        try:
            interaction_dict = {
                "interactionType": interaction["interaction_type"],
                "metadata": interaction["metadata"],
                "customerId": interaction["customer_id"],
                "sessionId": interaction["session_id"],
                "shopId": interaction["shop_id"],
                "createdAt": interaction["created_at"],
            }
            return self.adapter_factory.extract_product_id(interaction_dict)
        except Exception as e:
            logger.error(f"Error extracting product_id: {e}")
            return None

    def _build_product_journey(
        self,
        product_id: str,
        customer_id: str,
        purchase_time: datetime,
        all_interactions: List[Dict[str, Any]],
        attribution_window: timedelta = None,
    ) -> Optional[Dict[str, Any]]:
        """
        🆕 NEW METHOD: Build complete customer journey for a product purchase.

        This is the CORE FIX that enables multi-step journey attribution!

        Match Logic:
        1. Find ANY recommendation interaction (click/view/add) for this product
        2. Check if it's within attribution window (default 30 days)
        3. Calculate confidence score based on journey complexity and timing
        4. If found and confident → attribute to that recommendation

        Examples:

        Journey 1 (Direct - High Confidence):
        T+0: Click recommendation → T+1: Add to cart
        Result: 95% confidence, attribute to recommendation

        Journey 2 (Multi-Step - Medium Confidence):
        T+0: Click recommendation → T+5min: Search → T+7min: View → T+10min: Add
        Result: 75% confidence, attribute to recommendation

        Journey 3 (Long Delay - Lower Confidence):
        Day 1: Click recommendation → Day 5: Add to cart
        Result: 45% confidence, still attribute (within 30 day window)

        Args:
            product_id: Product ID being purchased
            customer_id: Customer making purchase
            purchase_time: When purchase happened
            all_interactions: All interactions for this customer
            attribution_window: Time window for attribution (default: 30 days)

        Returns:
            Journey data dict with attribution info, or None if no attribution
        """
        if attribution_window is None:
            attribution_window = self.attribution_windows.get(
                "long", timedelta(days=30)
            )

        logger.info(
            f"🔍 Building product journey for {product_id} with {len(all_interactions)} interactions"
        )

        # Step 1: Filter interactions for this product
        product_interactions = [
            i
            for i in all_interactions
            if self._extract_product_id_from_interaction(i) == product_id
        ]

        logger.info(
            f"📦 Found {len(product_interactions)} interactions for product {product_id}"
        )

        if not product_interactions:
            return None

        # Step 2: Find recommendation interactions (earliest wins for fairness)
        recommendation_interactions = [
            i
            for i in product_interactions
            if i["interaction_type"]
            in [
                "recommendation_clicked",
                "recommendation_viewed",
                "recommendation_add_to_cart",
            ]
            and i["extension_type"] in ["phoenix", "venus", "apollo"]
        ]

        if not recommendation_interactions:
            logger.info(
                f"❌ No recommendation interactions found for product {product_id}"
            )
            return None

        logger.info(
            f"🎯 Found {len(recommendation_interactions)} recommendation interactions"
        )

        # Step 3: Check attribution window and calculate confidence
        # Sort by time (earliest first for first-touch attribution)
        recommendation_interactions.sort(key=lambda x: x["created_at"])

        for rec_interaction in recommendation_interactions:
            time_diff = purchase_time - rec_interaction["created_at"]

            # Check if within attribution window
            if timedelta(0) <= time_diff <= attribution_window:

                # Calculate journey metrics
                journey_steps = self._count_journey_steps(
                    rec_interaction, product_interactions, purchase_time
                )

                confidence = self._calculate_attribution_confidence(
                    rec_interaction, time_diff, journey_steps, product_interactions
                )

                logger.info(
                    f"✅ ATTRIBUTION MATCH FOUND!\n"
                    f"   Product: {product_id}\n"
                    f"   Extension: {rec_interaction['extension_type']}\n"
                    f"   Type: {rec_interaction['interaction_type']}\n"
                    f"   Time to purchase: {time_diff}\n"
                    f"   Journey steps: {journey_steps}\n"
                    f"   Confidence: {confidence:.2%}"
                )

                return {
                    "interaction": rec_interaction,
                    "time_to_purchase": time_diff,
                    "journey_steps": journey_steps,
                    "confidence": confidence,
                    "product_id": product_id,
                }

        logger.info(
            f"❌ No recommendation interactions within attribution window for {product_id}"
        )
        return None

    def _count_journey_steps(
        self,
        first_interaction: Dict[str, Any],
        all_product_interactions: List[Dict[str, Any]],
        purchase_time: datetime,
    ) -> int:
        """
        🆕 NEW METHOD: Count steps in the journey from recommendation to purchase.

        Journey complexity affects confidence:
        - 1-2 steps (direct): High confidence (95%)
        - 3-4 steps (normal): Medium confidence (75%)
        - 5+ steps (complex): Lower confidence (50%)

        Examples:

        Simple Journey (1 step):
        Click recommendation → Add to cart

        Normal Journey (3 steps):
        Click recommendation → View product → Add to cart

        Complex Journey (5 steps):
        Click recommendation → View → Search → View again → Add to cart

        Args:
            first_interaction: The initial recommendation interaction
            all_product_interactions: All interactions for this product
            purchase_time: When purchase happened

        Returns:
            Number of steps in the journey
        """
        # Count interactions between recommendation and purchase
        steps_between = [
            i
            for i in all_product_interactions
            if first_interaction["created_at"] < i["created_at"] <= purchase_time
        ]

        # Total steps = first interaction + steps between + purchase
        total_steps = 1 + len(steps_between)

        logger.debug(
            f"📊 Journey complexity: {total_steps} steps "
            f"({len(steps_between)} intermediate actions)"
        )

        return total_steps

    # ============================================================================
    # STEP 4: Add _calculate_attribution_confidence() method (NEW)
    # ============================================================================

    def _calculate_attribution_confidence(
        self,
        rec_interaction: Dict[str, Any],
        time_to_purchase: timedelta,
        journey_steps: int,
        product_interactions: List[Dict[str, Any]],
    ) -> float:
        """
        🆕 NEW METHOD: Calculate attribution confidence score (0.0 to 1.0).

        Confidence Factors:

        1. Time Decay (40% weight):
        - 1 hour: 1.0 (perfect)
        - 1 day: 0.8 (high)
        - 7 days: 0.5 (medium)
        - 30 days: 0.2 (low but acceptable)

        2. Journey Complexity (30% weight):
        - 1-2 steps: 1.0 (direct)
        - 3-4 steps: 0.75 (normal)
        - 5+ steps: 0.5 (complex)

        3. Interaction Type (20% weight):
        - recommendation_add_to_cart: 1.0 (highest)
        - recommendation_clicked: 0.9 (high)
        - recommendation_viewed: 0.7 (medium)

        4. Position Quality (10% weight):
        - Position 1-3: 1.0 (top recommendations)
        - Position 4-6: 0.8 (good)
        - Position 7+: 0.6 (lower)

        Args:
            rec_interaction: The recommendation interaction
            time_to_purchase: Time between recommendation and purchase
            journey_steps: Number of steps in journey
            product_interactions: All product interactions

        Returns:
            Confidence score between 0.0 and 1.0
        """

        # 1. Time Decay Factor (40%) - Exponential decay
        hours_to_purchase = time_to_purchase.total_seconds() / 3600
        # Decay half-life: 24 hours (after 24h, confidence is 0.5)
        time_factor = math.exp(-hours_to_purchase / 35)  # ln(2) * 50 ≈ 35
        time_factor = max(0.1, min(1.0, time_factor))  # Clamp between 0.1 and 1.0

        # 2. Journey Complexity Factor (30%)
        if journey_steps <= 2:
            complexity_factor = 1.0  # Direct journey
        elif journey_steps <= 4:
            complexity_factor = 0.75  # Normal journey
        else:
            complexity_factor = 0.5 / math.sqrt(journey_steps - 3)  # Complex journey

        # 3. Interaction Type Factor (20%)
        interaction_type = rec_interaction["interaction_type"]
        type_scores = {
            "recommendation_add_to_cart": 1.0,  # Direct add-to-cart
            "recommendation_clicked": 0.9,  # Click
            "recommendation_viewed": 0.7,  # View only
        }
        type_factor = type_scores.get(interaction_type, 0.5)

        # 4. Position Quality Factor (10%)
        position = rec_interaction.get("metadata", {}).get(
            "recommendation_position", 999
        )
        try:
            position = int(position)
            if position <= 3:
                position_factor = 1.0  # Top 3
            elif position <= 6:
                position_factor = 0.8  # Top 6
            else:
                position_factor = 0.6  # Lower positions
        except (ValueError, TypeError):
            position_factor = 0.7  # Unknown position

        # Weighted combination
        confidence = (
            time_factor * 0.40
            + complexity_factor * 0.30
            + type_factor * 0.20
            + position_factor * 0.10
        )

        # Clamp final result
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            f"📊 Confidence breakdown:\n"
            f"   Time factor (40%): {time_factor:.2f} ({hours_to_purchase:.1f}h)\n"
            f"   Complexity (30%): {complexity_factor:.2f} ({journey_steps} steps)\n"
            f"   Type factor (20%): {type_factor:.2f} ({interaction_type})\n"
            f"   Position (10%): {position_factor:.2f} (pos {position})\n"
            f"   → TOTAL: {confidence:.2%}"
        )

        return confidence

    def _deduplicate_product_interactions(
        self, interactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate multiple recommendations for the same product.

        Scenario 6: Multiple Recommendations for Same Product
        - User sees same product recommended multiple times
        - We should only attribute the most influential interaction
        - Prevents double attribution for same product

        Args:
            interactions: List of interactions for a product

        Returns:
            Deduplicated list of interactions
        """
        if len(interactions) <= 1:
            return interactions

        logger.info(
            f"🔍 Deduplicating {len(interactions)} interactions for same product"
        )

        # Group interactions by extension and interaction type
        interaction_groups = {}
        for interaction in interactions:
            # Create a more specific grouping key to handle edge cases
            extension = interaction["extension_type"]
            interaction_type = interaction["interaction_type"]

            # Special handling for different scenarios
            if interaction_type == "recommendation_add_to_cart":
                # Add to cart is always most important - group separately
                key = f"{extension}_add_to_cart"
            elif interaction_type == "recommendation_clicked":
                # Clicks are secondary - group by extension
                key = f"{extension}_clicked"
            else:
                # Other interaction types
                key = f"{extension}_{interaction_type}"

            if key not in interaction_groups:
                interaction_groups[key] = []
            interaction_groups[key].append(interaction)

        deduplicated = []

        # ✅ SCENARIO 6: Prioritize add_to_cart over clicks
        # If we have both add_to_cart and clicked interactions, prioritize add_to_cart
        has_add_to_cart = any(
            group_key.endswith("_add_to_cart")
            for group_key in interaction_groups.keys()
        )

        if has_add_to_cart:
            # Filter out click interactions if we have add_to_cart
            filtered_groups = {
                key: interactions
                for key, interactions in interaction_groups.items()
                if not key.endswith("_clicked")
            }
            logger.info(
                f"🔍 Prioritizing add_to_cart interactions, filtering out {len(interaction_groups) - len(filtered_groups)} click groups"
            )
            interaction_groups = filtered_groups

        # For each group, select the most influential interaction
        for group_key, group_interactions in interaction_groups.items():
            if len(group_interactions) == 1:
                # Single interaction in group - keep it
                deduplicated.append(group_interactions[0])
            else:
                # Multiple interactions in same group - select best one
                best_interaction = self._select_best_interaction(group_interactions)
                deduplicated.append(best_interaction)

                logger.info(
                    f"🔍 Group {group_key}: Selected best interaction from {len(group_interactions)} options"
                )

        logger.info(
            f"✅ Deduplication complete: {len(interactions)} → {len(deduplicated)} interactions"
        )

        return deduplicated

    def _select_best_interaction(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Select the best interaction from a group of similar interactions.

        Selection criteria (in order of priority):
        1. Most recent interaction (recency)
        2. Highest recommendation position (position 1 > position 5)
        3. Most specific interaction type (add_to_cart > clicked)
        4. Highest confidence score (if available)

        Args:
            interactions: List of similar interactions

        Returns:
            Best interaction to attribute
        """
        if len(interactions) == 1:
            return interactions[0]

        # Sort by multiple criteria
        def interaction_score(interaction):
            # 1. Recency (newer is better)
            recency_score = interaction["created_at"].timestamp()

            # 2. Position (lower position number is better)
            position = interaction.get("metadata", {}).get(
                "recommendation_position", 999
            )
            position_score = 1000 - int(position) if str(position).isdigit() else 0

            # 3. Interaction type priority (add_to_cart > clicked)
            type_priority = {
                "recommendation_add_to_cart": 100,
                "recommendation_clicked": 50,
                "recommendation_viewed": 10,
            }
            type_score = type_priority.get(interaction["interaction_type"], 0)

            # 4. Confidence score (if available)
            confidence = interaction.get("metadata", {}).get("confidence", 0)
            confidence_score = float(confidence) * 10 if confidence else 0

            # Combined score (higher is better)
            total_score = (
                recency_score * 0.4  # 40% recency
                + position_score * 0.3  # 30% position
                + type_score * 0.2  # 20% type
                + confidence_score * 0.1  # 10% confidence
            )

            return total_score

        # Sort by score (highest first)
        sorted_interactions = sorted(interactions, key=interaction_score, reverse=True)
        best_interaction = sorted_interactions[0]

        logger.info(
            f"🏆 Selected best interaction: {best_interaction['extension_type']} "
            f"{best_interaction['interaction_type']} at {best_interaction['created_at']}"
        )

        return best_interaction

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

        # ✅ SCENARIO 6: Deduplicate multiple recommendations for same product
        deduplicated_interactions = self._deduplicate_product_interactions(interactions)

        logger.info(
            f"🔍 Product {product_id}: {len(interactions)} interactions → {len(deduplicated_interactions)} after deduplication"
        )

        # Sort interactions by time (most recent first)
        deduplicated_interactions.sort(key=lambda x: x["created_at"], reverse=True)

        # Apply attribution rules
        if len(deduplicated_interactions) == 1:
            # Single interaction - direct attribution
            return self._create_direct_attribution(
                product_id, product_amount, deduplicated_interactions[0]
            )
        else:
            # Multiple interactions - cross-extension attribution
            return self._create_cross_extension_attribution(
                product_id, product_amount, deduplicated_interactions
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

        ✅ SCENARIO 7: Cross-Extension Attribution

        Story: Sarah sees a recommendation on homepage (Atlas), clicks it,
        then sees it again in cart (Phoenix), then sees it in post-purchase
        email (Apollo). All extensions should get proportional attribution.

        Args:
            product_id: Product ID
            product_amount: Product amount
            interactions: List of interactions (sorted by time)

        Returns:
            List of attribution breakdowns
        """
        breakdowns = []

        # ✅ SCENARIO 7: Calculate cross-extension weights
        extension_weights = self._calculate_cross_extension_weights(interactions)

        logger.info(
            f"🔗 Cross-extension attribution for product {product_id}: "
            f"{len(interactions)} interactions, weights: {extension_weights}"
        )

        # Distribute attribution based on calculated weights
        # Create one breakdown per extension, not per interaction
        for extension, weight in extension_weights.items():
            attributed_amount = product_amount * Decimal(str(weight))

            if attributed_amount > 0:
                # Find the most recent interaction for this extension
                extension_interactions = [
                    i for i in interactions if i["extension_type"] == extension
                ]
                most_recent_interaction = max(
                    extension_interactions, key=lambda x: x["created_at"]
                )

                breakdowns.append(
                    AttributionBreakdown(
                        extension_type=ExtensionType(extension),
                        product_id=product_id,
                        attributed_amount=attributed_amount,
                        attribution_weight=weight,
                        attribution_type=AttributionType.CROSS_EXTENSION,
                        interaction_id=most_recent_interaction["id"],
                        metadata={
                            "interaction_type": most_recent_interaction[
                                "interaction_type"
                            ],
                            "recommendation_position": most_recent_interaction[
                                "metadata"
                            ].get("recommendation_position"),
                            "created_at": most_recent_interaction[
                                "created_at"
                            ].isoformat(),
                            "attribution_role": "cross_extension",
                            "total_interactions": len(extension_interactions),
                        },
                    )
                )

        return breakdowns

    async def _is_payment_failed(self, context: AttributionContext) -> bool:
        """
        ✅ SCENARIO 14: Check if payment failed for this order

        Story: Sarah sees a recommendation, adds to cart, but payment fails.
        We should not attribute failed payments, only successful ones.

        Args:
            context: Attribution context

        Returns:
            True if payment failed, False if successful
        """
        try:
            # Check order financial status from context metadata
            financial_status = getattr(context, "financial_status", None)
            if financial_status:
                # Shopify financial statuses: PAID, PENDING, PARTIALLY_PAID, REFUNDED, VOIDED, PARTIALLY_REFUNDED
                failed_statuses = ["VOIDED", "CANCELLED"]
                if financial_status in failed_statuses:
                    logger.info(
                        f"💳 Payment failed for order {context.order_id}: {financial_status}"
                    )
                    return True

            # Check for payment failure indicators in metadata
            metadata = getattr(context, "metadata", {})
            if metadata:
                payment_status = metadata.get("payment_status")
                if payment_status in ["failed", "declined", "cancelled"]:
                    logger.info(
                        f"💳 Payment failed for order {context.order_id}: {payment_status}"
                    )
                    return True

            # Check for error messages
            error_message = metadata.get("error_message", "")
            if error_message and isinstance(error_message, str):
                if any(
                    keyword in error_message.lower()
                    for keyword in ["declined", "failed", "insufficient", "expired"]
                ):
                    logger.info(
                        f"💳 Payment failed for order {context.order_id}: {error_message}"
                    )
                    return True

            return False

        except Exception as e:
            logger.error(
                f"Error checking payment status for order {context.order_id}: {e}"
            )
            return False  # Assume successful if we can't determine

    async def _is_subscription_cancelled(self, context: AttributionContext) -> bool:
        """
        ✅ SCENARIO 15: Check if subscription was cancelled for this order

        Story: Sarah sees a recommendation, subscribes to a service, but then
        cancels the subscription. We need to handle attribution for cancelled
        subscriptions appropriately.

        Args:
            context: Attribution context

        Returns:
            True if subscription cancelled, False otherwise
        """
        try:
            # Check for subscription cancellation indicators
            metadata = getattr(context, "metadata", {})

            # Check for subscription status
            subscription_status = metadata.get("subscription_status")
            if (
                subscription_status
                and isinstance(subscription_status, str)
                and subscription_status in ["cancelled", "terminated", "expired"]
            ):
                logger.info(
                    f"📋 Subscription cancelled for order {context.order_id}: {subscription_status}"
                )
                return True

            # Check for cancellation date
            cancelled_at = metadata.get("cancelled_at")
            if cancelled_at:
                logger.info(
                    f"📋 Subscription cancelled for order {context.order_id} at {cancelled_at}"
                )
                return True

            # Check for subscription-related metadata
            if metadata.get("subscription_cancelled"):
                logger.info(f"📋 Subscription cancelled for order {context.order_id}")
                return True

            return False

        except Exception as e:
            logger.error(
                f"Error checking subscription cancellation for order {context.order_id}: {e}"
            )
            return False

    async def _calculate_normal_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """Fallback method for normal attribution calculation"""
        # This would contain the normal attribution logic
        # For now, return a basic result
        return AttributionResult(
            order_id=context.order_id,
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
            total_attributed_revenue=context.purchase_amount,
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.CALCULATED,
            calculated_at=now_utc(),
            metadata={"scenario": "normal_attribution"},
        )

    def _determine_attribution_window(self, context: AttributionContext) -> timedelta:
        """
        ✅ SCENARIO 9: Determine appropriate attribution window based on context

        Story: Sarah sees a recommendation for a $10 t-shirt (short window) vs
        a $2000 laptop (extended window). Different products need different
        attribution windows based on their value and consideration time.

        Args:
            context: Attribution context with purchase data

        Returns:
            Appropriate attribution window
        """
        try:
            # Calculate total purchase value
            total_value = sum(
                float(product.get("price", 0)) * int(product.get("quantity", 1))
                for product in context.purchase_products
            )

            # Determine window based on purchase value
            if total_value < 50:
                window_type = "short"  # Quick purchases under $50
            elif total_value < 200:
                window_type = "medium"  # Medium consideration $50-$200
            elif total_value < 1000:
                window_type = "long"  # Long consideration $200-$1000
            else:
                window_type = "extended"  # Extended consideration $1000+

            window = self.attribution_windows.get(
                window_type, self.attribution_windows["default"]
            )

            logger.info(
                f"🕒 Attribution window determined: {window_type} ({window}) "
                f"for purchase value ${total_value}"
            )

            return window

        except Exception as e:
            logger.error(f"Error determining attribution window: {e}")
            return self.attribution_windows["default"]

    def _calculate_cross_extension_weights(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        ✅ SCENARIO 7: Calculate cross-extension attribution weights

        Story: When multiple extensions influence the same purchase,
        we need to distribute attribution fairly based on:
        - Interaction recency (newer = higher weight)
        - Interaction type (add_to_cart > clicked)
        - Extension type (Phoenix > Venus > Apollo)
        - Position (position 1 > position 5)

        Args:
            interactions: List of interactions for the product

        Returns:
            Dictionary mapping extension_type to weight
        """
        if not interactions:
            return {}

        # Calculate individual scores for each interaction
        interaction_scores = []
        for interaction in interactions:
            score = self._calculate_interaction_score(interaction)
            interaction_scores.append((interaction, score))

        # Sort by score (highest first)
        interaction_scores.sort(key=lambda x: x[1], reverse=True)

        # Calculate weights based on position and score
        total_score = sum(score for _, score in interaction_scores)
        weights = {}

        for i, (interaction, score) in enumerate(interaction_scores):
            extension = interaction["extension_type"]

            # Primary interaction gets 60%, others get 40% distributed
            if i == 0:
                weight = 0.6  # Primary gets 60%
            else:
                # Distribute remaining 40% based on relative scores
                remaining_interactions = interaction_scores[1:]
                remaining_total = sum(score for _, score in remaining_interactions)
                if remaining_total > 0:
                    weight = 0.4 * (score / remaining_total)
                else:
                    weight = 0.0

            weights[extension] = weight

        # Normalize weights to ensure they sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        logger.info(f"🔗 Cross-extension weights calculated: {weights}")
        return weights

    def _calculate_interaction_score(self, interaction: Dict[str, Any]) -> float:
        """
        Calculate a score for an interaction to determine its influence.

        Scoring factors:
        - Recency (40%): Newer interactions score higher
        - Type (30%): add_to_cart > clicked > viewed
        - Extension (20%): Phoenix > Venus > Apollo
        - Position (10%): Lower position number scores higher
        """
        # 1. Recency score (40% weight)
        recency_score = interaction["created_at"].timestamp()

        # 2. Type score (30% weight)
        type_scores = {
            "recommendation_add_to_cart": 100,
            "recommendation_clicked": 80,
            "recommendation_viewed": 40,
        }
        type_score = type_scores.get(interaction["interaction_type"], 0)

        # 3. Extension score (20% weight)
        extension_scores = {
            "phoenix": 100,  # Cart recommendations are most influential
            "venus": 80,  # Customer account recommendations
            "apollo": 60,  # Post-purchase recommendations
            "atlas": 40,  # Web pixel (least influential)
        }
        extension_score = extension_scores.get(interaction["extension_type"], 0)

        # 4. Position score (10% weight)
        position = interaction.get("metadata", {}).get("recommendation_position", 999)
        position_score = max(0, 100 - int(position)) if str(position).isdigit() else 0

        # Calculate weighted total
        total_score = (
            recency_score * 0.4
            + type_score * 0.3
            + extension_score * 0.2
            + position_score * 0.1
        )

        return total_score

    async def _store_attribution_result(
        self, result: AttributionResult
    ) -> Optional[str]:
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
                return await self._save_attribution(
                    self.session,
                    result,
                    contributing_extensions,
                    attribution_weights,
                    attributed_revenue,
                    interactions_by_extension,
                )
            else:
                async with get_session_context() as session:
                    return await self._save_attribution(
                        session,
                        result,
                        contributing_extensions,
                        attribution_weights,
                        attributed_revenue,
                        interactions_by_extension,
                    )

        except Exception as e:
            if (
                "Unique constraint failed" in str(e)
                or "duplicate key" in str(e).lower()
            ):
                logger.info(
                    f"Attribution already exists for order {result.order_id}, skipping storage"
                )
                # Try to fetch existing attribution id for returning
                try:
                    if self.session:
                        session = self.session
                        # fallthrough to fetch below
                    else:
                        async with get_session_context() as session_ctx:
                            return await self._get_existing_attribution_id(
                                session_ctx, result
                            )
                    return await self._get_existing_attribution_id(session, result)
                except Exception:
                    return None
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
    ) -> Optional[str]:
        """Save attribution to database using provided session.

        Returns the created attribution id, or existing id if found.
        """
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
            return str(existing_attribution.id)

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
        return str(attribution.id)

    async def _get_existing_attribution_id(
        self, session: AsyncSession, result: AttributionResult
    ) -> Optional[str]:
        """Helper to fetch an existing attribution id for a given result."""
        stmt = select(PurchaseAttribution.id).where(
            and_(
                PurchaseAttribution.shop_id == result.shop_id,
                PurchaseAttribution.order_id == str(result.order_id),
            )
        )
        res = await session.execute(stmt)
        existing_id = res.scalar_one_or_none()
        return str(existing_id) if existing_id is not None else None

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
            calculated_at=now_utc(),
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
            calculated_at=now_utc(),
            metadata={"error": error_message},
        )

    async def _analyze_recommendation_timing(
        self, context: AttributionContext
    ) -> Dict[str, Any]:
        """
        ✅ SCENARIO 22: Analyze recommendation timing for attribution adjustment

        Story: Sarah sees a recommendation, but takes a long time to purchase.
        We need to analyze the timing to adjust attribution accordingly.

        Args:
            context: Attribution context

        Returns:
            Timing analysis results
        """
        try:
            # Get interactions to analyze timing
            attribution_window = self._determine_attribution_window(context)
            interactions = await self._get_relevant_interactions(
                context, attribution_window
            )

            if not interactions:
                # No interactions = no timing adjustment needed
                return {
                    "timing_score": 1.0,
                    "time_to_purchase_minutes": 0,
                    "session_duration_minutes": 0,
                    "user_activity_level": "unknown",
                    "recommendation_effectiveness": 0.0,
                    "requires_adjustment": False,  # ✅ No adjustment if no interactions
                }

            # Find earliest recommendation interaction
            recommendation_interactions = [
                i
                for i in interactions
                if i["interaction_type"]
                in [
                    "recommendation_clicked",
                    "recommendation_viewed",
                    "recommendation_add_to_cart",
                ]
            ]

            if not recommendation_interactions:
                # No recommendation interactions = no timing adjustment
                return {
                    "timing_score": 1.0,
                    "time_to_purchase_minutes": 0,
                    "session_duration_minutes": 0,
                    "user_activity_level": "unknown",
                    "recommendation_effectiveness": 0.0,
                    "requires_adjustment": False,  # ✅ No adjustment
                }

            # Calculate time to purchase from first recommendation
            earliest_rec = min(
                recommendation_interactions, key=lambda x: x["created_at"]
            )
            time_to_purchase = context.purchase_time - earliest_rec["created_at"]
            time_to_purchase_minutes = time_to_purchase.total_seconds() / 60

            # Calculate session duration (last interaction - first interaction)
            first_interaction = min(interactions, key=lambda x: x["created_at"])
            last_interaction = max(interactions, key=lambda x: x["created_at"])
            session_duration = (
                last_interaction["created_at"] - first_interaction["created_at"]
            )
            session_duration_minutes = session_duration.total_seconds() / 60

            # Calculate timing score using exponential decay
            # Half-life: 24 hours (1440 minutes)
            hours_to_purchase = time_to_purchase_minutes / 60
            timing_score = math.exp(-hours_to_purchase / 35)  # ln(2) * 50 ≈ 35
            timing_score = max(0.1, min(1.0, timing_score))

            # Determine user activity level
            interaction_count = len(interactions)
            if interaction_count >= 10:
                activity_level = "high"
            elif interaction_count >= 5:
                activity_level = "medium"
            else:
                activity_level = "low"

            # Calculate recommendation effectiveness
            # Based on: number of recommendation interactions / total interactions
            rec_count = len(recommendation_interactions)
            effectiveness = min(1.0, rec_count / max(1, interaction_count))

            # Determine if adjustment is needed
            # Only adjust if timing is significantly delayed (> 24 hours or < 70% score)
            requires_adjustment = timing_score < 0.7 or time_to_purchase_minutes > 1440

            result = {
                "timing_score": timing_score,
                "time_to_purchase_minutes": int(time_to_purchase_minutes),
                "session_duration_minutes": int(session_duration_minutes),
                "user_activity_level": activity_level,
                "recommendation_effectiveness": effectiveness,
                "requires_adjustment": requires_adjustment,
                "interaction_count": interaction_count,
                "recommendation_count": rec_count,
            }

            logger.info(f"📊 Timing analysis for order {context.order_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error analyzing recommendation timing: {e}")
            # Default to no adjustment on error
            return {
                "timing_score": 1.0,
                "time_to_purchase_minutes": 0,
                "session_duration_minutes": 0,
                "user_activity_level": "unknown",
                "recommendation_effectiveness": 0.5,
                "requires_adjustment": False,  # ✅ Don't adjust on error
            }

    async def _handle_timing_adjustment(
        self, context: AttributionContext, timing_analysis: Dict[str, Any]
    ) -> AttributionResult:
        """
        Handle timing-based attribution adjustment.

        IMPORTANT: Does NOT store result - that's done by the caller.
        """
        try:
            timing_score = timing_analysis.get("timing_score", 1.0)

            # Get interactions and calculate attribution
            attribution_window = self._determine_attribution_window(context)
            interactions = await self._get_relevant_interactions(
                context, attribution_window
            )

            if not interactions:
                logger.warning(f"No interactions found for timing adjustment")
                return self._create_empty_attribution(context)

            # Calculate normal attribution breakdown
            attribution_breakdown = self._calculate_attribution_breakdown(
                context, interactions
            )

            # Apply timing discount to each breakdown item
            adjusted_breakdown = []
            for breakdown in attribution_breakdown:
                adjusted_amount = breakdown.attributed_amount * Decimal(
                    str(timing_score)
                )

                adjusted_breakdown.append(
                    AttributionBreakdown(
                        extension_type=breakdown.extension_type,
                        product_id=breakdown.product_id,
                        attributed_amount=adjusted_amount,
                        attribution_weight=breakdown.attribution_weight * timing_score,
                        attribution_type=AttributionType.TIME_DECAY,
                        interaction_id=breakdown.interaction_id,
                        metadata={
                            **breakdown.metadata,
                            "timing_adjusted": True,
                            "timing_score": timing_score,
                            "original_amount": float(breakdown.attributed_amount),
                        },
                    )
                )

            # Calculate total
            total_adjusted_revenue = sum(
                breakdown.attributed_amount for breakdown in adjusted_breakdown
            )

            logger.info(
                f"Timing adjustment applied: Score {timing_score:.2%} -> ${total_adjusted_revenue}"
            )

            # Return result WITHOUT storing (caller will store)
            return AttributionResult(
                order_id=context.order_id,
                shop_id=context.shop_id,
                customer_id=context.customer_id,
                session_id=context.session_id,
                total_attributed_revenue=total_adjusted_revenue,
                attribution_breakdown=adjusted_breakdown,
                attribution_type=AttributionType.TIME_DECAY,
                status=AttributionStatus.CALCULATED,
                calculated_at=now_utc(),
                metadata={
                    "scenario": "timing_adjusted",
                    "timing_score": timing_score,
                    "time_to_purchase_minutes": timing_analysis.get(
                        "time_to_purchase_minutes"
                    ),
                    "interaction_count": len(interactions),
                },
            )

        except Exception as e:
            logger.error(f"Error handling timing adjustment: {e}", exc_info=True)
            return self._create_empty_attribution(context)

    def _create_payment_failed_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """Create attribution result for failed payments"""
        return AttributionResult(
            order_id=context.order_id,  # Use directly, not split
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.REJECTED,
            calculated_at=now_utc(),
            metadata={
                "scenario": "payment_failed",
                "reason": "Payment failed - no attribution given",
            },
        )

    def _create_subscription_cancelled_attribution(
        self, context: AttributionContext
    ) -> AttributionResult:
        """Create attribution result for cancelled subscriptions"""
        return AttributionResult(
            order_id=context.order_id,  # Use directly, not split
            shop_id=context.shop_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
            total_attributed_revenue=Decimal("0.00"),
            attribution_breakdown=[],
            attribution_type=AttributionType.DIRECT_CLICK,
            status=AttributionStatus.REJECTED,
            calculated_at=now_utc(),
            metadata={
                "scenario": "subscription_cancelled",
                "reason": "Subscription cancelled",
            },
        )

    async def _fetch_interactions(
        self, session: AsyncSession, context: AttributionContext, start_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch interactions with proper async handling.
        """
        try:
            # Build query
            query = select(UserInteraction).where(
                and_(
                    UserInteraction.shop_id == context.shop_id,
                    UserInteraction.created_at >= start_time,
                    UserInteraction.created_at <= context.purchase_time,
                )
            )

            # Add customer/session filters
            if context.customer_id:
                try:
                    linking_service = CrossSessionLinkingService()
                    all_sessions = await linking_service._get_customer_sessions(
                        customer_id=context.customer_id,
                        shop_id=context.shop_id,
                    )

                    if all_sessions:
                        session_ids = [s.id for s in all_sessions]
                        query = query.where(
                            or_(
                                UserInteraction.customer_id == context.customer_id,
                                UserInteraction.session_id.in_(session_ids),
                            )
                        )
                    else:
                        query = query.where(
                            UserInteraction.customer_id == context.customer_id
                        )
                except Exception as e:
                    logger.error(f"Error fetching linked sessions: {e}")
                    query = query.where(
                        UserInteraction.customer_id == context.customer_id
                    )

            elif context.session_id:
                query = query.where(UserInteraction.session_id == context.session_id)

            # Execute query
            result = await session.execute(
                query.order_by(UserInteraction.created_at.desc())
            )
            interactions = result.scalars().all()

            # Convert to dicts
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

        except Exception as e:
            logger.error(f"Error fetching interactions: {e}", exc_info=True)
            return []
        # Note: No finally block closing session - caller manages session lifecycle
