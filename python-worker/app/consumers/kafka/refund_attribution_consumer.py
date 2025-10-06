"""
Kafka-based refund attribution consumer for processing refund attribution events
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.database.models import RefundAttribution, RawOrder, OrderData, RefundData
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class RefundAttributionKafkaConsumer:
    """Kafka consumer for refund attribution jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()
        self.logger = logger

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["refund-attribution-jobs"],
                group_id="refund-attribution-processors",
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize refund attribution consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing refund attribution message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in refund attribution consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the refund attribution consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual refund attribution messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            event_type = payload.get("event_type")

            # Route to appropriate handler
            if event_type == "refund_created":
                await self._handle_individual_refund_attribution(payload)
            elif event_type == "refund_attribution_batch":
                await self._handle_batch_refund_attribution(payload)
            else:
                logger.warning(f"⚠️ Unknown event type: {event_type}")

        except Exception as e:
            logger.error(f"Failed to process refund attribution message: {e}")
            raise

    async def _handle_individual_refund_attribution(self, message: Dict[str, Any]):
        """Handle individual refund attribution (real-time events)."""
        try:
            # Extract and validate required fields
            shop_id = message.get("shop_id")
            refund_data_id = message.get("refund_data_id")
            order_id = message.get("shopify_id") or message.get("order_id")

            # Robust refund_data_id extraction with fallback
            if not refund_data_id:
                refund_data_id = message.get(
                    "refund_id"
                )  # Fallback for backward compatibility
                if not refund_data_id:
                    logger.warning(
                        "⚠️ No refund_data_id or refund_id found in message, skipping refund attribution"
                    )
                    return

            if not shop_id or not refund_data_id:
                logger.error(
                    "❌ Invalid refund_created payload - missing required fields",
                    message=message,
                )
                return

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for refund attribution",
                    shop_id=shop_id,
                )
                await self.dlq_service.send_to_dlq(
                    original_message=message,
                    reason="shop_suspended",
                    original_topic="refund-attribution-jobs",
                    error_details=f"Shop suspended at {datetime.utcnow().isoformat()}",
                )
                await self.consumer.commit(message)
                return

            # Use shared processing logic with SQLAlchemy session
            async with get_transaction_context() as session:
                await self._process_single_refund_attribution(
                    refund_data_id, shop_id, session
                )

        except Exception as e:
            logger.error(
                "Failed to process individual refund attribution", error=str(e)
            )
            raise

    async def _handle_batch_refund_attribution(self, message: Dict[str, Any]):
        """Handle batch refund attribution (triggered by normalization batches)."""
        shop_id = message.get("shop_id")
        refund_ids = message.get("refund_ids", [])

        if not shop_id or not refund_ids:
            logger.error(
                "❌ Invalid refund_attribution_batch payload - missing required fields",
                message=message,
            )
            return

        successful = 0
        failed = 0

        # Process all refunds in a single transaction for consistency
        try:
            async with get_transaction_context() as session:
                for refund_id in refund_ids:
                    try:
                        await self._process_single_refund_attribution(
                            refund_id, shop_id, session
                        )
                        successful += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process refund attribution for {refund_id}: {e}"
                        )
                        failed += 1
                        continue

        except Exception as e:
            logger.error(f"Failed to process batch refund attribution: {e}")
            raise

    async def _process_single_refund_attribution(
        self, refund_data_id: str, shop_id: str, session: Any
    ):
        """
        Process attribution for a single refund using RefundData and RefundAttribution tables.

        ✅ SCENARIO 11: Refund Attribution
        ✅ SCENARIO 16: Partial Refund Attribution

        - When a customer gets a refund, we need to reverse the attribution
        - Find original purchase attribution
        - Calculate proportional refund attribution
        - Create RefundAttribution record
        """
        # Get RefundData record
        refund_data_query = select(RefundData).where(
            and_(RefundData.id == refund_data_id, RefundData.shop_id == shop_id)
        )
        refund_data_result = await session.execute(refund_data_query)
        refund_data = refund_data_result.scalar_one_or_none()

        if not refund_data:
            logger.warning(
                "RefundData not found for refund attribution",
                shop_id=shop_id,
                refund_data_id=refund_data_id,
            )
            return

        # Check if attribution already exists (idempotency)
        existing_attribution_query = select(RefundAttribution).where(
            and_(
                RefundAttribution.shop_id == shop_id,
                RefundAttribution.refund_id == refund_data.refund_id,
            )
        )
        existing_attribution_result = await session.execute(existing_attribution_query)
        existing_attribution = existing_attribution_result.scalar_one_or_none()

        if existing_attribution:
            logger.info(
                f"Refund attribution already exists for {refund_data.refund_id}"
            )
            return

        # Load original order for customer and session data
        order_query = select(OrderData).where(
            and_(
                OrderData.shop_id == shop_id, OrderData.order_id == refund_data.order_id
            )
        )
        order_result = await session.execute(order_query)
        order = order_result.scalar_one_or_none()

        if not order:
            logger.warning(
                "OrderData not found for refund attribution",
                shop_id=shop_id,
                order_id=refund_data.order_id,
            )
            return

        # ✅ SCENARIO 11: Find original purchase attribution for refund
        original_attribution = await self._find_original_purchase_attribution(
            session, shop_id, refund_data.order_id
        )

        if not original_attribution:
            logger.info(
                f"No original attribution found for order {refund_data.order_id} - skipping refund attribution"
            )
            # Don't create refund attribution if there's no original attribution
            return
        else:
            # ✅ SCENARIO 12: Calculate proportional refund attribution
            attribution_data = await self._calculate_proportional_refund_attribution(
                original_attribution, refund_data, order
            )

        # Create single RefundAttribution record
        refund_attribution = RefundAttribution(
            shop_id=shop_id,
            customer_id=order.customer_id,
            session_id=getattr(order, "session_id", None),
            order_id=refund_data.order_id,
            refund_id=refund_data.refund_id,
            refunded_at=refund_data.refunded_at,
            total_refund_amount=refund_data.total_refund_amount,
            currency_code=refund_data.currency_code,
            contributing_extensions=attribution_data["contributing_extensions"],
            attribution_weights=attribution_data["attribution_weights"],
            # Store ONLY pre-tax attributed refund (sum of refunded attributed line subtotals)
            total_refunded_revenue=float(
                attribution_data.get("metadata", {}).get("refunded_attribution", 0.0)
            ),
            attributed_refund=attribution_data["attributed_refund"],
            total_interactions=attribution_data["total_interactions"],
            interactions_by_extension=attribution_data["interactions_by_extension"],
            attribution_algorithm="multi_touch",
            attribution_metadata=attribution_data["metadata"],
        )

        session.add(refund_attribution)
        await session.flush()  # Flush to get the ID if needed

        # 🔥 CRITICAL: Update trial revenue to reverse the attributed refund
        if attribution_data["attributed_refund"]:
            total_attributed_refund = sum(
                attribution_data["attributed_refund"].values()
            )
            if total_attributed_refund > 0:
                await self._update_trial_revenue_for_refund(
                    session, shop_id, total_attributed_refund, refund_attribution
                )

    async def _find_original_purchase_attribution(
        self, session: Any, shop_id: str, order_id: str
    ):
        """
        ✅ SCENARIO 11: Find original purchase attribution for refund

        Story: When a customer gets a refund, we need to find the original
        purchase attribution to reverse it proportionally.
        """
        from app.core.database.models.purchase_attribution import PurchaseAttribution

        query = select(PurchaseAttribution).where(
            and_(
                PurchaseAttribution.shop_id == shop_id,
                PurchaseAttribution.order_id == order_id,
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object."""
        if not datetime_str:
            return None
        try:
            from dateutil import parser

            return parser.parse(datetime_str)
        except Exception:
            return None

    def _extract_refund_amount(self, refund_obj: Dict[str, Any]) -> float:
        """Extract refund amount from refund object."""
        # Try different possible field names for refund amount
        total_refunded = refund_obj.get("total_refunded", {})
        if isinstance(total_refunded, dict):
            amount = total_refunded.get("amount", 0)
            return float(amount) if amount else 0.0

        # Fallback to direct field
        return float(
            refund_obj.get("total_refund_amount", refund_obj.get("amount", 0.0))
        )

    def _extract_refund_currency(self, refund_obj: Dict[str, Any]) -> str:
        """Extract currency from refund object."""
        # Try different possible field names for currency
        total_refunded = refund_obj.get("total_refunded", {})
        if isinstance(total_refunded, dict):
            currency = total_refunded.get("currency_code")
            if currency:
                return currency

        # Fallback to direct field
        return refund_obj.get("currency_code", "USD")

    async def _calculate_proportional_refund_attribution(
        self, original_attribution, refund_data: RefundData, order
    ):
        """
        ✅ SCENARIO 12: Calculate proportional refund attribution
        ✅ SCENARIO 16: Enhanced partial refund attribution

        Story: Calculate refund attribution based on which specific products were refunded
        and their individual attribution, not the overall order attribution ratio.
        """
        refund_amount = float(refund_data.total_refund_amount)
        original_revenue = float(original_attribution.total_revenue)

        # Check if this is a partial refund
        is_partial_refund = refund_amount < original_revenue

        # Get refund line items from RefundData
        refund_line_items = refund_data.refund_line_items or []

        # Debug logging
        logger.info(f"Refund line items: {refund_line_items}")
        logger.info(
            f"Contributing extensions: {original_attribution.contributing_extensions}"
        )

        # Debug: Print product IDs from refund line items
        refund_product_ids = []
        for refund_item in refund_line_items:
            line_item = refund_item.get("line_item", {})
            product_id = str(line_item.get("product", {}).get("id", ""))
            refund_product_ids.append(product_id)
        logger.info(f"Refund product IDs: {refund_product_ids}")

        # Debug: Print product IDs from contributing extensions
        contributing_product_ids = []
        for ext in original_attribution.contributing_extensions or []:
            contributing_product_ids.append(str(ext.get("product_id", "")))
        logger.info(f"Contributing product IDs: {contributing_product_ids}")

        # Calculate attribution for refunded products only
        refunded_attribution = 0.0
        refunded_products = []

        for refund_item in refund_line_items:
            # The refund line items structure is different - product_id is directly in the item
            product_id = str(refund_item.get("product_id", ""))
            refund_amount_item = float(refund_item.get("refund_amount", 0))

            logger.info(
                f"Processing refund item: product_id={product_id}, amount={refund_amount_item}"
            )

            # Check if this product was originally attributed
            contributing_extensions = original_attribution.contributing_extensions or []
            found_match = False
            for ext in contributing_extensions:
                ext_product_id = str(ext.get("product_id", ""))
                logger.info(
                    f"Comparing refund product {product_id} with contributing product {ext_product_id}"
                )
                if ext_product_id == product_id:
                    # This product was attributed, so 100% of its refund is attributed
                    refunded_attribution += refund_amount_item
                    refunded_products.append(
                        {
                            "product_id": product_id,
                            "refund_amount": refund_amount_item,
                            "attribution_weight": 1.0,
                        }
                    )
                    logger.info(
                        f"✅ MATCH FOUND: Product {product_id} was attributed, adding ${refund_amount_item} to refunded_attribution"
                    )
                    found_match = True
                    break

            if not found_match:
                logger.info(
                    f"❌ NO MATCH: Product {product_id} was not originally attributed"
                )

        # Calculate refund attribution ratio based on refunded attributed products
        refund_ratio = (
            refunded_attribution / original_revenue if original_revenue > 0 else 0
        )

        # Apply the refund attribution to the original extension weights
        original_weights = original_attribution.attribution_weights or {}
        refund_weights = {
            extension: weight * refund_ratio
            for extension, weight in original_weights.items()
        }

        # Calculate attributed refund amounts
        attributed_refund = {
            extension: refunded_attribution * weight
            for extension, weight in original_weights.items()
        }

        # ✅ SCENARIO 16: Enhanced metadata for partial refunds
        metadata = {
            "refund_ratio": refund_ratio,
            "original_attribution_id": original_attribution.id,
            "scenario": "product_specific_refund_attribution",
            "is_partial_refund": is_partial_refund,
            "remaining_revenue": original_revenue - refund_amount,
            "refund_percentage": (
                (refund_amount / original_revenue) * 100 if original_revenue > 0 else 0
            ),
            "refunded_attribution": refunded_attribution,
            "refunded_products": refunded_products,
            "total_refunded_products": len(refunded_products),
        }

        # Add partial refund specific metadata
        if is_partial_refund:
            metadata.update(
                {
                    "partial_refund_details": {
                        "refunded_amount": refund_amount,
                        "remaining_amount": original_revenue - refund_amount,
                        "refund_type": "partial",
                    }
                }
            )

        return {
            "contributing_extensions": list(
                original_attribution.contributing_extensions
            ),
            "attribution_weights": refund_weights,
            "attributed_refund": attributed_refund,
            "total_interactions": original_attribution.total_interactions,
            "interactions_by_extension": original_attribution.interactions_by_extension,
            "metadata": metadata,
        }

    def _compute_simplified_refund_attribution(
        self, refund_data: RefundData, order: Any
    ) -> Dict[str, Any]:
        """Compute simplified refund attribution using RefundData."""
        # Get customer interactions for attribution
        customer_id = getattr(order, "customerId", None)
        if not customer_id:
            return self._create_empty_attribution_data()

        # Load customer interactions (similar to purchase attribution)
        interactions = self._get_customer_interactions_for_refund(
            customer_id, getattr(order, "shopId", ""), order
        )

        if not interactions:
            return self._create_empty_attribution_data()

        # Compute attribution using same logic as purchase attribution
        total_refund_amount = float(refund_data.total_refund_amount)
        attribution_weights = self._compute_attribution_weights(interactions)

        # Calculate attributed refund per extension
        attributed_refund = {}
        contributing_extensions = []

        for extension, weight in attribution_weights.items():
            if weight > 0:
                attributed_amount = total_refund_amount * weight
                attributed_refund[extension] = attributed_amount
                contributing_extensions.append(extension)

        return {
            "contributing_extensions": contributing_extensions,
            "attribution_weights": attribution_weights,
            "attributed_refund": attributed_refund,
            "total_interactions": len(interactions),
            "interactions_by_extension": self._group_interactions_by_extension(
                interactions
            ),
            "metadata": {
                "computation_method": "simplified_refund_attribution",
                "refund_note": refund_data.note or "",
                "refund_restock": refund_data.restock,
                "total_refund_amount": total_refund_amount,
            },
        }

    def _get_customer_interactions_for_refund(
        self, customer_id: str, shop_id: str, order: Any
    ) -> List[Dict[str, Any]]:
        """Get customer interactions for refund attribution (reuse purchase attribution logic)."""
        # This would use the same logic as purchase attribution
        # For now, return empty list - this should be implemented based on existing purchase attribution logic
        return []

    def _create_empty_attribution_data(self) -> Dict[str, Any]:
        """Create empty attribution data when no interactions found."""
        return {
            "contributing_extensions": [],
            "attribution_weights": {},
            "attributed_refund": {},
            "total_interactions": 0,
            "interactions_by_extension": {},
            "metadata": {
                "computation_method": "no_interactions_found",
                "reason": "no_customer_interactions",
            },
        }

    async def _update_trial_revenue_for_refund(
        self,
        session: Any,
        shop_id: str,
        attributed_refund_amount: float,
        refund_attribution,
    ):
        """
        Update trial revenue to reverse the attributed refund amount.

        This is critical for proper trial revenue tracking when refunds occur.
        """
        try:
            from app.core.database.models.billing import BillingPlan
            from sqlalchemy import select, and_
            from decimal import Decimal

            # Get billing plan with lock to prevent race conditions
            billing_plan_query = (
                select(BillingPlan)
                .where(
                    and_(BillingPlan.shop_id == shop_id, BillingPlan.status == "active")
                )
                .with_for_update()
            )

            result = await session.execute(billing_plan_query)
            billing_plan = result.scalar_one_or_none()

            if not billing_plan:
                logger.warning(f"No active billing plan found for shop {shop_id}")
                return

            if not billing_plan.is_trial_active:
                logger.info(
                    f"Shop {shop_id} is not in trial - skipping trial revenue update"
                )
                return

            # Calculate new trial revenue (subtract the attributed refund)
            old_trial_revenue = float(billing_plan.trial_revenue or 0)
            new_trial_revenue = old_trial_revenue - attributed_refund_amount

            # Ensure trial revenue doesn't go below 0
            new_trial_revenue = max(0, new_trial_revenue)

            # Update billing plan
            billing_plan.trial_revenue = Decimal(str(new_trial_revenue))
            billing_plan.updated_at = datetime.utcnow()

            # Check if trial should be reactivated (if revenue falls below threshold)
            trial_threshold = float(billing_plan.trial_threshold or 0)
            if new_trial_revenue < trial_threshold and billing_plan.is_trial_active:
                # Trial is still active, no need to change
                pass
            elif (
                new_trial_revenue < trial_threshold and not billing_plan.is_trial_active
            ):
                # Trial was completed but now revenue is below threshold, reactivate
                billing_plan.is_trial_active = True
                logger.info(f"🔄 Trial reactivated for shop {shop_id} due to refund")
            elif new_trial_revenue >= trial_threshold and billing_plan.is_trial_active:
                # Revenue is above threshold, trial should be completed
                billing_plan.is_trial_active = False
                logger.info(
                    f"🎉 Trial completed for shop {shop_id} due to refund adjustment"
                )

            await session.commit()

            logger.info(
                f"📊 Trial revenue updated for refund: ${old_trial_revenue} → ${new_trial_revenue} "
                f"(reversed ${attributed_refund_amount})"
            )

        except Exception as e:
            logger.error(f"Failed to update trial revenue for refund: {e}")
            await session.rollback()
            raise

    def _compute_attribution_weights(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Compute attribution weights from interactions."""
        # This should use the same logic as purchase attribution
        # For now, return empty dict - this should be implemented based on existing purchase attribution logic
        return {}

    def _group_interactions_by_extension(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Group interactions by extension type."""
        # This should use the same logic as purchase attribution
        # For now, return empty dict - this should be implemented based on existing purchase attribution logic
        return {}
