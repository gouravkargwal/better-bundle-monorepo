"""
Billing Service V2 (Flat Fee)

Updated billing service for flat fee pricing.
Attribution is calculated for analytics only; billing is decoupled
and handled via Shopify AppRecurringPricing.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from .attribution_engine import AttributionEngine, AttributionContext
from .flat_fee_billing_service import FlatFeeBillingService
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from ..models.attribution_models import AttributionResult, PurchaseEvent
from app.core.database.models import (
    ShopSubscription,
    SubscriptionStatus,
    SubscriptionType,
)
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)


class BillingServiceV2:
    """
    Updated billing service for flat fee pricing.

    Key differences from usage-based:
    - Attribution is calculated for analytics ONLY (no billing per purchase)
    - Trial is time-based (not revenue threshold-based)
    - Shopify billing uses AppRecurringPricing (not AppUsagePricing)
    - No commission records or usage tracking
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.attribution_engine = AttributionEngine(session)
        self.flat_fee_billing = FlatFeeBillingService(session, self.billing_repository)

    # ============= MAIN ENTRY POINT =============

    async def process_purchase_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """
        Process purchase attribution for analytics purposes only.

        With flat fee pricing, purchases are NOT billed individually.
        Attribution is calculated to provide analytics data to merchants.
        The monthly flat fee is charged separately via Shopify.
        """
        try:
            shop_id = purchase_event.shop_id

            # ✅ IDEMPOTENCY: Check if purchase already processed
            if await self._is_purchase_already_processed(purchase_event):
                return await self._get_existing_attribution_result(purchase_event)

            # ✅ TRANSACTION: Calculate attribution only (no billing)
            try:
                # 1. Calculate attribution (for analytics)
                attribution_result = await self._calculate_attribution(purchase_event)

                # Skip if no revenue to attribute
                if attribution_result.total_attributed_revenue <= 0:
                    return attribution_result

                # 2. Check trial expiry by time (not revenue)
                shop_subscription = await self.billing_repository.get_shop_subscription(
                    shop_id
                )
                if shop_subscription:
                    await self._check_trial_expiry_by_time(shop_id, shop_subscription)

                # 3. NO BILLING OPERATIONS — flat fee is charged via Shopify recurring subscription
                # Attribution data is stored for analytics dashboards only

                # ✅ ATOMIC: Commit changes
                await self.session.commit()

                logger.info(
                    f"📊 Attribution calculated for order {purchase_event.order_id}: "
                    f"${attribution_result.total_attributed_revenue} attributed "
                    f"({len(attribution_result.attribution_breakdown)} sources)"
                )

                return attribution_result

            except Exception as e:
                await self.session.rollback()
                logger.error(
                    f"❌ Transaction rolled back for purchase {purchase_event.order_id}: {e}"
                )
                raise

        except Exception as e:
            logger.error(f"❌ Error processing attribution: {e}", exc_info=True)
            raise

    async def _check_trial_expiry_by_time(
        self, shop_id: str, shop_subscription
    ) -> None:
        """
        Check if trial has expired based on time (not revenue).
        With flat fee pricing, trials are time-based (e.g., 14 days).
        """
        if not shop_subscription:
            return

        if shop_subscription.subscription_type != SubscriptionType.TRIAL:
            return

        if shop_subscription.status != SubscriptionStatus.TRIAL:
            return

        await self.billing_repository.check_trial_expiry_by_time(shop_id)

    async def _is_purchase_already_processed(
        self, purchase_event: PurchaseEvent
    ) -> bool:
        """Check if purchase has already been processed to prevent duplicate processing.

        Returns True if the order has been processed AND no new line items were added
        AND no existing line items were updated since the last attribution calculation
        AND the attribution already used tracking data (if available).

        This ensures that when line item data is fixed (e.g., custom attributes like _bb_rec_*),
        OR when we add new tracking data extraction logic, republishing events will trigger recalculation.
        """
        try:
            from sqlalchemy import select, func
            from app.core.database.models.purchase_attribution import (
                PurchaseAttribution,
            )
            from app.core.database.models.order_data import LineItemData

            # Check if attribution record exists
            query = select(PurchaseAttribution).where(
                PurchaseAttribution.order_id == str(purchase_event.order_id),
                PurchaseAttribution.shop_id == purchase_event.shop_id,
            )
            result = await self.session.execute(query)
            existing_attribution = result.scalar_one_or_none()

            if not existing_attribution:
                return False  # No attribution record, need to process

            # ✅ NEW CHECK: Verify if attribution used tracking data when tracking data exists
            # If tracking data exists in line items/metafields but attribution doesn't indicate
            # it was used, we need to recalculate
            has_tracking_data = self._check_if_tracking_data_exists(purchase_event)
            if has_tracking_data:
                # Check if attribution metadata indicates tracking data was used
                attribution_metadata = existing_attribution.attribution_metadata
                if isinstance(attribution_metadata, dict):
                    tracking_interactions_count = attribution_metadata.get(
                        "tracking_interactions", 0
                    )
                    if tracking_interactions_count == 0:
                        logger.info(
                            f"🔄 Tracking data exists but attribution doesn't show it was used - "
                            f"will reprocess order {purchase_event.order_id} to use tracking data"
                        )
                        return False  # Force recalculation to use tracking data
                else:
                    # Old attribution format - likely didn't use tracking data
                    logger.info(
                        f"🔄 Attribution metadata format doesn't indicate tracking data usage - "
                        f"will reprocess order {purchase_event.order_id}"
                    )
                    return False  # Force recalculation

            # ✅ FIX: LineItemData.order_id is a FK to OrderData.id (UUID), not Shopify order ID
            # First, get the OrderData record to find its UUID
            from app.core.database.models.order_data import OrderData

            order_query = select(OrderData.id).where(
                OrderData.order_id == existing_attribution.order_id
            )
            order_result = await self.session.execute(order_query)
            order_record_id = order_result.scalar_one_or_none()

            if not order_record_id:
                logger.warning(
                    f"❌ Order record not found for order_id {existing_attribution.order_id}"
                )
                return False  # If no order record, process it

            # Use the later of created_at or updated_at as the reference timestamp
            # This handles cases where attribution was already recalculated
            attribution_reference_time = existing_attribution.created_at
            if (
                hasattr(existing_attribution, "updated_at")
                and existing_attribution.updated_at
                and existing_attribution.updated_at > existing_attribution.created_at
            ):
                attribution_reference_time = existing_attribution.updated_at

            # Check if new line items were added since last attribution
            # Get the count of line items that were created after the attribution
            new_line_items_query = select(func.count(LineItemData.id)).where(
                LineItemData.order_id == order_record_id,
                LineItemData.created_at > attribution_reference_time,
            )
            new_line_items_result = await self.session.execute(new_line_items_query)
            new_line_items_count = new_line_items_result.scalar() or 0

            if new_line_items_count > 0:
                return False  # New line items added, need to re-process

            # ✅ FIX: Also check if existing line items were updated after attribution
            # This handles cases where line item data was fixed (e.g., custom attributes like _bb_rec_*)
            # When line items are updated (e.g., properties field fixed), we need to recalculate attribution
            # Use MAX(updated_at) to get the most recent line item update time
            max_line_item_updated_query = select(
                func.max(LineItemData.updated_at)
            ).where(
                LineItemData.order_id == order_record_id,
            )
            max_line_item_result = await self.session.execute(
                max_line_item_updated_query
            )
            max_line_item_updated_at = max_line_item_result.scalar()

            if max_line_item_updated_at:
                # Check if any line item was updated after attribution was last calculated
                if max_line_item_updated_at > attribution_reference_time:
                    logger.info(
                        f"🔄 Line items were updated after attribution "
                        f"(max_line_item_updated_at={max_line_item_updated_at}, "
                        f"attribution_ref_time={attribution_reference_time}) - "
                        f"will reprocess order {purchase_event.order_id}"
                    )
                    return False  # Line items updated, need to re-process
                else:
                    logger.debug(
                        f"✅ No line item updates detected "
                        f"(max_line_item_updated_at={max_line_item_updated_at} <= "
                        f"attribution_ref_time={attribution_reference_time}) for order {purchase_event.order_id}"
                    )

            return (
                True  # No new or updated line items, and tracking data was already used
            )

        except Exception as e:
            logger.error(f"Error checking if purchase already processed: {e}")
            return False

    def _check_if_tracking_data_exists(self, purchase_event: PurchaseEvent) -> bool:
        """
        Check if purchase event has tracking data from extensions.

        Returns True if:
        - Line items have _bb_rec_extension properties
        - Order has bb_recommendation.extension metafield (Apollo)
        """
        # Check line item properties for tracking
        for product in purchase_event.products:
            properties = product.get("properties", {})
            if isinstance(properties, dict) and properties:
                extension = properties.get("_bb_rec_extension")
                if extension and extension.lower() in ["apollo", "mercury"]:
                    return True

        # Check order metafields for Apollo/Mercury tracking
        order_metafields = getattr(purchase_event, "order_metafields", None)
        if order_metafields:
            for metafield in order_metafields:
                if (
                    isinstance(metafield, dict)
                    and metafield.get("namespace") == "bb_recommendation"
                    and metafield.get("key") == "extension"
                ):
                    extension_value = metafield.get("value", "").lower()
                    if extension_value in ["apollo", "mercury"]:
                        return True
                # Also check for Mercury products array (different structure)
                if (
                    isinstance(metafield, dict)
                    and metafield.get("namespace") == "bb_recommendation"
                    and metafield.get("key") == "products"
                ):
                    products_value = metafield.get("value")
                    if products_value:
                        return True

        return False

    async def _has_post_purchase_line_items(
        self, order_id: int, order_created_at: datetime
    ) -> bool:
        """Check if order has line items added after the original order creation (post-purchase additions).

        Returns True if any line items were created more than 5 seconds after order creation.
        The 5-second buffer accounts for normal Shopify order processing time.
        """
        try:
            from sqlalchemy import select, func
            from app.core.database.models.order_data import LineItemData

            # ✅ FIX: LineItemData.order_id is a FK to OrderData.id (UUID), not Shopify order ID
            # First, get the OrderData record to find its UUID
            from app.core.database.models.order_data import OrderData

            order_query = select(OrderData.id).where(
                OrderData.order_id == str(order_id)
            )
            order_result = await self.session.execute(order_query)
            order_record_id = order_result.scalar_one_or_none()

            if not order_record_id:
                logger.warning(f"❌ Order record not found for order_id {order_id}")
                return False

            # Count line items created after order creation (with 5-second buffer)
            cutoff_time = order_created_at + timedelta(seconds=5)

            line_items_query = select(func.count(LineItemData.id)).where(
                LineItemData.order_id == str(order_id),
                LineItemData.created_at > cutoff_time,
            )
            result = await self.session.execute(line_items_query)
            post_purchase_count = result.scalar() or 0

            if post_purchase_count > 0:
                logger.info(
                    f"✅ Order {order_id} has {post_purchase_count} post-purchase line items "
                    f"(created >{cutoff_time})"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Error checking for post-purchase line items: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Default to False (use created_at) if check fails
            return False

    async def _has_post_purchase_interactions(
        self,
        shop_id: str,
        customer_id: str,
        session_id: str,
        order_created_at: datetime,
        order_updated_at: datetime,
    ) -> bool:
        """Check if there are Apollo post-purchase interactions after order creation.

        This checks for recommendation clicks/add-to-cart events that occurred after
        the initial order was created, indicating post-purchase additions.

        Returns True if there are interactions after order_created_at.
        """
        try:
            from sqlalchemy import select, func, and_, or_
            from app.core.database.models.user_interaction import UserInteraction
            from app.domains.analytics.models.interaction import InteractionType

            # Look for Apollo interactions that indicate post-purchase recommendations
            post_purchase_interaction_types = [
                InteractionType.RECOMMENDATION_CLICKED.value,
                InteractionType.RECOMMENDATION_ADD_TO_CART.value,
                InteractionType.RECOMMENDATION_VIEWED.value,
            ]

            # Query for interactions that occurred AFTER the initial order creation
            # but BEFORE or AT the order update time
            query = select(func.count(UserInteraction.id)).where(
                and_(
                    UserInteraction.shop_id == shop_id,
                    UserInteraction.customer_id == customer_id,
                    UserInteraction.interaction_type.in_(
                        post_purchase_interaction_types
                    ),
                    UserInteraction.extension_type == "apollo",
                    UserInteraction.created_at > order_created_at,
                    UserInteraction.created_at <= order_updated_at,
                )
            )

            result = await self.session.execute(query)
            interaction_count = result.scalar() or 0

            if interaction_count > 0:
                logger.info(
                    f"✅ Found {interaction_count} post-purchase Apollo interactions "
                    f"between {order_created_at} and {order_updated_at}"
                )
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ Error checking for post-purchase interactions: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Default to False (use created_at) if check fails
            return False

    async def _get_existing_attribution_result(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """Get existing attribution result for already processed purchase."""
        try:
            from sqlalchemy import select
            from app.core.database.models.purchase_attribution import (
                PurchaseAttribution,
            )
            from app.domains.billing.models.attribution_models import (
                AttributionType,
                AttributionStatus,
                AttributionBreakdown,
            )

            query = select(PurchaseAttribution).where(
                PurchaseAttribution.order_id == str(purchase_event.order_id),
                PurchaseAttribution.shop_id == purchase_event.shop_id,
            )
            result = await self.session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                # Convert existing attribution to AttributionResult
                import json

                # ✅ FIX: Helper function to parse JSON fields that might be strings
                def parse_json_field(field_value, field_name, default=None):
                    if field_value is None:
                        return default if default is not None else {}
                    if isinstance(field_value, str):
                        try:
                            return json.loads(field_value)
                        except json.JSONDecodeError:
                            logger.error(
                                f"Failed to parse {field_name} as JSON: {field_value}"
                            )
                            return default if default is not None else {}
                    return field_value

                attribution_breakdown = []
                weights_data = parse_json_field(
                    existing.attribution_weights, "attribution_weights", []
                )

                for weight_data in weights_data:
                    if isinstance(weight_data, dict):
                        attribution_breakdown.append(
                            AttributionBreakdown(
                                extension_type=weight_data.get("extension_type"),
                                attributed_amount=Decimal(
                                    str(weight_data.get("attributed_amount", 0))
                                ),
                                attribution_weight=weight_data.get("weight", 0.0),
                                attribution_type=AttributionType.CROSS_EXTENSION,
                                interaction_id=weight_data.get("interaction_id"),
                                metadata=weight_data.get("metadata", {}),
                            )
                        )

                # Parse metadata field
                metadata = parse_json_field(
                    existing.attribution_metadata, "attribution_metadata", {}
                )

                return AttributionResult(
                    order_id=int(purchase_event.order_id),
                    shop_id=purchase_event.shop_id,
                    customer_id=purchase_event.customer_id,
                    session_id=existing.session_id,
                    total_attributed_revenue=existing.total_revenue,
                    attribution_breakdown=attribution_breakdown,
                    attribution_type=AttributionType.CROSS_EXTENSION,
                    status=AttributionStatus.CALCULATED,
                    calculated_at=existing.created_at,
                    metadata=metadata,
                )
            else:
                # Fallback - create empty result
                return AttributionResult(
                    order_id=int(purchase_event.order_id),
                    shop_id=purchase_event.shop_id,
                    customer_id=purchase_event.customer_id,
                    session_id=None,
                    total_attributed_revenue=Decimal("0.00"),
                    attribution_breakdown=[],
                    attribution_type=AttributionType.DIRECT_CLICK,
                    status=AttributionStatus.PENDING,
                    calculated_at=now_utc(),
                    metadata={},
                )
        except Exception as e:
            logger.error(f"Error getting existing attribution result: {e}")
            return AttributionResult(
                order_id=int(purchase_event.order_id),
                shop_id=purchase_event.shop_id,
                customer_id=purchase_event.customer_id,
                session_id=None,
                total_attributed_revenue=Decimal("0.00"),
                attribution_breakdown=[],
                attribution_type=AttributionType.DIRECT_CLICK,
                status=AttributionStatus.PENDING,
                calculated_at=now_utc(),
                metadata={},
            )

    # ============= HELPER METHODS =============

    async def _calculate_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """Calculate attribution for a purchase."""
        # ✅ FIX: For post-purchase additions, check if line items were added after order creation
        # Use updated_at only if there are actual post-purchase line item additions
        purchase_time = purchase_event.created_at

        if purchase_event.updated_at:

            # Check if there are post-purchase interactions (Apollo recommendations)
            has_post_purchase_interactions = await self._has_post_purchase_interactions(
                purchase_event.shop_id,
                purchase_event.customer_id,
                purchase_event.session_id,
                purchase_event.created_at,
                purchase_event.updated_at,
            )

            if has_post_purchase_interactions:
                logger.info(
                    f"✅ Order {purchase_event.order_id} HAS post-purchase interactions, "
                    f"using updated_at ({purchase_event.updated_at}) for attribution"
                )
                purchase_time = purchase_event.updated_at

        context = AttributionContext(
            shop_id=purchase_event.shop_id,
            customer_id=purchase_event.customer_id,
            session_id=purchase_event.session_id,
            order_id=purchase_event.order_id,
            purchase_amount=purchase_event.total_amount,
            purchase_products=purchase_event.products,
            purchase_time=purchase_time,
            order_metafields=getattr(purchase_event, "order_metafields", None),
        )

        attribution_result = await self.attribution_engine.calculate_attribution(
            context
        )
        return attribution_result

    # _process_billing_by_status removed — flat fee pricing does not bill per purchase
