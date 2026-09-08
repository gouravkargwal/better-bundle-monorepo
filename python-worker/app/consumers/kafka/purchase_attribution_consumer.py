"""
Kafka-based purchase attribution consumer for processing purchase attribution events
"""

import logging
from typing import Dict, Any, Optional, List
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
)
from app.core.database.models.offer_impression import OfferImpression
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

                # ✅ CHECK ORDER METAFIELDS FOR SESSION ID
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
                            f"⚠️ Session ID from metafields not found in database: {session_id_from_metafields}"
                        )
                        # Fall back to customer-based session lookup (already done above)
                        if user_session:
                            logger.info(
                                f"📌 Falling back to most recent customer session: {user_session.id}"
                            )
                        else:
                            logger.warning(
                                f"⚠️ No fallback session found for customer {customer_id}"
                            )

                # Extract order metafields for Apollo tracking data FIRST (needed for pre-check)
                order_metafields_list = None
                order_metafields = getattr(order, "metafields", None)
                if order_metafields:
                    if isinstance(order_metafields, list):
                        order_metafields_list = order_metafields
                    elif isinstance(order_metafields, dict):
                        # Convert dict to list format if needed
                        order_metafields_list = [
                            {
                                "namespace": k.split(".")[0] if "." in k else k,
                                "key": k.split(".")[1] if "." in k else k,
                                "value": v,
                            }
                            for k, v in order_metafields.items()
                        ]

                # Line-item properties / Apollo metafields are checked as well
                # as impressions, so an order carrying extension tracking data
                # is still processed if the impression row is missing.
                has_tracking_data = self._has_tracking_data_from_extensions(
                    products, order_metafields_list
                )
                has_impressions = await self._has_offer_impressions(
                    session, shop_id, customer_id, user_session
                )

                # Process if we have either tracking data OR a shown offer
                if not has_tracking_data and not has_impressions:
                    logger.debug(
                        f"⏭️ Skipping order {order_id} - no tracking data or offers shown"
                    )
                    return

                purchase_event = PurchaseEvent(
                    order_id=order_id,
                    customer_id=customer_id,
                    shop_id=shop_id,
                    session_id=getattr(user_session, "id", None),
                    total_amount=total_amount,
                    currency=currency,
                    products=products,
                    created_at=getattr(order, "order_date", None) or now_utc(),
                    updated_at=getattr(
                        order, "updated_at", None
                    ),  # For post-purchase additions
                    metadata={
                        "source": "normalization",
                        "line_item_count": len(products),
                    },
                    order_metafields=order_metafields_list,
                )

                # Process attribution
                billing = BillingServiceV2(session)
                await billing.process_purchase_attribution(purchase_event)

        except Exception as e:
            logger.error("Failed to process purchase attribution", error=str(e))
            raise

    async def _has_offer_impressions(
        self, session, shop_id: str, customer_id: str, user_session
    ) -> bool:
        """Whether we showed this shopper an offer that could be attributed.

        A cheap pre-filter so attribution does not run for every order in the
        store — only for shoppers we actually put an offer in front of.

        Reads `offer_impressions`, which is the only table that records offers
        shown. The old implementation queried `user_interactions`; that table
        has had no writer since the behaviour-tracking pipeline was removed, so
        the check returned False for every order and silently suppressed all
        attribution.

        Control impressions are excluded: a held-out shopper saw no offer, so
        nothing about their order is attributable.
        """
        try:
            cutoff_time = now_utc() - timedelta(days=30)

            conditions = [
                OfferImpression.shop_id == shop_id,
                OfferImpression.created_at >= cutoff_time,
                OfferImpression.is_control.is_(False),
            ]

            if customer_id:
                conditions.append(OfferImpression.customer_id == customer_id)
            elif user_session and getattr(user_session, "id", None):
                conditions.append(OfferImpression.session_id == user_session.id)
            else:
                # Nothing to join on. The attribution engine would attribute
                # zero anyway, so skip the work rather than scanning the shop.
                return False

            query = select(OfferImpression.id).where(and_(*conditions)).limit(1)
            result = await session.execute(query)
            return result.scalar_one_or_none() is not None

        except Exception as e:
            logger.error(f"Error checking offer impressions: {e}")
            # Err toward processing: the engine attributes zero when there is
            # nothing to find, so a false positive costs a query, not money.
            return True

    def _has_tracking_data_from_extensions(
        self,
        products: List[Dict[str, Any]],
        order_metafields: Optional[List[Dict[str, Any]]],
    ) -> bool:
        """
        Check if order has tracking data from extensions (line items or Apollo metafields).

        This is the PRIORITY source of truth - what extensions actually added to the order
        at checkout time, regardless of whether UserInteraction records exist.
        """
        # 1. Check for tracking in line item properties
        for product in products:
            properties = product.get("properties", {})
            if isinstance(properties, dict) and properties:
                extension = properties.get("_bb_rec_extension")
                if extension and extension.lower() in ["apollo", "mercury"]:
                    logger.debug(f"✅ Found tracking data in line item: {extension}")
                    return True

        # 2. Check for Apollo/Mercury tracking in order metafields
        if order_metafields:
            for metafield in order_metafields:
                if (
                    isinstance(metafield, dict)
                    and metafield.get("namespace") == "bb_recommendation"
                    and metafield.get("key") == "extension"
                ):
                    extension_value = metafield.get("value", "").lower()
                    if extension_value in ["apollo", "mercury"]:
                        logger.debug(
                            f"✅ Found tracking data in metafields: {extension_value}"
                        )
                        return True
                # Also check for Mercury products array (different structure)
                if (
                    isinstance(metafield, dict)
                    and metafield.get("namespace") == "bb_recommendation"
                    and metafield.get("key") == "products"
                ):
                    products_value = metafield.get("value")
                    if products_value:
                        logger.debug(f"✅ Found Mercury products array in metafields")
                        return True

        return False
