import uuid
from typing import Dict, Any
from pydantic import ValidationError, TypeAdapter
from .repository import WebhookRepository
from .models import ShopifyBehavioralEvent
from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.core.database.simple_db_client import get_database

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
            result = await db.behavioralevents.update_many(
                where={"shopId": shop_id, "clientId": client_id, "customerId": None},
                data={"customerId": customer_id},
            )

            logger.info(
                f"Backfilled {result.count} events for {client_id} → {customer_id}"
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
                await self._handle_customer_linking(
                    shop_db_id,
                    validated_event.data.clientId,
                    validated_event.data.customerId,
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
