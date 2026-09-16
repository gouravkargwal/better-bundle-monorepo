import asyncio
from datetime import datetime
from typing import Dict, Any

from app.shared.helpers import now_utc
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.services.shop_cache_service import get_shop_cache_service
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class DataCollectionKafkaConsumer:
    """Kafka consumer for data collection jobs - handles events directly"""

    def __init__(self, shopify_service=None):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.shopify_service = shopify_service
        self.shop_repo = ShopRepository()
        self._initialized = False
        self.dlq_service = DLQService()

        # How many messages to work on at once. Kept modest: each one makes
        # Shopify calls, and max_poll_interval_ms still has to cover the
        # slowest message in a batch.
        self.MAX_CONCURRENT_MESSAGES = 10
        # Longest a partially filled batch waits before being processed.
        self.BATCH_WAIT_SECONDS = 2.0

    async def initialize(self):
        """Initialize consumer"""
        try:
            if not self.shopify_service:
                raise ValueError(
                    "Shopify service is required for data collection consumer"
                )

            await self.consumer.initialize(
                topics=["data-collection-jobs", "shopify-events"],
                group_id="data-collection-processors",
            )

            self._initialized = True

        except Exception as e:
            logger.exception(f"❌ Failed to initialize data collection consumer: {e}")
            raise

    async def start_consuming(self):
        """Consume in small concurrent batches.

        One-message-at-a-time was the shape of the problem: each webhook takes
        seconds (a Shopify fetch, a write, a publish), so a single serial
        consumer topped out near 0.2 messages/second while a bulk catalog
        change produced them four times faster. The lag grew without bound and
        never drained.

        Messages are taken in batches, run concurrently, and the batch is
        committed only once every message in it has finished. Committing at the
        batch boundary keeps the usual Kafka guarantee — a committed offset
        means everything before it is done — so a crash mid-batch replays the
        whole batch rather than losing the slow messages in it. Replay is safe
        because storage is an upsert.
        """
        if not self._initialized:
            await self.initialize()

        # A reader task feeds a queue, and the batcher waits on the queue.
        #
        # The batcher needs a timeout so a partial batch still gets processed
        # when traffic is thin. Applying that timeout directly to the consumer
        # iterator is what it must not do: asyncio.wait_for cancels whatever it
        # is waiting on, so every idle window tore down an in-flight Kafka
        # fetch. Throughput collapsed to a trickle even though each message
        # only takes about a second. Cancelling a queue get is harmless.
        queue: asyncio.Queue = asyncio.Queue(
            maxsize=self.MAX_CONCURRENT_MESSAGES * 2
        )
        reader = asyncio.create_task(self._fill_queue(queue))

        batch: list = []
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=self.BATCH_WAIT_SECONDS
                    )
                except asyncio.TimeoutError:
                    if batch:
                        await self._process_batch(batch)
                        batch = []
                    if reader.done():
                        break
                    continue

                if message is None:  # reader finished
                    break

                batch.append(message)
                if len(batch) >= self.MAX_CONCURRENT_MESSAGES:
                    await self._process_batch(batch)
                    batch = []
        except Exception as e:
            logger.exception(f"❌ Error in data collection consumer: {e}")
            raise
        finally:
            if batch:
                await self._process_batch(batch)
            reader.cancel()
            try:
                await reader
            except (asyncio.CancelledError, Exception):
                pass

    async def _fill_queue(self, queue: asyncio.Queue) -> None:
        """Read the consumer into `queue`, blocking when the batcher is busy.

        The queue is bounded, so this backs off naturally instead of reading
        the whole backlog into memory.
        """
        try:
            async for message in self.consumer.consume():
                await queue.put(message)
        finally:
            await queue.put(None)

    async def _process_batch(self, batch: list) -> None:
        """Run a batch concurrently, then commit up to its last message."""
        results = await asyncio.gather(
            *(self._handle_message(m) for m in batch), return_exceptions=True
        )

        for message, result in zip(batch, results):
            if isinstance(result, BaseException):
                logger.error(
                    f"Error processing data collection message at offset "
                    f"{message.get('offset')}: {result}"
                )

        # Commit the batch's furthest offset per partition. Messages that
        # failed are logged above and not retried here; the collection path
        # does its own retry and DLQs what it cannot complete.
        furthest = {}
        for message in batch:
            key = (message.get("topic"), message.get("partition"))
            if message.get("offset", -1) >= furthest.get(key, (None, -1))[1]:
                furthest[key] = (message, message.get("offset", -1))

        for message, _ in furthest.values():
            try:
                await self.consumer.commit(message)
            except Exception as e:
                logger.error(f"Failed to commit offset: {e}")

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual data collection messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            event_type = payload.get("event_type")

            # Resolve shop data once for all event types
            shop_data = await self._resolve_shop_data(payload)
            if not shop_data:
                return
            if not shop_data.get("is_active"):
                logger.warning(f"❌ Shop {shop_data.get('id')} is suspended")
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="data-collection-jobs",
                    error_details=f"Shop suspended at {now_utc().isoformat()}",
                )
                await self.consumer.commit(message)
                return
            # Route to appropriate handler
            if event_type == "data_collection":
                await self._handle_data_collection_job(payload, shop_data)
            elif event_type in [
                "product_updated",
                "product_created",
                "product_deleted",
                "collection_updated",
                "collection_created",
                "collection_deleted",
                "order_paid",
                "order_updated",
                "refund_created",
                "customer_created",
                "customer_updated",
                "inventory_updated",
            ]:
                await self._handle_webhook_event(payload, shop_data)
            else:
                logger.warning(f"❌ Unknown event type: {event_type}")

        except Exception as e:
            logger.exception(f"Failed to process data collection message: {e}")
            raise

    async def _resolve_shop_data(self, event: Dict[str, Any]) -> Dict[str, Any] | None:
        """Resolve shop data for any event type"""
        event_type = event.get("event_type")

        # For data collection jobs, use shop_id
        if event_type == "data_collection":
            shop_id = event.get("shop_id")
            if not shop_id:
                logger.error("❌ No shop_id for data collection job")
                return None

            shop_record = await self.shop_repo.get_active_by_id(shop_id)
            if not shop_record or not shop_record.access_token:
                logger.error(f"❌ Shop not found for shop_id: {shop_id}")
                return None

            return {
                "id": shop_record.id,
                "domain": shop_record.shop_domain,
                "access_token": shop_record.access_token,
                "is_active": shop_record.is_active,
            }

        # For webhook events, use shop_domain
        else:
            shop_domain = event.get("shop_domain")
            if not shop_domain:
                logger.error("❌ No shop_domain for webhook event")
                return None

            shop_cache = await get_shop_cache_service()
            shop_data = await shop_cache.get_active_shop_by_domain(shop_domain)
            if not shop_data:
                logger.error(f"❌ Shop not found for domain: {shop_domain}")
                return None

            return shop_data

    async def _handle_data_collection_job(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ):
        """Handle data collection jobs from analysis triggers"""
        job_id = event.get("job_id")
        collection_payload = event.get("collection_payload", {})

        if not job_id:
            logger.error("❌ Missing job_id for data collection job")
            return

        await self._process_data_collection_job(
            job_id, shop_data["id"], collection_payload, shop_data
        )

    async def _handle_webhook_event(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ):
        """Handle webhook events and convert to data collection jobs"""
        try:
            event_type = event.get("event_type")
            shopify_id = event.get("shopify_id")

            # ✅ ADD LOGGING FOR ORDER_UPDATED EVENTS
            logger.info(
                f"🔄 Processing {event_type} webhook for {shopify_id} in shop {shop_data['id']}"
            )

            if not shopify_id:
                logger.error(f"❌ No shopify_id in webhook event: {event_type}")
                return

            # Check if this is a deletion event
            if event_type.endswith("_deleted"):
                await self._handle_deletion_event(
                    event_type, shopify_id, shop_data["id"]
                )
                return

            # Create collection payload based on event type
            collection_payload = self._create_collection_payload(event_type, shopify_id)
            if collection_payload:
                # Mark the delivery mechanism. This is the only point in the
                # chain that knows a webhook caused this fetch; without it the
                # resulting raw row is indistinguishable from a backfill and
                # the order is never attributed.
                collection_payload["trigger"] = "webhook"
            if not collection_payload:
                logger.warning(f"❌ No collection payload for event type: {event_type}")
                return

            # Create data collection job
            job_id = f"webhook_{event_type}_{shopify_id}_{event.get('timestamp', '')}"

            # Process as data collection job with resolved shop data
            await self._process_data_collection_job(
                job_id, shop_data["id"], collection_payload, shop_data
            )

        except Exception as e:
            logger.exception(f"Failed to handle webhook event: {e}")
            raise

    def _create_collection_payload(
        self, event_type: str, shopify_id: str
    ) -> Dict[str, Any]:
        """Create collection payload based on event type"""
        event_mapping = {
            # Product events
            "product_created": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            "product_updated": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            "product_deleted": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            # Collection events
            "collection_created": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            "collection_updated": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            "collection_deleted": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            # Order events
            "order_paid": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            "order_updated": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            "refund_created": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            # Customer events
            "customer_created": {
                "data_types": ["customers"],
                "specific_ids": {"customers": [shopify_id]},
            },
            "customer_updated": {
                "data_types": ["customers"],
                "specific_ids": {"customers": [shopify_id]},
            },
            "inventory_updated": {
                "data_types": ["products"],
                "specific_ids": {"inventory_items": [shopify_id]},
                "include_inventory": True,
            },
        }
        return event_mapping.get(event_type)

    async def _process_data_collection_job(
        self,
        job_id: str,
        shop_id: str,
        collection_payload: Dict[str, Any] = None,
        shop_data: Dict[str, Any] = None,
    ):
        """Process data collection job with retry and DLQ fallback"""
        if not shop_data or not shop_data.get("access_token"):
            logger.error("❌ Shop not found or inactive. Aborting data collection")
            return False

        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                result = await self.shopify_service.collect_all_data(
                    shop_domain=shop_data["domain"],
                    shop_id=shop_data["id"],
                    access_token=shop_data["access_token"],
                    collection_payload=collection_payload,
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    delay = 5 * (3 ** attempt)  # 5s, 15s
                    logger.warning(
                        f"⚠️ Data collection attempt {attempt + 1}/{max_attempts} failed for {shop_id}, "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted — send to DLQ
        logger.error(
            f"❌ Data collection failed after {max_attempts} attempts for {shop_id}: {last_error}"
        )
        await self.dlq_service.send_to_dlq(
            original_message={
                "event_type": "data_collection",
                "job_id": job_id,
                "shop_id": shop_id,
                "collection_payload": collection_payload,
            },
            reason="data_collection_failed",
            original_topic="data-collection-jobs",
            error_details=str(last_error),
            retry_count=max_attempts,
        )

    async def _handle_deletion_event(
        self, event_type: str, shopify_id: str, shop_id: str
    ):
        """Handle deletion events by marking entities as inactive"""
        try:
            # Determine data type from event type
            if event_type == "product_deleted":
                data_type = "products"
            elif event_type == "collection_deleted":
                data_type = "collections"
            elif event_type == "customer_deleted":
                data_type = "customers"
            elif event_type == "order_deleted":
                data_type = "orders"
            else:
                logger.warning(f"❌ Unknown deletion event type: {event_type}")
                return

            # Use the normalization service to handle deletion
            from app.domains.shopify.services.normalisation_service import (
                NormalizationService,
            )

            normalization_service = NormalizationService()

            # Create deletion job
            deletion_job = {
                "event_type": event_type,
                "data_type": data_type,
                "shop_id": shop_id,
                "shopify_id": shopify_id,
            }

            # Handle the deletion using the existing deletion service
            await normalization_service.deletion_service.handle_entity_deletion(
                deletion_job, None  # db parameter not needed for SQLAlchemy
            )

        except Exception as e:
            logger.exception(f"❌ Failed to handle deletion event: {e}")
            raise
