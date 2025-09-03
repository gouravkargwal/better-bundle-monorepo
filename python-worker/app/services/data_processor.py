"""
Data processing service that orchestrates data collection and ML training events
"""

import asyncio
import time
from typing import Dict, Any

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.services.data_collection import DataCollectionService
from app.services.gorse_service import gorse_service
from app.core.logger import get_logger

logger = get_logger("data-processor")


class DataProcessor:
    """Main data processor that handles the complete data processing workflow"""

    def __init__(self):
        self.data_collection_service = DataCollectionService()
        self.streams_manager = streams_manager
        self._shutdown_event = asyncio.Event()
        self._consumer_task = None

    async def initialize(self):
        """Initialize the data processor"""

        await self.data_collection_service.initialize()
        await self.streams_manager.initialize()

    async def shutdown(self):
        """Gracefully shutdown the data processor"""

        self._shutdown_event.set()

        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()

    async def start_consumer(self):
        """Start the consumer in a separate task"""
        if self._consumer_task and not self._consumer_task.done():
            logger.warning("Consumer is already running")
            return

        self._consumer_task = asyncio.create_task(
            self.consume_data_jobs(), name="data-processor-consumer"
        )

    async def stop_consumer(self):
        """Stop the consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def _update_job_status(
        self, job_id: str, status: str, progress: int, error: str = None
    ) -> None:
        """Update job status in database"""
        try:
            from app.core.database import get_database

            db = await get_database()

            from datetime import datetime

            update_data = {
                "status": status,
                "progress": progress,
                "updatedAt": datetime.now(),
            }

            if error:
                update_data["error"] = error

            await db.analysisjob.update(where={"jobId": job_id}, data=update_data)

        except Exception as e:
            logger.error(f"Failed to update job status: {e}", job_id=job_id)
            # Don't raise - status update failures shouldn't stop the main process

    async def consume_data_jobs(self):
        """
        Consumer loop for processing data jobs from Redis Streams
        """
        consumer_name = f"{settings.WORKER_ID}-main"
        consecutive_failures = 0
        # Circuit breaker configuration - less aggressive for better recovery
        max_consecutive_failures = 10  # Increased from 3 to 10 for better resilience

        # Resource optimization: Use configurable sleep intervals
        idle_sleep_interval = settings.CONSUMER_IDLE_SLEEP_SECONDS
        error_sleep_interval = settings.CONSUMER_ERROR_SLEEP_SECONDS

        # Circuit breaker state
        circuit_breaker_open = False
        circuit_breaker_open_time = 0
        circuit_breaker_timeout = 600  # 10 minutes (increased from 5 minutes)

        # Initialize services before starting the consumer loop
        await self.initialize()

        loop_iteration = 0

        while not self.is_shutdown_requested():
            loop_iteration += 1
            loop_start_time = time.time()

            try:
                # Check circuit breaker
                if circuit_breaker_open:
                    current_time = time.time()
                    if (
                        current_time - circuit_breaker_open_time
                        > circuit_breaker_timeout
                    ):
                        circuit_breaker_open = False
                        consecutive_failures = 0
                    else:
                        remaining_time = circuit_breaker_timeout - (
                            current_time - circuit_breaker_open_time
                        )
                        # Check shutdown every 5 seconds instead of 30
                        for i in range(6):  # 6 * 5 = 30 seconds
                            if self.is_shutdown_requested():
                                return
                            await asyncio.sleep(5)
                        continue

                # Check shutdown before consuming
                if self.is_shutdown_requested():
                    return

                # SIMPLE FIX: Always sleep between iterations to prevent resource exhaustion
                await asyncio.sleep(idle_sleep_interval)  # Sleep when idle

                # Consume events with resource-optimized settings
                events = await self.streams_manager.consume_events(
                    stream_name=settings.DATA_JOB_STREAM,
                    consumer_group=settings.DATA_PROCESSOR_GROUP,
                    consumer_name=consumer_name,
                    count=settings.CONSUMER_BATCH_SIZE,  # Configurable batch size
                    block=settings.CONSUMER_POLLING_INTERVAL_MS,  # Configurable polling interval
                )

                # Reset failure counter on successful consumption
                if events:
                    consecutive_failures = 0

                    for event in events:
                        # Check shutdown before processing each event
                        if self.is_shutdown_requested():
                            return

                        try:

                            # Process the event
                            await self._process_single_event(event)

                        except Exception as e:
                            logger.error(
                                f"Consumer event: event_processing_error | event_id={event.get('_message_id')} | error={str(e)} | error_type={type(e).__name__}"
                            )
                            # Acknowledge failed events to prevent infinite retries
                            await self._acknowledge_event_safely(event)

                else:
                    consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                error_duration_ms = (time.time() - loop_start_time) * 1000

                # Check if it's a Redis timeout error
                is_redis_timeout = "Timeout" in str(e) or "timeout" in str(e).lower()
                
                logger.error(
                    f"Consumer event: consumer_error | iteration={loop_iteration} | consecutive_failures={consecutive_failures} | error={str(e)} | error_type={type(e).__name__} | duration_ms={error_duration_ms:.2f} | is_redis_timeout={is_redis_timeout}"
                )

                # Implement exponential backoff with circuit breaker
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        f"Consumer event: circuit_breaker_triggered | consecutive_failures={consecutive_failures} | max_failures={max_consecutive_failures}"
                    )

                    # Open circuit breaker
                    circuit_breaker_open = True
                    circuit_breaker_open_time = time.time()

                    # Wait longer when circuit breaker is triggered
                    wait_time = min(60, 2 ** consecutive_failures)  # Cap at 60 seconds
                    logger.warning(
                        f"Consumer event: circuit_breaker_wait | wait_time_seconds={wait_time}"
                    )
                    
                    # Check shutdown every 5 seconds during circuit breaker wait
                    for i in range(wait_time // 5):
                        if self.is_shutdown_requested():
                            return
                        await asyncio.sleep(5)
                else:
                    # Implement exponential backoff for non-circuit breaker failures
                    wait_time = min(30, 2 ** consecutive_failures)  # Cap at 30 seconds
                    logger.info(
                        f"Consumer event: waiting_before_retry | wait_seconds={wait_time}"
                    )
                    
                    # Check shutdown every 5 seconds during backoff wait
                    for i in range(wait_time // 5):
                        if self.is_shutdown_requested():
                            return
                        await asyncio.sleep(5)

    async def _process_single_event(self, event: dict):
        """Process a single event with proper error handling"""
        try:
            # Extract job details
            job_id = event.get("job_id") or event.get("jobId")
            shop_id = event.get("shop_id") or event.get("shopId")
            shop_domain = event.get("shop_domain") or event.get("shopDomain")
            access_token = event.get("access_token") or event.get("accessToken")
            job_type = event.get("job_type") or event.get("jobType", "complete")
            days_back_raw = event.get("days_back") or event.get("daysBack")
            days_back = int(days_back_raw) if days_back_raw is not None else None

            # Validate required fields
            if not all([job_id, shop_id, shop_domain, access_token]):
                raise ValueError(f"Missing required fields in event: {event}")

            # Process with timeout using the new modular data collection method
            async with asyncio.timeout(300):  # 5 minute timeout
                result = await self.process_data_collection_job(
                    {
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "shop_domain": shop_domain,
                        "access_token": access_token,
                        "job_type": job_type,
                        "days_back": days_back,
                    }
                )

            # Acknowledge successful processing
            await self.streams_manager.acknowledge_event(
                stream_name=settings.DATA_JOB_STREAM,
                consumer_group=settings.DATA_PROCESSOR_GROUP,
                message_id=event["_message_id"],
            )

          

        except asyncio.TimeoutError:
            logger.error(f"Job processing timed out: {event.get('job_id', 'unknown')}")
            await self._acknowledge_event_safely(event)
        except Exception as e:
            logger.error(f"Error processing job: {e}")
            await self._acknowledge_event_safely(event)

    async def _acknowledge_event_safely(self, event: dict):
        """Safely acknowledge an event even if it failed"""
        try:
            await self.streams_manager.acknowledge_event(
                stream_name=settings.DATA_JOB_STREAM,
                consumer_group=settings.DATA_PROCESSOR_GROUP,
                message_id=event["_message_id"],
            )
        except Exception as e:
            logger.error(f"Failed to acknowledge event: {e}")

    async def process_data_collection_job(
        self, job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a data collection job using separate, idempotent collection methods"""
        job_id = job_data.get("job_id")
        shop_id = job_data.get("shop_id")

        if not shop_id:
            logger.error("Missing shop_id in job data", job_data=job_data)
            return {"success": False, "error": "Missing shop_id"}

        try:
            # Collect each data type independently
            results = {}

            # 1. Collect Products (most likely to succeed)
            logger.info(
                f"Job processing: products_collection_start | job_id={job_id} | shop_id={shop_id}"
            )

            # Create shop config from job data
            from app.services.data_collection import DataCollectionConfig

            shop_config = DataCollectionConfig(
                shop_id=shop_id,
                shop_domain=job_data.get("shop_domain") or job_data.get("shopDomain"),
                access_token=job_data.get("access_token")
                or job_data.get("accessToken"),
                days_back=job_data.get("days_back") or job_data.get("daysBack"),
            )

            products_result = await self.data_collection_service.collect_products_only(
                shop_id, shop_config
            )
            results["products"] = products_result

            if products_result["success"]:
                logger.info(
                    f"Job processing: products_collection_completed | job_id={job_id} | shop_id={shop_id} | products_count={products_result.get('products_count', 0)}"
                )
            else:
                logger.error(
                    f"Job processing: products_collection_failed | job_id={job_id} | shop_id={shop_id} | error={products_result.get('message', 'Unknown error')}"
                )

            # 2. Try to collect Orders (may fail due to permissions)
            logger.info(
                f"Job processing: orders_collection_start | job_id={job_id} | shop_id={shop_id}"
            )
            try:
                orders_result = await self.data_collection_service.collect_orders_only(
                    shop_id, shop_config
                )
                results["orders"] = orders_result

                if orders_result["success"]:
                    logger.info(
                        f"Job processing: orders_collection_completed | job_id={job_id} | shop_id={shop_id} | orders_count={orders_result.get('orders_count', 0)}"
                    )
                else:
                    logger.error(
                        f"Job processing: orders_collection_failed | job_id={job_id} | shop_id={shop_id} | error={orders_result.get('message', 'Unknown error')}"
                    )
            except Exception as e:
                orders_result = {"success": False, "message": str(e), "orders_count": 0}
                results["orders"] = orders_result
                logger.error(
                    f"Job processing: orders_collection_failed | job_id={job_id} | error={str(e)}"
                )

            # 3. Try to collect Customers (may fail due to permissions)
            logger.info(
                f"Job processing: customers_collection_start | job_id={job_id} | shop_id={shop_id}"
            )
            try:
                customers_result = (
                    await self.data_collection_service.collect_customers_only(
                        shop_id, shop_config
                    )
                )
                results["customers"] = customers_result

                if customers_result["success"]:
                    logger.info(
                        f"Job processing: customers_collection_completed | job_id={job_id} | shop_id={shop_id} | customers_count={customers_result.get('customers_count', 0)}"
                    )
                else:
                    logger.error(
                        f"Job processing: customers_collection_failed | job_id={job_id} | shop_id={shop_id} | error={customers_result.get('message', 'Unknown error')}"
                    )
            except Exception as e:
                customers_result = {
                    "success": False,
                    "message": str(e),
                    "customers_count": 0,
                }
                results["customers"] = customers_result
                logger.error(
                    f"Job processing: customers_collection_failed | job_id={job_id} | error={str(e)}"
                )

            # 4. Determine overall success and send notification
            overall_success = any(
                [
                    products_result.get("success", False),
                    orders_result.get("success", False),
                    customers_result.get("success", False),
                ]
            )

            if overall_success:
                # Send success notification
                await self._send_data_collection_notification(
                    shop_id, results, overall_success=True
                )

                logger.info(
                    f"Job processing: data_collection_completed | job_id={job_id} | shop_id={shop_id} | results={results} | overall_success=True"
                )

                return {
                    "success": True,
                    "message": "Data collection completed with partial success",
                    "results": results,
                    "overall_success": True,
                }
            else:
                # All collections failed
                await self._send_data_collection_notification(
                    shop_id, results, overall_success=False
                )

                logger.error(
                    f"Job processing: data_collection_failed | job_id={job_id} | shop_id={shop_id} | results={results} | overall_success=False"
                )

                return {
                    "success": False,
                    "message": "All data collections failed",
                    "results": results,
                    "overall_success": False,
                }

        except Exception as e:
            logger.error(
                f"Data collection job failed: {e}", job_id=job_id, shop_id=shop_id
            )
            return {"success": False, "error": str(e)}

    async def _send_data_collection_notification(
        self, shop_id: str, results: Dict[str, Any], overall_success: bool
    ):
        """Send notification about data collection results and trigger features computation"""
        try:
            from app.core.redis_client import streams_manager

            # Calculate totals
            total_products = results.get("products", {}).get("products_count", 0)
            total_orders = results.get("orders", {}).get("orders_count", 0)
            total_customers = results.get("customers", {}).get("customers_count", 0)

            if overall_success:
                if total_products > 0 and total_orders > 0 and total_customers > 0:
                    message = f"✅ Complete data collection successful! Collected {total_products} products, {total_orders} orders, and {total_customers} customers."
                    notification_type = "data_collection_completed"
                elif total_products > 0:
                    message = f"✅ Products data collected successfully! Collected {total_products} products. Orders and customers data not available due to app permissions."
                    notification_type = "data_collection_partial_success"
                else:
                    message = "⚠️ Data collection completed with limited success. Some data types failed due to app permissions."
                    notification_type = "data_collection_partial_success"
            else:
                message = "❌ Data collection failed for all data types. Please check app permissions and try again."
                notification_type = "data_collection_failed"

            # Send user notification
            await streams_manager.publish_user_notification_event(
                shop_id=shop_id,
                notification_type=notification_type,
                message=message,
                data={
                    "products_count": total_products,
                    "orders_count": total_orders,
                    "customers_count": total_customers,
                    "results": results,
                    "overall_success": overall_success,
                },
            )

            # If data collection was successful, trigger features computation
            if overall_success:
                await self._trigger_features_computation(shop_id, results)

        except Exception as e:
            logger.error(
                f"Failed to send data collection notification: {e}", shop_id=shop_id
            )

    async def _trigger_features_computation(
        self, shop_id: str, results: Dict[str, Any]
    ):
        """Trigger features computation after successful data collection"""
        try:
            from app.core.redis_client import streams_manager

            # Publish features computation event
            event_data = {
                "event_type": "DATA_COLLECTION_COMPLETED",
                "shop_id": shop_id,
                "data_collection_results": results,
                "timestamp": time.time(),
            }

            await streams_manager.publish_event(
                stream_name=settings.FEATURES_COMPUTED_STREAM,
                event_data=event_data,
            )

            logger.info(
                "Features computation event published",
                shop_id=shop_id,
                stream=settings.FEATURES_COMPUTED_STREAM,
            )

        except Exception as e:
            logger.error(
                f"Failed to trigger features computation: {e}", shop_id=shop_id
            )


# Global data processor instance
data_processor = DataProcessor()
