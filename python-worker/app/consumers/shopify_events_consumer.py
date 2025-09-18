from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.core.stream_manager import stream_manager, StreamType

logger = get_logger(__name__)


class ShopifyEventsConsumer(BaseConsumer):
    """Consumes events from betterbundle:shopify-events and forwards them to betterbundle:data-jobs"""

    def __init__(self) -> None:
        super().__init__(
            stream_name="betterbundle:shopify-events",
            consumer_group="shopify-events-consumer-group",
            consumer_name="shopify-events-consumer",
            batch_size=10,
            poll_timeout=1000,
            max_retries=3,
            retry_delay=0.5,
        )
        self.logger = get_logger(__name__)

    async def _process_single_message(self, message: Dict[str, Any]):
        try:
            # Debug: Log which stream this message came from
            stream_name = message.get("_stream_name", "unknown")
            self.logger.info(f"🔍 Message received from stream: {stream_name}")

            # Redis stream messages use numbered keys, so we need to parse them differently
            # The format is: {'0': 'event_type', '1': 'product_updated', '2': 'shop_id', '3': 'shop_id_value', ...}
            event_type = message.get("1")  # event_type is at position 1
            shop_id = message.get("3")  # shop_id is at position 3
            shopify_id = message.get("5")  # shopify_id is at position 5
            timestamp = message.get("7")  # timestamp is at position 7

            self.logger.info(
                f"📥 Received Shopify event: {event_type} for shop {shop_id}, product {shopify_id}"
            )

            # Skip normalize_entity events (these are our own forwarded messages)
            if event_type == "normalize_entity":
                self.logger.info(
                    "⏭️ Skipping normalize_entity event (our own forwarded message)"
                )
                return

            # Only process original Shopify webhook events, not our own forwarded messages
            if event_type in [
                "product_updated",
                "product_created",
                "product_deleted",
                "order_paid",
                "refund_created",
                "customer_created",
                "customer_updated",
                "collection_created",
                "collection_updated",
                "collection_deleted",
            ]:
                # Create a normalize_entity job for the event
                normalize_job = {
                    "event_type": "normalize_entity",
                    "data_type": self._get_entity_type(event_type),
                    "format": "rest",  # All webhook events are REST format
                    "shop_id": str(shop_id),  # Ensure string
                    "shopify_id": shopify_id,  # Keep as integer - NormalizeJob now accepts both
                    "timestamp": datetime.utcnow(),  # Keep as datetime object
                    "original_event_type": event_type,  # Pass the original Shopify event type
                }

                # Publish to normalization stream using stream manager
                message_id = await stream_manager.publish_to_domain(
                    StreamType.NORMALIZATION, normalize_job
                )

                self.logger.info(
                    f"📤 Forwarded {event_type} to normalization stream: {message_id}"
                )
            else:
                self.logger.warning(f"⚠️ Unknown event type: {event_type}")

        except Exception as e:
            self.logger.error(f"❌ Error processing Shopify event: {e}")
            raise

    def _get_entity_type(self, event_type: str) -> str:
        """Map event type to entity type"""
        mapping = {
            "product_updated": "products",
            "product_created": "products",
            "product_deleted": "products",
            "order_paid": "orders",
            "refund_created": "refunds",
            "customer_created": "customers",
            "customer_updated": "customers",
            "customer_redacted": "customers",
            "collection_created": "collections",
            "collection_updated": "collections",
            "collection_deleted": "collections",
        }
        return mapping.get(event_type, "unknown")
