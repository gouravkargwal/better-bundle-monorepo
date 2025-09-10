import uuid
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from pydantic import ValidationError, TypeAdapter
from .repository import WebhookRepository
from .models import ShopifyBehavioralEvent
from .distributed_rate_limiter import DistributedRateLimiter, RateLimitConfig
from .distributed_batch_manager import DistributedBatchManager, BatchConfig
from .shopify_webhook_verifier import ShopifyWebhookVerifier
from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class WebhookHandler:
    """
    Enhanced WebhookHandler with batch processing, incremental logic, and rate limiting.

    Features:
    1. Batch Processing: Groups events for efficient processing
    2. Incremental Logic: Only processes new/unprocessed events
    3. Rate Limiting: Protects against API abuse
    4. Connection Pooling: Efficient database usage
    5. Monitoring: Performance tracking and metrics
    """

    def __init__(
        self,
        repository: WebhookRepository,
        rate_limit_config: RateLimitConfig = None,
        batch_config: BatchConfig = None,
    ):
        self.repository = repository
        # Initialize a TypeAdapter once to validate the union type efficiently.
        self.event_adapter = TypeAdapter(ShopifyBehavioralEvent)

        # Initialize distributed components
        self.rate_limiter = DistributedRateLimiter(rate_limit_config)
        self.batch_manager = DistributedBatchManager(batch_config)
        self.webhook_verifier = ShopifyWebhookVerifier()

        # Register batch processor for each shop
        self._registered_shops: Set[str] = set()

        # Graceful shutdown
        self._shutdown_event = asyncio.Event()
        self._background_tasks: List[asyncio.Task] = []

        # Metrics tracking
        self._metrics = {
            "events_processed": 0,
            "events_queued": 0,
            "rate_limited_requests": 0,
            "verification_failures": 0,
            "processing_errors": 0,
            "last_reset": now_utc(),
        }

    async def _resolve_shop_id(self, shop_domain: str) -> str:
        """Resolve shop domain to database ID"""
        try:
            db = await get_database()
            shop = await db.shop.find_unique(where={"shopDomain": shop_domain})

            if not shop:
                logger.error(f"Shop not found for domain: {shop_domain}")
                raise ValueError(f"Shop not found for domain: {shop_domain}")

            return shop.id
        except Exception as e:
            logger.error(f"Failed to resolve shop ID for domain {shop_domain}: {e}")
            raise

    async def _ensure_shop_registered(self, shop_id: str):
        """Ensure shop is registered with batch manager"""
        if shop_id not in self._registered_shops:
            # Register batch processor for this shop
            self.batch_manager.register_batch_processor(
                shop_id, self._process_shop_batch
            )
            self._registered_shops.add(shop_id)
            logger.info(f"Registered batch processor for shop {shop_id}")

    async def _process_shop_batch(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a batch of events for a shop"""
        if not events:
            return {"status": "success", "processed": 0, "errors": 0}

        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get shop domain for processing
            db = await get_database()
            shop_id = events[0].get("shopId")
            if not shop_id:
                return {"status": "error", "message": "No shop ID in events"}

            shop = await db.shop.find_unique(where={"id": shop_id})
            if not shop:
                return {"status": "error", "message": f"Shop not found: {shop_id}"}

            shop_domain = shop.shopDomain

            # Process events in smaller sub-batches
            sub_batch_size = 20
            for i in range(0, len(events), sub_batch_size):
                sub_batch = events[i : i + sub_batch_size]

                # Process sub-batch concurrently
                tasks = [
                    self.process_behavioral_event(shop_domain, event)
                    for event in sub_batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        error_count += 1
                        errors.append(str(result))
                    elif result.get("status") == "success":
                        processed_count += 1
                    else:
                        error_count += 1
                        errors.append(result.get("message", "Unknown error"))

            duration = (now_utc() - start_time).total_seconds()

            # Update metrics
            self._metrics["events_processed"] += processed_count
            if error_count > 0:
                self._metrics["processing_errors"] += error_count

            logger.info(
                f"Batch processing completed: {processed_count} processed, {error_count} errors in {duration:.2f}s"
            )

            return {
                "status": "success",
                "processed": processed_count,
                "errors": error_count,
                "duration_seconds": duration,
                "error_details": errors[:5],  # Limit error details
            }

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            self._metrics["processing_errors"] += 1
            return {"status": "error", "message": str(e)}

    async def queue_behavioral_event(self, shop_domain: str, payload: Dict[str, Any]):
        """Queues a behavioral event for background processing via Redis streams."""
        if not shop_domain:
            logger.warning("Missing shop_domain in request.")
            return {"status": "error", "message": "Missing shop_domain"}

        try:
            # Generate a unique event ID for tracking
            event_id = str(uuid.uuid4())

            # Publish event to Redis stream for background processing
            message_id = await streams_manager.publish_behavioral_event(
                event_id=event_id, shop_id=shop_domain, payload=payload
            )

            logger.info(
                "Behavioral event queued for processing.",
                event_id=event_id,
                shop_domain=shop_domain,
                message_id=message_id,
            )

            return {
                "status": "queued",
                "event_id": event_id,
                "message_id": message_id,
                "message": "Event queued for background processing",
            }

        except Exception as e:
            logger.error("Failed to queue behavioral event.", error=str(e))
            return {"status": "error", "message": "Failed to queue event"}

    async def _handle_customer_linking(
        self, shop_id: str, client_id: str, customer_id: str
    ):
        """Handle customer linking when user logs in"""
        try:
            db = await get_database()

            # Check if link already exists
            existing_link = await db.useridentitylink.find_first(
                where={
                    "shopId": shop_id,
                    "clientId": client_id,
                    "customerId": customer_id,
                }
            )

            if not existing_link:
                # Create new link
                await db.useridentitylink.create(
                    data={
                        "shopId": shop_id,
                        "clientId": client_id,
                        "customerId": customer_id,
                    }
                )

                # Backfill customer_id for existing events
                await self._backfill_customer_id(shop_id, client_id, customer_id)

                logger.info(f"Created customer link: {client_id} → {customer_id}")
            else:
                logger.info(
                    f"Customer link already exists: {client_id} → {customer_id}"
                )

        except Exception as e:
            logger.error(f"Failed to handle customer linking: {e}")

    async def _backfill_customer_id(
        self, shop_id: str, client_id: str, customer_id: str
    ):
        """Backfill customer_id for existing events"""
        try:
            db = await get_database()

            # Update all events with this clientId that don't have a customerId
            # Also update the timestamp so incremental processing picks up the changes
            result = await db.behavioralevents.update_many(
                where={"shopId": shop_id, "clientId": client_id, "customerId": None},
                data={
                    "customerId": customer_id,
                    "timestamp": now_utc(),  # Update timestamp to trigger incremental processing
                },
            )

            logger.info(
                f"Backfilled {result.count} events for {client_id} → {customer_id} (updated timestamps for incremental processing)"
            )

        except Exception as e:
            logger.error(f"Failed to backfill customer_id: {e}")

    async def _check_existing_customer_link(self, shop_id: str, client_id: str) -> str:
        """Check if a clientId already has a linked customerId"""
        try:
            if not client_id:
                return None

            db = await get_database()
            link = await db.useridentitylink.find_first(
                where={"shopId": shop_id, "clientId": client_id}
            )
            return link.customerId if link else None
        except Exception as e:
            logger.error(f"Failed to check existing customer link: {e}")
            return None

    async def process_behavioral_event(self, shop_domain: str, payload: Dict[str, Any]):
        """
        Validates and processes an incoming behavioral event from a Web Pixel.

        This method is intended to be called by a background worker that consumes
        messages from a Redis stream.
        """
        if not shop_domain:
            logger.warning("Missing shop_domain in request.")
            return {"status": "error", "message": "Missing shop_domain"}

        try:
            # Resolve shop domain to database ID
            shop_db_id = await self._resolve_shop_id(shop_domain)

            # Use the pre-initialized TypeAdapter to correctly validate the Union type.
            validated_event = self.event_adapter.validate_python(payload)

            # Handle customer linking events specially
            if validated_event.name == "customer_linked":
                # Check if this is actually a CustomerLinkedEvent with proper data structure
                if (
                    hasattr(validated_event.data, "clientId")
                    and hasattr(validated_event.data, "customerId")
                    and validated_event.data.clientId
                    and validated_event.data.customerId
                ):
                    await self._handle_customer_linking(
                        shop_db_id,
                        validated_event.data.clientId,
                        validated_event.data.customerId,
                    )
                else:
                    logger.warning(
                        f"customer_linked event {validated_event.id} missing required clientId or customerId in data. "
                        f"clientId: {getattr(validated_event.data, 'clientId', 'missing')}, "
                        f"customerId: {getattr(validated_event.data, 'customerId', 'missing')}"
                    )
            else:
                # For regular events, check if clientId already has a linked customerId
                client_id = payload.get("clientId")
                if client_id and not validated_event.customer_id:
                    existing_customer_id = await self._check_existing_customer_link(
                        shop_db_id, client_id
                    )
                    if existing_customer_id:
                        # Update the validated event with the linked customer ID
                        validated_event.customer_id = existing_customer_id
                        logger.info(
                            f"Auto-linked event {validated_event.id} to customer {existing_customer_id}"
                        )

            await self.repository.save_behavioral_event(
                shop_db_id, payload, validated_event
            )

            logger.info(
                "Successfully processed behavioral event.",
                event_id=validated_event.id,
                type=validated_event.name,
                shop_domain=shop_domain,
            )
            return {"status": "success"}

        except ValidationError as e:
            logger.error(
                "Behavioral event validation failed.", error=str(e), payload=payload
            )
            return {"status": "validation_error", "details": str(e)}
        except Exception as e:
            logger.error("Failed to process behavioral event.", error=str(e))
            return {"status": "processing_error"}

    # Enhanced Methods for High-Volume Processing

    async def _check_rate_limit(
        self, shop_id: str, client_id: Optional[str] = None
    ) -> bool:
        """
        Check if request is within rate limits

        Args:
            shop_id: Shop identifier
            client_id: Optional client identifier for per-client rate limiting

        Returns:
            True if within limits, False if rate limited
        """
        now = now_utc()
        window_start = now - timedelta(seconds=self.rate_limit_window)

        # Clean old entries from rate limiters
        self._rate_limiters[shop_id] = deque(
            [t for t in self._rate_limiters[shop_id] if t > window_start]
        )

        if client_id:
            self._client_rate_limiters[client_id] = deque(
                [t for t in self._client_rate_limiters[client_id] if t > window_start]
            )

        # Check shop-level rate limit
        if len(self._rate_limiters[shop_id]) >= self.rate_limit_max_requests:
            logger.warning(
                f"Shop {shop_id} rate limited: {len(self._rate_limiters[shop_id])} requests in window"
            )
            self._metrics["rate_limited_requests"] += 1
            return False

        # Check client-level rate limit
        if (
            client_id
            and len(self._client_rate_limiters[client_id]) >= self.rate_limit_per_client
        ):
            logger.warning(
                f"Client {client_id} rate limited: {len(self._client_rate_limiters[client_id])} requests in window"
            )
            self._metrics["rate_limited_requests"] += 1
            return False

        # Add current request to rate limiters
        self._rate_limiters[shop_id].append(now)
        if client_id:
            self._client_rate_limiters[client_id].append(now)

        return True

    async def _get_unprocessed_events(
        self, shop_id: str, event_ids: List[str]
    ) -> List[str]:
        """
        Get list of event IDs that haven't been processed yet

        Args:
            shop_id: Shop identifier
            event_ids: List of event IDs to check

        Returns:
            List of unprocessed event IDs
        """
        try:
            db = await get_database()

            # Query for existing event IDs
            existing_events = await db.behavioralevents.find_many(
                where={"shopId": shop_id, "eventId": {"in": event_ids}},
                select={"eventId": True},
            )

            existing_ids = {event.eventId for event in existing_events}
            unprocessed_ids = [
                event_id for event_id in event_ids if event_id not in existing_ids
            ]

            logger.info(
                f"Found {len(unprocessed_ids)} unprocessed events out of {len(event_ids)} total"
            )
            return unprocessed_ids

        except Exception as e:
            logger.error(f"Failed to check unprocessed events: {e}")
            # If we can't check, assume all are unprocessed to be safe
            return event_ids

    async def _process_event_batch(
        self, shop_id: str, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process a batch of events efficiently

        Args:
            shop_id: Shop identifier
            events: List of events to process

        Returns:
            Processing result with metrics
        """
        if not events:
            return {"status": "success", "processed": 0, "errors": 0}

        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get shop domain for processing
            db = await get_database()
            shop = await db.shop.find_unique(where={"id": shop_id})
            if not shop:
                return {"status": "error", "message": f"Shop not found: {shop_id}"}

            shop_domain = shop.shopDomain

            # Extract event IDs for incremental processing
            event_ids = [
                event.get("eventId") for event in events if event.get("eventId")
            ]

            # Get only unprocessed events
            unprocessed_ids = await self._get_unprocessed_events(shop_id, event_ids)
            unprocessed_events = [
                event for event in events if event.get("eventId") in unprocessed_ids
            ]

            if not unprocessed_events:
                logger.info(
                    f"All {len(events)} events already processed for shop {shop_id}"
                )
                return {"status": "success", "processed": 0, "skipped": len(events)}

            logger.info(
                f"Processing {len(unprocessed_events)} unprocessed events out of {len(events)} total"
            )

            # Process events in smaller sub-batches to avoid overwhelming the database
            sub_batch_size = 20
            for i in range(0, len(unprocessed_events), sub_batch_size):
                sub_batch = unprocessed_events[i : i + sub_batch_size]

                # Process sub-batch concurrently
                tasks = [
                    self.process_behavioral_event(shop_domain, event)
                    for event in sub_batch
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        error_count += 1
                        errors.append(str(result))
                    elif result.get("status") == "success":
                        processed_count += 1
                    else:
                        error_count += 1
                        errors.append(result.get("message", "Unknown error"))

            duration = (now_utc() - start_time).total_seconds()

            # Update metrics
            self._metrics["events_processed"] += processed_count
            self._metrics["events_batched"] += len(events)
            if error_count > 0:
                self._metrics["processing_errors"] += error_count

            logger.info(
                f"Batch processing completed: {processed_count} processed, {error_count} errors, "
                f"{len(events) - len(unprocessed_events)} skipped in {duration:.2f}s"
            )

            return {
                "status": "success",
                "processed": processed_count,
                "errors": error_count,
                "skipped": len(events) - len(unprocessed_events),
                "duration_seconds": duration,
                "error_details": errors[:5],  # Limit error details
            }

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            self._metrics["processing_errors"] += 1
            return {"status": "error", "message": str(e)}

    async def _schedule_batch_processing(self, shop_id: str):
        """
        Schedule batch processing for a shop after timeout

        Args:
            shop_id: Shop identifier
        """
        if shop_id in self._batch_timers:
            # Cancel existing timer
            self._batch_timers[shop_id].cancel()

        async def process_batch():
            await asyncio.sleep(self.batch_timeout)
            await self._trigger_batch_processing(shop_id)

        self._batch_timers[shop_id] = asyncio.create_task(process_batch())

    async def _trigger_batch_processing(self, shop_id: str):
        """
        Trigger batch processing for a shop

        Args:
            shop_id: Shop identifier
        """
        async with self._processing_locks[shop_id]:
            if shop_id not in self._event_batches or not self._event_batches[shop_id]:
                return

            events = self._event_batches[shop_id].copy()
            self._event_batches[shop_id].clear()

            if shop_id in self._batch_timers:
                self._batch_timers[shop_id].cancel()
                del self._batch_timers[shop_id]

            if events:
                result = await self._process_event_batch(shop_id, events)
                logger.info(f"Batch processing result for shop {shop_id}: {result}")

    async def queue_behavioral_event_batch(
        self, shop_domain: str, payload: Dict[str, Any], force_immediate: bool = False
    ) -> Dict[str, Any]:
        """
        Enhanced queue method with batching and rate limiting

        Args:
            shop_domain: Shop domain
            payload: Event payload
            force_immediate: Force immediate processing (bypass batching)

        Returns:
            Queue result
        """
        if not shop_domain:
            return {"status": "error", "message": "Missing shop_domain"}

        try:
            # Resolve shop ID
            shop_id = await self._resolve_shop_id(shop_domain)

            # Extract client ID for rate limiting
            client_id = payload.get("clientId")

            # Check rate limits
            if not await self._check_rate_limit(shop_id, client_id):
                return {
                    "status": "rate_limited",
                    "message": "Request rate limit exceeded",
                }

            # Generate event ID if not present
            if "eventId" not in payload:
                payload["eventId"] = str(uuid.uuid4())

            # Add timestamp if not present
            if "timestamp" not in payload:
                payload["timestamp"] = now_utc().isoformat()

            if force_immediate:
                # Process immediately (for critical events)
                result = await self._process_event_batch(shop_id, [payload])
                return {
                    "status": "processed",
                    "event_id": payload["eventId"],
                    "result": result,
                }
            else:
                # Add to batch
                async with self._processing_locks[shop_id]:
                    self._event_batches[shop_id].append(payload)

                    # Trigger batch processing if batch is full
                    if len(self._event_batches[shop_id]) >= self.batch_size:
                        await self._trigger_batch_processing(shop_id)
                    else:
                        # Schedule batch processing after timeout
                        await self._schedule_batch_processing(shop_id)

                return {
                    "status": "queued",
                    "event_id": payload["eventId"],
                    "batch_size": len(self._event_batches[shop_id]),
                    "message": "Event queued for batch processing",
                }

        except Exception as e:
            logger.error(f"Failed to queue behavioral event: {e}")
            self._metrics["processing_errors"] += 1
            return {"status": "error", "message": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get processing metrics

        Returns:
            Dictionary of metrics
        """
        now = now_utc()
        uptime = (now - self._metrics["last_reset"]).total_seconds()

        return {
            "events_processed": self._metrics["events_processed"],
            "events_batched": self._metrics["events_batched"],
            "rate_limited_requests": self._metrics["rate_limited_requests"],
            "processing_errors": self._metrics["processing_errors"],
            "uptime_seconds": uptime,
            "events_per_second": self._metrics["events_processed"] / max(uptime, 1),
            "active_batches": len(self._event_batches),
            "active_timers": len(self._batch_timers),
        }

    async def flush_all_batches(self) -> Dict[str, Any]:
        """
        Flush all pending batches immediately

        Returns:
            Flush results
        """
        results = {}

        for shop_id in list(self._event_batches.keys()):
            if self._event_batches[shop_id]:
                await self._trigger_batch_processing(shop_id)
                results[shop_id] = "flushed"

        return results

    # New Distributed Methods

    async def queue_behavioral_event_distributed(
        self,
        shop_domain: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        timestamp: Optional[str] = None,
        ip_address: Optional[str] = None,
        force_immediate: bool = False,
    ) -> Dict[str, Any]:
        """
        Enhanced queue method with distributed architecture, security, and rate limiting

        Args:
            shop_domain: Shop domain
            payload: Event payload
            signature: Optional webhook signature for verification
            timestamp: Optional timestamp for verification
            ip_address: Optional IP address for rate limiting
            force_immediate: Force immediate processing (bypass batching)

        Returns:
            Queue result with comprehensive status
        """
        if not shop_domain:
            return {"status": "error", "message": "Missing shop_domain"}

        try:
            # Resolve shop ID
            shop_id = await self._resolve_shop_id(shop_domain)

            # Ensure shop is registered with batch manager
            await self._ensure_shop_registered(shop_id)

            # Verify webhook signature (if provided)
            if signature:
                verification_result = (
                    await self.webhook_verifier.verify_behavioral_event_signature(
                        shop_domain, payload, signature, timestamp
                    )
                )
                if not verification_result["verified"]:
                    self._metrics["verification_failures"] += 1
                    return {
                        "status": "verification_failed",
                        "message": verification_result["error"],
                        "details": verification_result,
                    }

            # Extract identifiers for rate limiting
            client_id = payload.get("clientId")

            # Check rate limits
            rate_limit_result = await self.rate_limiter.check_rate_limit(
                shop_id, client_id, ip_address
            )

            if not rate_limit_result.allowed:
                self._metrics["rate_limited_requests"] += 1
                return {
                    "status": "rate_limited",
                    "message": rate_limit_result.reason,
                    "retry_after": rate_limit_result.retry_after,
                    "reset_time": rate_limit_result.reset_time.isoformat(),
                }

            # Add shop ID to payload for batch processing
            payload["shopId"] = shop_id

            # Queue event using distributed batch manager
            result = await self.batch_manager.queue_event(
                shop_id, payload, force_immediate
            )

            # Update metrics
            if result["status"] in ["queued", "processed"]:
                self._metrics["events_queued"] += 1

            return {
                **result,
                "rate_limit_remaining": rate_limit_result.remaining,
                "verification_status": "verified" if signature else "skipped",
            }

        except Exception as e:
            logger.error(f"Failed to queue behavioral event: {e}")
            self._metrics["processing_errors"] += 1
            return {"status": "error", "message": str(e)}

    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics from all components

        Returns:
            Dictionary with metrics from all components
        """
        try:
            # Get metrics from all components
            handler_metrics = self._metrics.copy()
            rate_limiter_metrics = await self.rate_limiter.get_rate_limit_status(
                "system"
            )
            batch_manager_metrics = await self.batch_manager.get_metrics()

            # Calculate derived metrics
            now = now_utc()
            uptime = (now - self._metrics["last_reset"]).total_seconds()

            return {
                "handler": {
                    **handler_metrics,
                    "uptime_seconds": uptime,
                    "events_per_second": self._metrics["events_processed"]
                    / max(uptime, 1),
                    "registered_shops": len(self._registered_shops),
                },
                "rate_limiter": rate_limiter_metrics,
                "batch_manager": batch_manager_metrics,
                "system": {
                    "timestamp": now.isoformat(),
                    "active_background_tasks": len(self._background_tasks),
                    "shutdown_requested": self._shutdown_event.is_set(),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get comprehensive metrics: {e}")
            return {"error": str(e), "timestamp": now_utc().isoformat()}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check

        Returns:
            Health status of all components
        """
        try:
            health_status = {
                "status": "healthy",
                "timestamp": now_utc().isoformat(),
                "components": {},
            }

            # Check rate limiter
            try:
                await self.rate_limiter.get_rate_limit_status("health_check")
                health_status["components"]["rate_limiter"] = "healthy"
            except Exception as e:
                health_status["components"]["rate_limiter"] = f"unhealthy: {e}"
                health_status["status"] = "degraded"

            # Check batch manager
            try:
                await self.batch_manager.get_metrics()
                health_status["components"]["batch_manager"] = "healthy"
            except Exception as e:
                health_status["components"]["batch_manager"] = f"unhealthy: {e}"
                health_status["status"] = "degraded"

            # Check webhook verifier
            try:
                await self.webhook_verifier.get_webhook_secret_status("health_check")
                health_status["components"]["webhook_verifier"] = "healthy"
            except Exception as e:
                health_status["components"]["webhook_verifier"] = f"unhealthy: {e}"
                health_status["status"] = "degraded"

            # Check database connection
            try:
                db = await get_database()
                await db.shop.find_first(take=1)
                health_status["components"]["database"] = "healthy"
            except Exception as e:
                health_status["components"]["database"] = f"unhealthy: {e}"
                health_status["status"] = "unhealthy"

            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": now_utc().isoformat(),
            }

    async def graceful_shutdown(self, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Gracefully shutdown the webhook handler and all components

        Args:
            timeout_seconds: Maximum time to wait for shutdown

        Returns:
            Shutdown result
        """
        logger.info("Starting graceful shutdown of webhook handler")

        try:
            # Signal shutdown
            self._shutdown_event.set()

            # Shutdown batch manager
            batch_shutdown_result = await self.batch_manager.graceful_shutdown(
                timeout_seconds
            )

            # Cancel any remaining background tasks
            if self._background_tasks:
                logger.info(f"Canceling {len(self._background_tasks)} background tasks")
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()

            # Wait for tasks to complete
            if self._background_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._background_tasks, return_exceptions=True),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timeout waiting for background tasks during shutdown"
                    )

            logger.info("Webhook handler shutdown completed")

            return {
                "status": "success",
                "batch_manager_shutdown": batch_shutdown_result,
                "background_tasks_canceled": len(self._background_tasks),
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": now_utc().isoformat(),
            }

    async def emergency_flush_all(self) -> Dict[str, Any]:
        """
        Emergency flush all pending batches and reset rate limits

        Returns:
            Flush results
        """
        try:
            # Flush all batches
            batch_flush_result = await self.batch_manager.flush_all_batches()

            # Reset all rate limits (use with caution)
            rate_limit_cleanup = await self.rate_limiter.cleanup_expired_entries()

            return {
                "status": "success",
                "batch_flush": batch_flush_result,
                "rate_limit_cleanup": rate_limit_cleanup,
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Emergency flush failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": now_utc().isoformat(),
            }
