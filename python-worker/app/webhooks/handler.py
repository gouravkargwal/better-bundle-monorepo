import uuid
from typing import Dict, Any
from pydantic import ValidationError, TypeAdapter
from .repository import WebhookRepository
from .models import ShopifyBehavioralEvent
from app.core.logging import get_logger
from app.core.redis_client import streams_manager

logger = get_logger(__name__)


class WebhookHandler:
    """
    Handles the ingestion and processing of incoming Shopify Web Pixel events.

    This class uses a two-step approach:
    1. A quick-response `queue_behavioral_event` to publish the event to a Redis stream,
       ensuring the API endpoint returns a response immediately.
    2. A `process_behavioral_event` method that is designed to be run by a background
       worker consuming from the Redis stream, where the actual data validation and
       database persistence occurs.
    """

    def __init__(self, repository: WebhookRepository):
        self.repository = repository
        # Initialize a TypeAdapter once to validate the union type efficiently.
        self.event_adapter = TypeAdapter(ShopifyBehavioralEvent)

    async def queue_behavioral_event(self, shop_id: str, payload: Dict[str, Any]):
        """Queues a behavioral event for background processing via Redis streams."""
        if not shop_id:
            logger.warning("Missing shop_id in request.")
            return {"status": "error", "message": "Missing shop_id"}

        try:
            # Generate a unique event ID for tracking
            event_id = str(uuid.uuid4())

            # Publish event to Redis stream for background processing
            message_id = await streams_manager.publish_behavioral_event(
                event_id=event_id, shop_id=shop_id, payload=payload
            )

            logger.info(
                "Behavioral event queued for processing.",
                event_id=event_id,
                shop_id=shop_id,
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

    async def process_behavioral_event(self, shop_id: str, payload: Dict[str, Any]):
        """
        Validates and processes an incoming behavioral event from a Web Pixel.

        This method is intended to be called by a background worker that consumes
        messages from a Redis stream.
        """
        if not shop_id:
            logger.warning("Missing shop_id in request.")
            return {"status": "error", "message": "Missing shop_id"}

        try:
            # Use the pre-initialized TypeAdapter to correctly validate the Union type.
            validated_event = self.event_adapter.validate_python(payload)

            await self.repository.save_behavioral_event(
                shop_id, payload, validated_event
            )

            logger.info(
                "Successfully processed behavioral event.",
                event_id=validated_event.id,
                type=validated_event.name,
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
