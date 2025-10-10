# app/core/services/dlq_service.py

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.shared.helpers import now_utc
from app.core.messaging.event_publisher import EventPublisher
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.database.models.shop import Shop
from sqlalchemy import select
from app.core.logging import get_logger

logger = get_logger(__name__)


class DLQService:
    """Service for managing Dead Letter Queue operations"""

    def __init__(self):
        self.publisher = EventPublisher(kafka_settings.model_dump())

    async def send_to_dlq(
        self,
        original_message: Dict[str, Any],
        reason: str,
        original_topic: str,
        error_details: Optional[str] = None,
        retry_count: int = 0,
    ) -> bool:
        """
        Send a message to the Dead Letter Queue

        Args:
            original_message: The original message that failed
            reason: Reason for sending to DLQ (e.g., "shop_suspended")
            original_topic: The topic the message came from
            error_details: Additional error information
            retry_count: Number of times this message has been retried

        Returns:
            True if successfully sent to DLQ
        """
        try:
            # Enrich message with DLQ metadata
            dlq_message = {
                "original_message": original_message,
                "dlq_metadata": {
                    "reason": reason,
                    "original_topic": original_topic,
                    "original_timestamp": original_message.get(
                        "timestamp", now_utc().isoformat()
                    ),
                    "dlq_timestamp": now_utc().isoformat(),
                    "error_details": error_details,
                    "retry_count": retry_count,
                    "shop_id": original_message.get("shop_id"),
                    "event_type": original_message.get("event_type"),
                },
                "headers": {
                    "x-dlq-reason": reason,
                    "x-original-topic": original_topic,
                    "x-retry-count": str(retry_count),
                },
            }

            # Send to DLQ topic
            await self.publisher.publish(
                topic="suspended-shop-events", message=dlq_message
            )

            logger.info(
                f"📬 Message sent to DLQ - shop_id: {original_message.get('shop_id')}, "
                f"reason: {reason}, event: {original_message.get('event_type')}"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to send message to DLQ: {e}")
            return False

    async def get_dlq_messages_for_shop(
        self, shop_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all DLQ messages for a specific shop

        This is used when a shop reactivates to reprocess their events
        """
        try:
            messages = []

            # Create a consumer for the DLQ topic
            consumer = KafkaConsumer(kafka_settings.model_dump())
            await consumer.initialize(
                topics=["suspended-shop-events"],
                group_id=f"dlq-retrieval-{shop_id}-{now_utc().timestamp()}",
            )

            # Read messages from the beginning
            message_count = 0
            async for kafka_message in consumer.consume():
                try:
                    message_data = kafka_message["value"]

                    # Filter for this shop
                    if message_data.get("dlq_metadata", {}).get("shop_id") == shop_id:
                        messages.append(message_data)
                        message_count += 1

                        if message_count >= limit:
                            break

                except Exception as e:
                    logger.error(f"Error reading DLQ message: {e}")
                    continue

            await consumer.close()

            logger.info(f"📦 Retrieved {len(messages)} DLQ messages for shop {shop_id}")
            return messages

        except Exception as e:
            logger.error(f"❌ Failed to retrieve DLQ messages: {e}")
            return []

    async def reprocess_shop_dlq_messages(
        self, shop_id: str, max_messages: int = 1000
    ) -> Dict[str, Any]:
        """
        Reprocess all DLQ messages for a shop after reactivation

        Returns:
            Statistics about reprocessing (success count, failure count, etc.)
        """
        try:
            logger.info(f"🔄 Starting DLQ reprocessing for shop {shop_id}")

            # Check if shop is now active
            async with get_transaction_context() as session:
                result = await session.execute(select(Shop).where(Shop.id == shop_id))
                shop = result.scalar_one_or_none()

                if not shop or not shop.is_active:
                    logger.warning(
                        f"Shop {shop_id} is not active, skipping reprocessing"
                    )
                    return {"success": False, "reason": "shop_not_active"}

            # Get all DLQ messages for this shop
            dlq_messages = await self.get_dlq_messages_for_shop(shop_id, max_messages)

            stats = {
                "total_messages": len(dlq_messages),
                "successfully_reprocessed": 0,
                "failed_reprocessing": 0,
                "errors": [],
            }

            # Reprocess each message
            for dlq_message in dlq_messages:
                try:
                    original_message = dlq_message["original_message"]
                    original_topic = dlq_message["dlq_metadata"]["original_topic"]

                    # Republish to original topic for reprocessing
                    await self.publisher.publish(
                        topic=original_topic, message=original_message
                    )

                    stats["successfully_reprocessed"] += 1

                except Exception as e:
                    stats["failed_reprocessing"] += 1
                    stats["errors"].append(
                        {"message_id": dlq_message.get("id"), "error": str(e)}
                    )
                    logger.error(f"Failed to reprocess message: {e}")

            logger.info(
                f"✅ DLQ reprocessing complete for shop {shop_id}: "
                f"{stats['successfully_reprocessed']}/{stats['total_messages']} messages reprocessed"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ Failed to reprocess DLQ messages: {e}")
            return {"success": False, "error": str(e)}

    async def purge_shop_dlq_messages(self, shop_id: str) -> bool:
        """
        Remove all DLQ messages for a shop (used when shop uninstalls)

        Note: In Kafka, you can't delete specific messages, so we mark them as processed
        """
        logger.info(f"🗑️ Purging DLQ messages for shop {shop_id}")
        # Implementation depends on your requirements
        # Could involve marking messages in a database or just letting them expire
        return True
