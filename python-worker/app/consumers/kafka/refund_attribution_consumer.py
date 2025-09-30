"""
Kafka-based refund attribution consumer for processing refund attribution events
"""

from typing import Any, Dict, List
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.database.models import RefundAttribution, RawOrder, OrderData
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

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["refund-attribution-jobs"],
                group_id="refund-attribution-processors",
            )

            self._initialized = True
            logger.info("Refund attribution Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize refund attribution consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting refund attribution consumer...")
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
        logger.info("Refund attribution consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the refund attribution consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual refund attribution messages"""
        try:
            logger.info(f"🔄 Processing refund attribution message: {message}")

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
            refund_id = message.get("refund_id")
            order_id = message.get("shopify_id") or message.get("order_id")

            # Robust refund_id extraction with fallback
            if not refund_id:
                refund_id = message.get("raw_record_id")
                if not refund_id:
                    logger.warning(
                        "⚠️ No refund_id or raw_record_id found in message, skipping refund attribution"
                    )
                    return

            if not shop_id or not refund_id:
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

            logger.info(
                f"📋 Processing individual refund attribution: shop_id={shop_id}, refund_id={refund_id}, order_id={order_id}"
            )

            # Use shared processing logic with SQLAlchemy session
            async with get_transaction_context() as session:
                await self._process_single_refund_attribution(
                    refund_id, shop_id, session
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

        logger.info(
            f"🔄 Processing batch refund attribution: shop_id={shop_id}, refund_count={len(refund_ids)}"
        )

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

            logger.info(
                f"✅ Batch refund attribution completed: successful={successful}, failed={failed}"
            )

        except Exception as e:
            logger.error(f"Failed to process batch refund attribution: {e}")
            raise

    async def _process_single_refund_attribution(
        self, refund_id: str, shop_id: str, session: Any
    ):
        """Process attribution for a single refund using single RefundAttribution table."""
        # Check if attribution already exists (idempotency)
        existing_attribution_query = select(RefundAttribution).where(
            and_(
                RefundAttribution.shop_id == shop_id,
                RefundAttribution.refund_id == refund_id,
            )
        )
        existing_attribution_result = await session.execute(existing_attribution_query)
        existing_attribution = existing_attribution_result.scalar_one_or_none()

        if existing_attribution:
            logger.info(
                f"✅ Refund attribution already exists - skipping",
                shop_id=shop_id,
                refund_id=refund_id,
            )
            return

        # Load refund data from RawOrder (single source of truth)
        raw_order_query = select(RawOrder).where(
            and_(RawOrder.shop_id == shop_id, RawOrder.shopify_id == refund_id)
        )
        raw_order_result = await session.execute(raw_order_query)
        raw_order = raw_order_result.scalar_one_or_none()

        if not raw_order or not raw_order.payload:
            logger.warning(
                "RawOrder not found for refund attribution",
                shop_id=shop_id,
                refund_id=refund_id,
            )
            return

        # Extract refund data from RawOrder payload
        payload_data = raw_order.payload if isinstance(raw_order.payload, dict) else {}
        refunds = payload_data.get("refunds", [])

        # Find the specific refund
        refund_obj = None
        for refund in refunds:
            if str(refund.get("id", "")) == refund_id:
                refund_obj = refund
                break

        if not refund_obj:
            logger.warning(
                "Refund not found in RawOrder payload",
                shop_id=shop_id,
                refund_id=refund_id,
            )
            return

        # Load original order for customer and session data
        order_id = str(payload_data.get("id", ""))
        order_query = select(OrderData).where(
            and_(OrderData.shop_id == shop_id, OrderData.order_id == order_id)
        )
        order_result = await session.execute(order_query)
        order = order_result.scalar_one_or_none()

        if not order:
            logger.warning(
                "OrderData not found for refund attribution",
                shop_id=shop_id,
                order_id=order_id,
            )
            return

        # Compute attribution using simplified logic
        attribution_data = self._compute_simplified_refund_attribution(
            refund_obj, order, payload_data
        )

        # Create single RefundAttribution record
        refund_attribution = RefundAttribution(
            shop_id=shop_id,
            customer_id=order.customer_id,
            session_id=getattr(order, "session_id", None),
            order_id=order_id,
            refund_id=refund_id,
            refunded_at=refund_obj.get("created_at", datetime.utcnow()),
            total_refund_amount=float(refund_obj.get("total_refund_amount", 0.0)),
            currency_code=refund_obj.get("currency_code", "USD"),
            contributing_extensions=attribution_data["contributing_extensions"],
            attribution_weights=attribution_data["attribution_weights"],
            total_refunded_revenue=float(refund_obj.get("total_refund_amount", 0.0)),
            attributed_refund=attribution_data["attributed_refund"],
            total_interactions=attribution_data["total_interactions"],
            interactions_by_extension=attribution_data["interactions_by_extension"],
            attribution_algorithm="multi_touch",
            attribution_metadata=attribution_data["metadata"],
        )

        session.add(refund_attribution)
        await session.flush()  # Flush to get the ID if needed

        logger.info(
            f"✅ Refund attribution created successfully",
            shop_id=shop_id,
            order_id=order_id,
            refund_id=refund_id,
            attributed_refund=attribution_data["attributed_refund"],
        )

    def _compute_simplified_refund_attribution(
        self, refund_obj: Dict[str, Any], order: Any, payload_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute simplified refund attribution using RawOrder data."""
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
        total_refund_amount = float(refund_obj.get("total_refund_amount", 0.0))
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
                "refund_note": refund_obj.get("note", ""),
                "refund_restock": refund_obj.get("restock", False),
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
