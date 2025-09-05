"""
Behavioral Events Consumer for processing Shopify Web Pixel events
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from app.consumers.base_consumer import BaseConsumer
from app.core.config.settings import settings
from app.core.logging import get_logger
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository

logger = get_logger(__name__)


class BehavioralEventsConsumer(BaseConsumer):
    """Consumer for processing behavioral events from Shopify Web Pixels"""

    def __init__(self):
        super().__init__(
            stream_name=settings.BEHAVIORAL_EVENTS_STREAM,
            consumer_group="behavioral-events-processors",
            consumer_name=f"behavioral-events-consumer-{settings.WORKER_ID}",
        )

        # Initialize webhook services
        self.repository = WebhookRepository()
        self.handler = WebhookHandler(self.repository)

        # Job tracking
        self.active_events = {}

        # Consumer settings
        self.batch_size = 10  # Process up to 10 events at once
        self.poll_timeout = 1000  # 1 second poll timeout
        self.job_timeout = 300  # 5 minutes for event processing

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single behavioral event message"""
        try:
            # Extract message data - Redis streams return data directly
            message_data = message  # No need to get "data" field
            event_id = message_data.get("event_id")
            shop_id = message_data.get("shop_id")
            payload = message_data.get("payload")
            received_at = message_data.get("received_at")

            if not all([event_id, shop_id, payload]):
                self.logger.error(
                    "Invalid message: missing event_id, shop_id, or payload"
                )
                return

            self.logger.info(
                f"Processing behavioral event",
                event_id=event_id,
                shop_id=shop_id,
                received_at=received_at,
            )

            # Track the event
            self.active_events[event_id] = {
                "shop_id": shop_id,
                "started_at": datetime.utcnow(),
                "status": "processing",
                "received_at": received_at,
            }

            # Parse payload if it's a string
            if isinstance(payload, str):
                payload = json.loads(payload)

            # Process the behavioral event
            result = await self.handler.process_behavioral_event(shop_id, payload)

            # Mark event as completed
            if event_id in self.active_events:
                self.active_events[event_id]["status"] = "completed"
                self.active_events[event_id]["completed_at"] = datetime.utcnow()
                self.active_events[event_id]["result"] = result

            self.logger.info(
                f"Behavioral event processed successfully",
                event_id=event_id,
                shop_id=shop_id,
                result=result.get("status"),
            )

        except Exception as e:
            self.logger.error(
                f"Failed to process behavioral event",
                event_id=message.get("event_id"),
                error=str(e),
            )
            raise

    async def get_active_events(self) -> Dict[str, Any]:
        """Get currently active events being processed"""
        return self.active_events.copy()

    async def get_event_status(self, event_id: str) -> Dict[str, Any]:
        """Get status of a specific event"""
        return self.active_events.get(event_id, {})
