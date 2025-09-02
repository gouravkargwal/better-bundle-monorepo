"""
Heuristic Decision Consumer Service
Consumes heuristic decision events and makes intelligent decisions about next analysis timing
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.core.database import get_database
from app.services.heuristic_service import heuristic_service
from app.core.logger import get_logger

logger = get_logger("heuristic-decision-consumer")


class HeuristicDecisionConsumer:
    """Consumer for heuristic decision events"""

    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._consumer_task = None

    async def initialize(self):
        """Initialize the consumer"""
        logger.info("Initializing heuristic decision consumer")
        await streams_manager.initialize()
        await heuristic_service.initialize()
        logger.info("Heuristic decision consumer initialized")

    async def start_consumer(self):
        """Start the consumer in a separate task"""
        if self._consumer_task and not self._consumer_task.done():
            logger.warning("Heuristic decision consumer is already running")
            return

        self._consumer_task = asyncio.create_task(
            self.consume_heuristic_decision_events(), name="heuristic-decision-consumer"
        )
        logger.info("Heuristic decision consumer started")

    async def stop_consumer(self):
        """Stop the consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            logger.info("Heuristic decision consumer stopped")

    async def consume_heuristic_decision_events(self):
        """Main consumer loop for heuristic decision events"""
        consumer_name = (
            f"heuristic-decision-consumer-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        consecutive_failures = 0
        max_consecutive_failures = 3

        logger.info(f"Starting heuristic decision consumer: {consumer_name}")

        while not self._shutdown_event.is_set():
            try:
                # Consume events from heuristic decision requested stream
                events = await streams_manager.consume_events(
                    stream_name=settings.HEURISTIC_DECISION_REQUESTED_STREAM,
                    consumer_group="heuristic-decision-processors",
                    consumer_name=consumer_name,
                    count=1,
                    block=5000,  # 5 seconds
                )

                if events:
                    for event in events:
                        try:
                            logger.info(
                                "Processing heuristic decision event",
                                message_id=event.get("_message_id"),
                                job_id=event.get("job_id"),
                                shop_id=event.get("shop_id"),
                            )

                            # Process the heuristic decision
                            await self._process_heuristic_decision(event)

                            # Acknowledge successful processing
                            await streams_manager.acknowledge_event(
                                stream_name=settings.HEURISTIC_DECISION_REQUESTED_STREAM,
                                consumer_group="heuristic-decision-processors",
                                message_id=event["_message_id"],
                            )

                            consecutive_failures = 0  # Reset failure counter

                        except Exception as e:
                            logger.error(
                                "Error processing heuristic decision event",
                                message_id=event.get("_message_id"),
                                error=str(e),
                            )
                            consecutive_failures += 1

                            # Acknowledge even failed events to avoid infinite retries
                            await streams_manager.acknowledge_event(
                                stream_name=settings.HEURISTIC_DECISION_REQUESTED_STREAM,
                                consumer_group="heuristic-decision-processors",
                                message_id=event["_message_id"],
                            )

                else:
                    # No events, sleep briefly
                    await asyncio.sleep(2)

                # Check for too many consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Too many consecutive failures ({consecutive_failures}), "
                        "waiting before retrying"
                    )
                    await asyncio.sleep(30)
                    consecutive_failures = 0

            except Exception as e:
                logger.error(f"Error in heuristic decision consumer loop: {e}")
                consecutive_failures += 1
                await asyncio.sleep(5)

        logger.info("Heuristic decision consumer loop ended")

    async def _process_heuristic_decision(self, event: Dict[str, Any]):
        """Process a single heuristic decision event"""
        try:
            job_id = event.get("job_id")
            shop_id = event.get("shop_id")
            shop_domain = event.get("shop_domain")
            training_result = event.get("training_result")

            logger.info(
                "🧠 Making heuristic decision for next analysis",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
            )

            # Make heuristic decision about next analysis timing
            heuristic_result = await heuristic_service.calculate_next_analysis_time(
                shop_id, training_result
            )

            if heuristic_result:
                logger.info(
                    "✅ Heuristic decision calculated successfully",
                    job_id=job_id,
                    shop_id=shop_id,
                    next_analysis_hours=heuristic_result.next_analysis_hours,
                    confidence=heuristic_result.confidence,
                    reasoning=heuristic_result.reasoning,
                )

                # Publish heuristic decision made event
                await self._publish_heuristic_decision_made(
                    job_id, shop_id, shop_domain, heuristic_result
                )

            else:
                logger.error(
                    "❌ Failed to calculate heuristic decision",
                    job_id=job_id,
                    shop_id=shop_id,
                )

        except Exception as e:
            logger.error(f"Error processing heuristic decision: {e}")
            raise

    async def _publish_heuristic_decision_made(
        self, job_id: str, shop_id: str, shop_domain: str, heuristic_result: Any
    ):
        """Publish heuristic decision made event"""
        try:
            heuristic_event = {
                "event_type": "HEURISTIC_DECISION_MADE",
                "job_id": job_id,
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "decision": {
                    "next_analysis_hours": heuristic_result.next_analysis_hours,
                    "confidence": heuristic_result.confidence,
                    "reasoning": heuristic_result.reasoning,
                    "factors": heuristic_result.factors.__dict__ if hasattr(heuristic_result, 'factors') else {},
                },
                "decision_made_at": datetime.now().isoformat(),
            }

            message_id = await streams_manager.publish_event(
                settings.HEURISTIC_DECISION_MADE_STREAM, heuristic_event
            )

            logger.info(
                "🧠 Heuristic decision made event published",
                message_id=message_id,
                job_id=job_id,
                shop_id=shop_id,
            )

        except Exception as e:
            logger.error("Error publishing heuristic decision made event", error=str(e))

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()

    async def shutdown(self):
        """Gracefully shutdown the consumer"""
        logger.info("Shutting down heuristic decision consumer")
        self._shutdown_event.set()

        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        logger.info("Heuristic decision consumer shutdown complete")


# Global instance
heuristic_decision_consumer = HeuristicDecisionConsumer()
