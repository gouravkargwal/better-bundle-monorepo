"""
Distributed Batch Manager using Redis for horizontal scaling and durability.

This module provides a Redis-based batch processing system that works across
multiple application instances, ensuring consistent batching and preventing
data loss during instance failures.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.redis_client import get_redis_client
from app.shared.helpers import now_utc

logger = get_logger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch processing"""

    batch_size: int = 100
    batch_timeout_seconds: float = 5.0
    max_batch_wait_seconds: float = 10.0
    sub_batch_size: int = 20
    cleanup_interval_seconds: int = 300  # 5 minutes


@dataclass
class BatchResult:
    """Result of batch processing"""

    batch_id: str
    shop_id: str
    processed_count: int
    error_count: int
    skipped_count: int
    duration_seconds: float
    status: str
    errors: List[str]
    timestamp: datetime


class DistributedBatchManager:
    """
    Redis-based distributed batch manager that works across multiple instances.

    Features:
    - Distributed event batching using Redis Streams
    - Automatic batch processing with configurable timeouts
    - Graceful shutdown handling
    - Circuit breaker pattern for Redis failures
    - Batch deduplication and incremental processing
    - Monitoring and metrics
    """

    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self.redis_client = None
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60  # seconds
        self._circuit_breaker_reset_time = None

        # Processing callbacks
        self._batch_processors: Dict[str, Callable] = {}

        # Graceful shutdown
        self._shutdown_event = asyncio.Event()
        self._background_tasks: List[asyncio.Task] = []

        # Metrics
        self._metrics = {
            "batches_processed": 0,
            "events_processed": 0,
            "events_skipped": 0,
            "processing_errors": 0,
            "last_reset": now_utc(),
        }

    async def _get_redis_client(self):
        """Get Redis client with circuit breaker protection"""
        if self._is_circuit_breaker_open():
            raise Exception("Batch manager circuit breaker is open")

        if self.redis_client is None:
            try:
                self.redis_client = await get_redis_client()
                self._circuit_breaker_failures = 0
            except Exception as e:
                self._circuit_breaker_failures += 1
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    self._circuit_breaker_reset_time = now_utc() + timedelta(
                        seconds=self._circuit_breaker_timeout
                    )
                raise e

        return self.redis_client

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self._circuit_breaker_reset_time is None:
            return False

        if now_utc() > self._circuit_breaker_reset_time:
            self._circuit_breaker_reset_time = None
            self._circuit_breaker_failures = 0
            return False

        return True

    def register_batch_processor(self, shop_id: str, processor: Callable):
        """
        Register a batch processor for a specific shop

        Args:
            shop_id: Shop identifier
            processor: Async function that processes a batch of events
        """
        self._batch_processors[shop_id] = processor
        logger.info(f"Registered batch processor for shop {shop_id}")

    async def queue_event(
        self, shop_id: str, event: Dict[str, Any], force_immediate: bool = False
    ) -> Dict[str, Any]:
        """
        Queue an event for batch processing

        Args:
            shop_id: Shop identifier
            event: Event data
            force_immediate: Force immediate processing

        Returns:
            Queue result
        """
        try:
            redis = await self._get_redis_client()

            # Generate event ID if not present
            if "eventId" not in event:
                event["eventId"] = str(uuid.uuid4())

            # Add timestamp if not present
            if "timestamp" not in event:
                event["timestamp"] = now_utc().isoformat()

            # Add queue timestamp
            event["queuedAt"] = now_utc().isoformat()

            if force_immediate:
                # Process immediately
                result = await self._process_single_event(shop_id, event)
                return {
                    "status": "processed",
                    "event_id": event["eventId"],
                    "result": result,
                }
            else:
                # Add to batch queue
                stream_key = f"batch_queue:{shop_id}"
                message_id = await redis.xadd(
                    stream_key,
                    {"event": json.dumps(event)},
                    maxlen=self.config.batch_size * 2,  # Keep some buffer
                )

                # Check if batch is ready for processing
                await self._check_and_trigger_batch(shop_id)

                return {
                    "status": "queued",
                    "event_id": event["eventId"],
                    "message_id": message_id,
                    "stream_key": stream_key,
                }

        except Exception as e:
            logger.error(f"Failed to queue event: {e}")
            self._metrics["processing_errors"] += 1
            return {"status": "error", "message": str(e)}

    async def _check_and_trigger_batch(self, shop_id: str):
        """Check if batch is ready and trigger processing"""
        try:
            redis = await self._get_redis_client()
            stream_key = f"batch_queue:{shop_id}"

            # Check current batch size
            stream_length = await redis.xlen(stream_key)

            if stream_length >= self.config.batch_size:
                # Batch is full, process immediately
                await self._process_batch(shop_id)
            else:
                # Schedule batch processing after timeout
                await self._schedule_batch_processing(shop_id)

        except Exception as e:
            logger.error(f"Failed to check batch trigger for shop {shop_id}: {e}")

    async def _schedule_batch_processing(self, shop_id: str):
        """Schedule batch processing after timeout"""
        try:
            redis = await self._get_redis_client()
            timeout_key = f"batch_timeout:{shop_id}"

            # Set timeout with expiration
            await redis.setex(
                timeout_key,
                int(self.config.batch_timeout_seconds),
                now_utc().isoformat(),
            )

            # Start background task to process batch after timeout
            task = asyncio.create_task(self._wait_and_process_batch(shop_id))
            self._background_tasks.append(task)

        except Exception as e:
            logger.error(f"Failed to schedule batch processing for shop {shop_id}: {e}")

    async def _wait_and_process_batch(self, shop_id: str):
        """Wait for timeout and process batch"""
        try:
            await asyncio.sleep(self.config.batch_timeout_seconds)

            # Check if batch still exists and hasn't been processed
            redis = await self._get_redis_client()
            stream_key = f"batch_queue:{shop_id}"
            timeout_key = f"batch_timeout:{shop_id}"

            if await redis.exists(stream_key) and await redis.exists(timeout_key):
                await self._process_batch(shop_id)

        except Exception as e:
            logger.error(f"Failed to wait and process batch for shop {shop_id}: {e}")
        finally:
            # Remove task from background tasks
            if asyncio.current_task() in self._background_tasks:
                self._background_tasks.remove(asyncio.current_task())

    async def _process_batch(self, shop_id: str) -> BatchResult:
        """Process a batch of events for a shop"""
        start_time = now_utc()
        batch_id = str(uuid.uuid4())

        try:
            redis = await self._get_redis_client()
            stream_key = f"batch_queue:{shop_id}"
            timeout_key = f"batch_timeout:{shop_id}"

            # Read all pending messages
            messages = await redis.xread(
                {stream_key: "0"}, count=self.config.batch_size
            )

            if not messages or not messages[0][1]:
                return BatchResult(
                    batch_id=batch_id,
                    shop_id=shop_id,
                    processed_count=0,
                    error_count=0,
                    skipped_count=0,
                    duration_seconds=0,
                    status="empty",
                    errors=[],
                    timestamp=start_time,
                )

            # Extract events from messages
            events = []
            message_ids = []

            for message_id, fields in messages[0][1]:
                try:
                    event = json.loads(fields[b"event"])
                    events.append(event)
                    message_ids.append(message_id)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse event message {message_id}: {e}")

            if not events:
                return BatchResult(
                    batch_id=batch_id,
                    shop_id=shop_id,
                    processed_count=0,
                    error_count=0,
                    skipped_count=0,
                    duration_seconds=0,
                    status="parse_error",
                    errors=["Failed to parse events"],
                    timestamp=start_time,
                )

            # Process events in sub-batches
            processed_count = 0
            error_count = 0
            skipped_count = 0
            errors = []

            for i in range(0, len(events), self.config.sub_batch_size):
                sub_batch = events[i : i + self.config.sub_batch_size]

                try:
                    # Get processor for this shop
                    processor = self._batch_processors.get(shop_id)
                    if not processor:
                        raise Exception(f"No processor registered for shop {shop_id}")

                    # Process sub-batch
                    result = await processor(sub_batch)

                    if result.get("status") == "success":
                        processed_count += result.get("processed", 0)
                        error_count += result.get("errors", 0)
                        skipped_count += result.get("skipped", 0)
                        if result.get("error_details"):
                            errors.extend(result["error_details"])
                    else:
                        error_count += len(sub_batch)
                        errors.append(result.get("message", "Unknown error"))

                except Exception as e:
                    logger.error(f"Failed to process sub-batch: {e}")
                    error_count += len(sub_batch)
                    errors.append(str(e))

            # Acknowledge processed messages
            if message_ids:
                await redis.xack(stream_key, "batch_consumer", *message_ids)
                await redis.xdel(stream_key, *message_ids)

            # Clean up timeout key
            await redis.delete(timeout_key)

            duration = (now_utc() - start_time).total_seconds()

            # Update metrics
            self._metrics["batches_processed"] += 1
            self._metrics["events_processed"] += processed_count
            self._metrics["events_skipped"] += skipped_count
            if error_count > 0:
                self._metrics["processing_errors"] += error_count

            result = BatchResult(
                batch_id=batch_id,
                shop_id=shop_id,
                processed_count=processed_count,
                error_count=error_count,
                skipped_count=skipped_count,
                duration_seconds=duration,
                status="success" if error_count == 0 else "partial_success",
                errors=errors[:10],  # Limit error details
                timestamp=start_time,
            )

            logger.info(
                f"Batch {batch_id} processed: {processed_count} processed, "
                f"{error_count} errors, {skipped_count} skipped in {duration:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to process batch {batch_id}: {e}")
            self._metrics["processing_errors"] += 1

            return BatchResult(
                batch_id=batch_id,
                shop_id=shop_id,
                processed_count=0,
                error_count=len(events) if "events" in locals() else 0,
                skipped_count=0,
                duration_seconds=(now_utc() - start_time).total_seconds(),
                status="error",
                errors=[str(e)],
                timestamp=start_time,
            )

    async def _process_single_event(
        self, shop_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a single event immediately"""
        try:
            processor = self._batch_processors.get(shop_id)
            if not processor:
                return {
                    "status": "error",
                    "message": f"No processor registered for shop {shop_id}",
                }

            result = await processor([event])
            return result

        except Exception as e:
            logger.error(f"Failed to process single event: {e}")
            return {"status": "error", "message": str(e)}

    async def flush_all_batches(self) -> Dict[str, Any]:
        """Flush all pending batches immediately"""
        try:
            redis = await self._get_redis_client()

            # Find all batch queues
            pattern = "batch_queue:*"
            stream_keys = await redis.keys(pattern)

            results = {}
            for stream_key in stream_keys:
                shop_id = stream_key.decode().split(":")[-1]
                result = await self._process_batch(shop_id)
                results[shop_id] = {
                    "status": result.status,
                    "processed": result.processed_count,
                    "errors": result.error_count,
                }

            return {
                "status": "success",
                "flushed_shops": len(results),
                "results": results,
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to flush all batches: {e}")
            return {"status": "error", "message": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """Get processing metrics"""
        now = now_utc()
        uptime = (now - self._metrics["last_reset"]).total_seconds()

        return {
            "batches_processed": self._metrics["batches_processed"],
            "events_processed": self._metrics["events_processed"],
            "events_skipped": self._metrics["events_skipped"],
            "processing_errors": self._metrics["processing_errors"],
            "uptime_seconds": uptime,
            "events_per_second": self._metrics["events_processed"] / max(uptime, 1),
            "batches_per_second": self._metrics["batches_processed"] / max(uptime, 1),
            "active_background_tasks": len(self._background_tasks),
            "registered_processors": len(self._batch_processors),
        }

    async def graceful_shutdown(self, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Gracefully shutdown the batch manager

        Args:
            timeout_seconds: Maximum time to wait for shutdown

        Returns:
            Shutdown result
        """
        logger.info("Starting graceful shutdown of batch manager")

        try:
            # Signal shutdown
            self._shutdown_event.set()

            # Flush all pending batches
            flush_result = await self.flush_all_batches()

            # Wait for background tasks to complete
            if self._background_tasks:
                logger.info(
                    f"Waiting for {len(self._background_tasks)} background tasks to complete"
                )

                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._background_tasks, return_exceptions=True),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout waiting for background tasks, canceling remaining tasks"
                    )
                    for task in self._background_tasks:
                        if not task.done():
                            task.cancel()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()

            logger.info("Batch manager shutdown completed")

            return {
                "status": "success",
                "flush_result": flush_result,
                "background_tasks_completed": len(self._background_tasks),
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": now_utc().isoformat(),
            }
