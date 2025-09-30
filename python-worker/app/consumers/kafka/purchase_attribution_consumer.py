"""
Kafka-based purchase attribution consumer for processing purchase attribution events
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.database.simple_db_client import get_database
from app.domains.billing.services.billing_service import BillingService
from app.domains.billing.models import PurchaseEvent
from app.core.logging import get_logger

logger = get_logger(__name__)


class PurchaseAttributionKafkaConsumer:
    """Kafka consumer for purchase attribution jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["purchase-attribution-jobs"],
                group_id="purchase-attribution-processors",
            )

            self._initialized = True
            logger.info("Purchase attribution Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize purchase attribution consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting purchase attribution consumer...")
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
        logger.info("Purchase attribution consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the purchase attribution consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual purchase attribution messages"""
        try:
            logger.info(f"🔄 Processing purchase attribution message: {message}")

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

            db = await get_database()

            # Load normalized order and line items
            order = await db.orderdata.find_first(
                where={"shopId": shop_id, "orderId": str(order_id)}
            )
            if not order:
                logger.warning(
                    "OrderData not found for attribution",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

            line_items = await db.lineitemdata.find_many(where={"orderId": order.id})

            # Construct PurchaseEvent
            products = []
            for li in line_items or []:
                products.append(
                    {
                        "id": li.productId,  # Changed from product_id to id
                        "variant_id": li.variantId,
                        "quantity": li.quantity,
                        "price": li.price,
                        "properties": getattr(li, "properties", None) or {},
                    }
                )

            total_amount = float(getattr(order, "totalAmount", 0.0) or 0.0)
            currency = getattr(order, "currencyCode", None) or "USD"
            customer_id = getattr(order, "customerId", None)

            logger.info(
                f"🔍 Created {len(products)} products for order {order_id}: {products}"
            )

            # Try to find a recent session for this customer (optional)
            session = None
            if customer_id:
                session = await db.usersession.find_first(
                    where={"shopId": shop_id, "customerId": customer_id},
                    order={"createdAt": "desc"},
                )

            # PRE-CHECK: Only process if customer has extension interactions
            if not await self._has_extension_interactions(
                db, shop_id, customer_id, session
            ):
                logger.info(
                    f"⏭️ Skipping attribution for order {order_id} - no extension interactions found",
                    shop_id=shop_id,
                    customer_id=customer_id,
                )
                return

            purchase_event = PurchaseEvent(
                order_id=order_id,
                customer_id=customer_id,
                shop_id=shop_id,
                session_id=getattr(session, "id", None),
                total_amount=total_amount,
                currency=currency,
                products=products,
                created_at=getattr(order, "orderDate", None) or datetime.utcnow(),
                metadata={
                    "source": "normalization",
                    "line_item_count": len(products),
                },
            )

            # Process attribution
            billing = BillingService(await get_database())
            await billing.process_purchase_attribution(purchase_event)

            logger.info(
                "Purchase attribution stored",
                shop_id=shop_id,
                order_id=order_id,
                line_items=len(products),
            )

        except Exception as e:
            logger.error("Failed to process purchase attribution", error=str(e))
            raise

    async def _has_extension_interactions(
        self, db, shop_id: str, customer_id: str, session
    ) -> bool:
        """
        Check if customer has any extension interactions that could drive attribution.
        Only processes orders from customers who have interacted with our extensions.
        """
        try:
            # Check for interactions in the last 30 days
            cutoff_time = datetime.utcnow() - timedelta(days=30)

            # Build query conditions
            where_conditions = {
                "shopId": shop_id,
                "createdAt": {"gte": cutoff_time},
            }

            # Add customer or session filter
            if customer_id:
                where_conditions["customerId"] = customer_id
            elif session and hasattr(session, "id"):
                where_conditions["sessionId"] = session.id

            # Check for any interactions from attribution-eligible extensions
            # (Phoenix, Venus, Apollo - excluding Atlas web pixel tracking)
            interactions = await db.userinteraction.find_many(
                where={
                    **where_conditions,
                    "extensionType": {
                        "in": [
                            "phoenix",
                            "venus",
                            "apollo",
                        ]  # Attribution-eligible extensions
                    },
                },
                take=1,  # We only need to know if any exist
            )

            has_interactions = len(interactions) > 0

            if has_interactions:
                logger.info(
                    f"✅ Found {len(interactions)} extension interactions for customer {customer_id}",
                    shop_id=shop_id,
                    customer_id=customer_id,
                )
            else:
                logger.info(
                    f"❌ No extension interactions found for customer {customer_id}",
                    shop_id=shop_id,
                    customer_id=customer_id,
                )

            return has_interactions

        except Exception as e:
            logger.error(f"Error checking extension interactions: {e}")
            # If we can't check, err on the side of processing to avoid missing attributions
            return True
