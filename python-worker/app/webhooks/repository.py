from typing import Dict, Any, Optional
from prisma import Json
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from .models import ShopifyBehavioralEvent
from datetime import datetime

logger = get_logger(__name__)


class WebhookRepository:
    def __init__(self):
        self._db_client = None

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    def _normalize_customer_id(self, customer_id: Optional[str]) -> Optional[str]:
        """
        Normalize customer ID from GID format to numeric format.

        Args:
            customer_id: Customer ID in GID format (e.g., "gid://shopify/Customer/24256") or None

        Returns:
            Normalized customer ID (e.g., "24256") or None
        """
        if not customer_id:
            return None

        # Handle GID format: gid://shopify/Customer/24256 -> 24256
        if customer_id.startswith("gid://shopify/Customer/"):
            return customer_id.split("/")[-1]

        # Return as-is if already in numeric format
        return customer_id

    def _normalize_gid_in_dict(self, data: Any) -> Any:
        """Recursively normalize GID IDs in nested dictionaries and lists"""
        if isinstance(data, dict):
            normalized = {}
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("gid://shopify/"):
                    # Normalize any GID field (not just 'id')
                    normalized[key] = value.split("/")[-1]
                elif isinstance(value, (dict, list)):
                    # Recursively normalize nested structures
                    normalized[key] = self._normalize_gid_in_dict(value)
                else:
                    normalized[key] = value
            return normalized
        elif isinstance(data, list):
            return [self._normalize_gid_in_dict(item) for item in data]
        else:
            return data

    async def save_behavioral_event(
        self,
        shop_id: str,
        raw_payload: Dict[str, Any],
        validated_event: ShopifyBehavioralEvent,
    ):
        """Saves the raw payload and the flexible, validated behavioral event."""
        try:
            db = await self._get_database()

            # Step 1: Save the full, raw payload for auditing using Prisma native method
            await db.rawbehavioralevents.create(
                data={
                    "shopId": shop_id,
                    "payload": Json(raw_payload),
                    "receivedAt": datetime.now(),
                }
            )

            # Step 2: Save the structured data to the main table using Prisma native method
            # Convert the specific 'data' part of the model to a dictionary
            event_data_dict = (
                validated_event.data.model_dump(by_alias=True, exclude_unset=True)
                if validated_event.data
                else None
            )

            # Normalize GID IDs in event data before saving
            normalized_event_data = (
                self._normalize_gid_in_dict(event_data_dict)
                if event_data_dict is not None
                else None
            )

            # Correctly handle the Json wrapper for the 'eventData' field
            event_data_json = (
                Json(normalized_event_data)
                if normalized_event_data is not None
                else None
            )

            # Extract clientId from raw payload for session tracking
            client_id = raw_payload.get("clientId")

            # Normalize customer ID from GID format to numeric format
            normalized_customer_id = self._normalize_customer_id(
                validated_event.customer_id
            )

            await db.behavioralevents.upsert(
                where={"eventId": validated_event.id},
                data={
                    "create": {
                        "eventId": validated_event.id,
                        "shopId": shop_id,
                        "customerId": normalized_customer_id,
                        "clientId": client_id,
                        "eventType": validated_event.name,
                        "timestamp": validated_event.timestamp,
                        "eventData": event_data_json,
                    },
                    "update": {
                        "customerId": normalized_customer_id,
                        "clientId": client_id,
                        "timestamp": validated_event.timestamp,
                        "eventData": event_data_json,
                    },
                },
            )

            logger.info(
                f"Successfully saved behavioral event {validated_event.id} for shop {shop_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to save behavioral event {validated_event.id} for shop {shop_id}: {str(e)}"
            )
            raise
