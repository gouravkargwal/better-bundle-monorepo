"""
Shopify Events Stream Consumer for BetterBundle Python Worker

This consumer processes Shopify webhook events from Redis Streams in real-time,
moving data from raw tables to main tables and triggering downstream processing.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.domains.ml.services.feature_engineering import FeatureEngineeringService
from app.core.logging import get_logger
from app.core.redis_client import streams_manager


class ShopifyEventsConsumer(BaseConsumer):
    """
    Real-time consumer that processes Shopify webhook events from Redis Streams
    """

    def __init__(self):
        # Stream configuration
        stream_name = "betterbundle:shopify-events"
        consumer_group = "shopify-processors"
        consumer_name = f"processor-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Initialize parent with required parameters
        super().__init__(
            stream_name=stream_name,
            consumer_group=consumer_group,
            consumer_name=consumer_name,
        )

        self.logger = get_logger(__name__)

        # Services
        self.main_table_service = MainTableStorageService()
        self.feature_service = FeatureEngineeringService()

        # Processing metrics
        self.processed_count = 0
        self.error_count = 0

        # Deduplication tracking
        self.processed_orders: Dict[str, str] = {}  # order_id -> last_event_type

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single Shopify event message (override from BaseConsumer)"""
        try:
            # Redis streams return data in array-like format with numeric keys
            # Convert to proper field mapping
            message_data = {}

            # Handle Redis Stream message format: {'0': 'event_type', '1': 'product_updated', ...}
            if "0" in message and "1" in message:
                # Convert array-like format to proper field names
                message_data = {
                    "event_type": message.get("1"),
                    "shop_id": message.get("3"),
                    "shopify_id": message.get("5"),
                    "timestamp": message.get("7"),
                }
            else:
                # Fallback to direct field access
                message_data = message

            event_type = message_data.get("event_type")
            shop_id = message_data.get("shop_id")
            shopify_id = message_data.get("shopify_id")
            timestamp_str = message_data.get("timestamp")

            if not all([event_type, shop_id, shopify_id, timestamp_str]):
                self.logger.error(
                    f"Invalid message: missing required fields: {message_data}"
                )
                return

            # Create unique order key for deduplication
            order_key = f"{shop_id}_{shopify_id}"

            # Check for duplicate processing
            if event_type in [
                "order_created",
                "order_updated",
                "order_paid",
                "order_cancelled",
            ]:
                if order_key in self.processed_orders:
                    last_event = self.processed_orders[order_key]
                    # Skip if we already processed a more important event
                    if (last_event == "order_paid" and event_type != "order_paid") or (
                        last_event == "order_updated" and event_type == "order_created"
                    ):
                        self.logger.info(
                            f"⏭️ Skipping duplicate order event: {event_type} for {order_key} (already processed {last_event})"
                        )
                        return

                # Update tracking
                self.processed_orders[order_key] = event_type

            self.logger.info(
                f"Processing {event_type} event for shop {shop_id}, Shopify ID: {shopify_id}"
            )

            # Route to appropriate handler based on event type
            if event_type == "product_created" or event_type == "product_updated":
                await self._process_product_event(shop_id, shopify_id)
            elif event_type in [
                "order_created",
                "order_updated",
                "order_paid",
                "order_cancelled",
            ]:
                await self._process_order_event(shop_id, shopify_id)
            elif event_type == "customer_created" or event_type == "customer_updated":
                await self._process_customer_event(shop_id, shopify_id)
            elif (
                event_type == "collection_created" or event_type == "collection_updated"
            ):
                await self._process_collection_event(shop_id, shopify_id)
            else:
                self.logger.warning(f"Unknown event type: {event_type}")

            self.processed_count += 1

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            self.error_count += 1
            raise  # Re-raise to trigger circuit breaker

    async def _process_product_event(self, shop_id: str, shopify_id: str):
        """Process a product event"""
        self.logger.info(
            f"Processing product event for shop {shop_id}, product {shopify_id}"
        )

        # Move data from raw tables to main tables
        await self.main_table_service._store_data_generic(
            data_type="products", shop_id=shop_id, incremental=True
        )

        # Trigger feature computation and Gorse sync
        await self._trigger_ml_pipeline(shop_id, "product_event")

        self.logger.info(f"Successfully processed product event for shop {shop_id}")

    async def _process_order_event(self, shop_id: str, shopify_id: str):
        """Process an order event"""
        self.logger.info(
            f"Processing order event for shop {shop_id}, order {shopify_id}"
        )

        # Move data from raw tables to main tables
        await self.main_table_service._store_data_generic(
            data_type="orders", shop_id=shop_id, incremental=True
        )

        # Trigger feature computation and Gorse sync
        await self._trigger_ml_pipeline(shop_id, "order_event")

        self.logger.info(f"Successfully processed order event for shop {shop_id}")

    async def _process_customer_event(self, shop_id: str, shopify_id: str):
        """Process a customer event"""
        self.logger.info(
            f"Processing customer event for shop {shop_id}, customer {shopify_id}"
        )

        # Move data from raw tables to main tables
        await self.main_table_service._store_data_generic(
            data_type="customers", shop_id=shop_id, incremental=True
        )

        # Trigger feature computation and Gorse sync
        await self._trigger_ml_pipeline(shop_id, "customer_event")

        self.logger.info(f"Successfully processed customer event for shop {shop_id}")

    async def _process_collection_event(self, shop_id: str, shopify_id: str):
        """Process a collection event"""
        self.logger.info(
            f"Processing collection event for shop {shop_id}, collection {shopify_id}"
        )

        # Move data from raw tables to main tables
        await self.main_table_service._store_data_generic(
            data_type="collections", shop_id=shop_id, incremental=True
        )

        # Trigger feature computation and Gorse sync
        await self._trigger_ml_pipeline(shop_id, "collection_event")

        self.logger.info(f"Successfully processed collection event for shop {shop_id}")

    async def _trigger_ml_pipeline(self, shop_id: str, event_type: str):
        """Trigger feature computation and Gorse sync for the shop"""
        try:
            self.logger.info(
                f"Triggering ML pipeline for shop {shop_id} after {event_type}"
            )

            # Run comprehensive feature computation pipeline
            feature_results = (
                await self.feature_service.run_comprehensive_pipeline_for_shop(
                    shop_id=shop_id,
                    incremental=True,
                )
            )

            self.logger.info(
                f"Feature computation completed for shop {shop_id}",
                feature_results=feature_results,
            )

        except Exception as e:
            self.logger.error(f"Failed to trigger ML pipeline for shop {shop_id}: {e}")
            # Don't raise the exception - we don't want ML pipeline failures to break the consumer

    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        return {
            "status": self.status.value,
            "metrics": {
                "messages_processed": self.processed_count,
                "messages_failed": self.error_count,
            },
            "stream_name": self.stream_name,
            "consumer_group": self.consumer_group,
            "consumer_name": self.consumer_name,
        }
