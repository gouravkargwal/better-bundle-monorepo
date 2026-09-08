"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
from typing import Dict, Any
from datetime import datetime

from app.shared.helpers import now_utc
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.domains.shopify.services.normalisation_service import (
    NormalizationService,
)
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False
        self.normalization_service = NormalizationService()
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize normalization consumer: {e}")
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
                    logger.error(f"Error processing normalization message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in normalization consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the normalization consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": now_utc().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual normalization messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")
            shop_id = payload.get("shop_id")
            if not shop_id:
                logger.error("❌ Invalid normalization event: missing shop_id")
                return

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for normalization",
                    shop_id=shop_id,
                )
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="normalization-jobs",
                    error_details=f"Shop suspended at {now_utc().isoformat()}",
                )
                await self.consumer.commit(message)
                return

            if event_type == "normalize_data":
                await self._handle_unified_normalization(payload)

        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_unified_normalization(self, payload: Dict[str, Any]):
        """Unified normalization handler - no complex mode switching"""
        try:
            shop_id = payload.get("shop_id")
            data_type = payload.get("data_type")
            format_type = payload.get("format", "graphql")
            shopify_id = payload.get("shopify_id")
            source = payload.get("source", "unknown")

            # Create simplified normalization parameters
            normalization_params = {
                "shopify_id": shopify_id,
                "format": format_type,
                "source": source,
            }

            # Use unified normalization method
            success = await self.normalization_service.normalize_data(
                shop_id, data_type, normalization_params
            )

            if success:
                # Trigger feature computation for the processed data type
                await self.normalization_service.feature_service.trigger_feature_computation(
                    shop_id, data_type
                )

                # Keep recommendation edges in step with the new data
                await self._refresh_edges_if_needed(shop_id, data_type)
            else:
                logger.error(f"❌ Normalization failed for {data_type}")
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise

    async def _refresh_edges_if_needed(self, shop_id: str, data_type: str):
        """Keep `product_edges` in step with newly normalized data.

        Two different refreshes, because the two halves of an edge score come
        from different places:

        - order data changes what customers actually bought together, so the
          co-purchase LLR is re-mined.
        - product data changes the catalog, so the affected products are
          re-embedded, re-enriched and re-resolved into fresh priors. This is
          the incremental path: adding five products costs one LLM call, not a
          full catalog pass.

        Both run detached. A slow refresh must never hold up normalization, and
        a failed one must never fail it either — the edges simply stay at their
        previous values until the next event or the nightly batch.
        """
        import asyncio

        try:
            kind = (data_type or "").lower()

            order_types = {
                "orders", "order", "order_data", "line_item", "line_item_data",
                "order_paid", "order_updated", "order_created",
            }
            product_types = {
                "products", "product", "product_data",
                "product_created", "product_updated",
            }

            if kind in order_types:
                logger.info(f"🔄 Re-mining co-purchases for shop {shop_id} ({kind})")
                self._detach(self._mine_copurchases(shop_id), "co-purchase mining")
            elif kind in product_types:
                logger.info(f"🔄 Refreshing catalog priors for shop {shop_id} ({kind})")
                self._detach(self._refresh_catalog(shop_id), "catalog refresh")

        except Exception as e:
            logger.error(f"Failed to schedule edge refresh: {e}")
            # Never raise: normalization succeeded and must not be rolled back.

    def _detach(self, coro, label: str):
        """Fire and forget, but surface the failure if there is one."""
        import asyncio

        task = asyncio.create_task(coro)
        task.add_done_callback(
            lambda t: logger.error(f"❌ {label} failed: {t.exception()}")
            if not t.cancelled() and t.exception()
            else None
        )

    async def _mine_copurchases(self, shop_id: str):
        from app.recommandations.edges.cooccurrence import CoPurchaseMiner

        result = await CoPurchaseMiner().run(shop_id)
        logger.info(
            f"✅ Co-purchase mining for shop {shop_id}: "
            f"{result.get('pairs', 0)} pairs over "
            f"{result.get('total_orders', 0)} orders"
        )

    async def _refresh_catalog(self, shop_id: str):
        from app.recommandations.edges.install import EdgeInstallPipeline

        report = await EdgeInstallPipeline().run(shop_id)
        logger.info(f"✅ Catalog refresh for shop {shop_id}: {report.as_dict()}")

