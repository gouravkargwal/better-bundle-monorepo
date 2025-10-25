"""
Kafka-based purchase attribution consumer for processing purchase attribution events
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.shared.helpers import now_utc
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.database.models import (
    OrderData,
    LineItemData,
    UserSession,
    UserInteraction,
)
from app.domains.billing.services.billing_service_v2 import BillingServiceV2
from app.domains.billing.models import PurchaseEvent
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class PurchaseAttributionKafkaConsumer:
    """Kafka consumer for purchase attribution jobs"""

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
                topics=["purchase-attribution-jobs"],
                group_id="purchase-attribution-processors",
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize purchase attribution consumer: {e}")
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
                    logger.error(f"Error processing purchase attribution message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in purchase attribution consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the purchase attribution consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": now_utc().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual purchase attribution messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            if payload.get("event_type") != "purchase_ready_for_attribution":
                return

            shop_id = payload.get("shop_id")
            order_id = payload.get("order_id")
            if not shop_id or not order_id:
                logger.error(
                    "Invalid purchase_ready_for_attribution payload", payload=payload
                )
                return

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for purchase attribution",
                    shop_id=shop_id,
                )
                # Send to DLQ instead of dropping
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="purchase-attribution-jobs",
                    error_details=f"Shop suspended at {now_utc().isoformat()}",
                )

                # Commit the message (remove from original queue)
                await self.consumer.commit(message)
                return

            # Use SQLAlchemy session for database operations
            async with get_transaction_context() as session:
                # Load normalized order and line items
                order_query = select(OrderData).where(
                    and_(
                        OrderData.shop_id == shop_id,
                        OrderData.order_id == str(order_id),
                    )
                )
                order_result = await session.execute(order_query)
                order = order_result.scalar_one_or_none()

                if not order:
                    logger.warning(
                        "OrderData not found for attribution",
                        shop_id=shop_id,
                        order_id=order_id,
                    )
                    return

                line_items_query = select(LineItemData).where(
                    LineItemData.order_id == order.id
                )
                line_items_result = await session.execute(line_items_query)
                line_items = line_items_result.scalars().all()

                # Construct PurchaseEvent
                products = []
                for li in line_items or []:
                    products.append(
                        {
                            "id": li.product_id,  # Updated to use SQLAlchemy field name
                            "variant_id": li.variant_id,
                            "quantity": li.quantity,
                            "price": li.price,
                            "properties": getattr(li, "properties", None) or {},
                        }
                    )

                total_amount = float(getattr(order, "total_amount", 0.0) or 0.0)
                currency = getattr(order, "currency_code", None) or "USD"
                customer_id = getattr(order, "customer_id", None)

                # ✅ CHECK ORDER METAFIELDS FOR SESSION ID (following Phoenix pattern)
                session_id_from_metafields = None
                order_metafields = getattr(order, "metafields", None)
                if order_metafields and isinstance(order_metafields, list):
                    for metafield in order_metafields:
                        if (
                            isinstance(metafield, dict)
                            and metafield.get("namespace") == "bb_recommendation"
                            and metafield.get("key") == "session_id"
                        ):
                            session_id_from_metafields = metafield.get("value")
                            logger.info(
                                f"✅ Found session ID in order metafields: {session_id_from_metafields}"
                            )
                            break

                # Try to find a recent session for this customer (optional)
                user_session = None
                if customer_id:
                    session_query = (
                        select(UserSession)
                        .where(
                            and_(
                                UserSession.shop_id == shop_id,
                                UserSession.customer_id == customer_id,
                            )
                        )
                        .order_by(UserSession.created_at.desc())
                        .limit(1)  # Only get the most recent session
                    )
                    session_result = await session.execute(session_query)
                    user_session = session_result.scalar_one_or_none()

                # ✅ PRIORITIZE SESSION ID FROM ORDER METAFIELDS (Apollo)
                if session_id_from_metafields:
                    # Find the specific session by ID from metafields
                    specific_session_query = (
                        select(UserSession)
                        .where(
                            and_(
                                UserSession.shop_id == shop_id,
                                UserSession.id == session_id_from_metafields,
                            )
                        )
                        .limit(1)
                    )
                    specific_session_result = await session.execute(
                        specific_session_query
                    )
                    specific_user_session = specific_session_result.scalar_one_or_none()

                    if specific_user_session:
                        user_session = specific_user_session
                        logger.info(
                            f"✅ Using session from order metafields: {session_id_from_metafields}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Session ID from metafields not found: {session_id_from_metafields}"
                        )

                # PRE-CHECK: Only process if customer has extension interactions
                has_interactions = await self._has_extension_interactions(
                    session, shop_id, customer_id, user_session
                )

                logger.info(
                    f"🔍 Extension interaction check for order {order_id}: "
                    f"shop_id={shop_id}, customer_id={customer_id}, "
                    f"has_interactions={has_interactions}"
                )

                # TEMPORARY: Process all orders for testing (remove this later)
                if not has_interactions:
                    logger.warning(
                        f"⚠️ No extension interactions found for order {order_id}, "
                        f"but processing anyway for testing"
                    )
                    # return  # Commented out for testing

                purchase_event = PurchaseEvent(
                    order_id=order_id,
                    customer_id=customer_id,
                    shop_id=shop_id,
                    session_id=getattr(user_session, "id", None),
                    total_amount=total_amount,
                    currency=currency,
                    products=products,
                    created_at=getattr(order, "order_date", None) or now_utc(),
                    metadata={
                        "source": "normalization",
                        "line_item_count": len(products),
                    },
                )

                # Process attribution
                billing = BillingServiceV2(session)
                await billing.process_purchase_attribution(purchase_event)

        except Exception as e:
            logger.error("Failed to process purchase attribution", error=str(e))
            raise

    async def _has_extension_interactions(
        self, session, shop_id: str, customer_id: str, user_session
    ) -> bool:
        """
        Check if customer has any extension interactions that could drive attribution.
        Only processes orders from customers who have interacted with our extensions.
        """
        try:
            # Check for interactions in the last 30 days
            cutoff_time = now_utc() - timedelta(days=30)

            logger.info(
                f"🔍 Checking extension interactions: shop_id={shop_id}, "
                f"customer_id={customer_id}, cutoff_time={cutoff_time}"
            )

            # Build query conditions
            query_conditions = [
                UserInteraction.shop_id == shop_id,
                UserInteraction.created_at >= cutoff_time,
                UserInteraction.extension_type.in_(
                    [
                        "phoenix",
                        "venus",
                        "apollo",
                    ]
                ),  # Attribution-eligible extensions
            ]

            # Add customer or session filter
            if customer_id:
                query_conditions.append(UserInteraction.customer_id == customer_id)
                logger.info(f"🔍 Filtering by customer_id: {customer_id}")
            elif user_session and hasattr(user_session, "id"):
                query_conditions.append(UserInteraction.session_id == user_session.id)
                logger.info(f"🔍 Filtering by session_id: {user_session.id}")
            else:
                logger.warning(
                    "🔍 No customer_id or session_id available for filtering"
                )

            # Check for any interactions from attribution-eligible extensions
            interactions_query = (
                select(UserInteraction).where(and_(*query_conditions)).limit(1)
            )  # We only need to know if any exist

            interactions_result = await session.execute(interactions_query)
            interactions = interactions_result.scalars().all()

            has_interactions = len(interactions) > 0

            logger.info(
                f"🔍 Found {len(interactions)} interactions for shop {shop_id}: "
                f"has_interactions={has_interactions}"
            )

            if interactions:
                for interaction in interactions:
                    logger.info(
                        f"🔍 Interaction: {interaction.extension_type} - "
                        f"{interaction.interaction_type} at {interaction.created_at}"
                    )

            return has_interactions

        except Exception as e:
            logger.error(f"Error checking extension interactions: {e}")
            # If we can't check, err on the side of processing to avoid missing attributions
            return True
