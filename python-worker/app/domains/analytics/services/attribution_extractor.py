"""
Attribution Extractor for processing behavioral events and extracting attribution data
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

from prisma import Prisma
from prisma.models import AttributionEvent
import logging

logger = logging.getLogger(__name__)


class AttributionExtractor:
    def __init__(self, db: Prisma):
        self.db = db

    async def process_behavioral_event_for_attribution(
        self,
        shop_id: str,
        customer_id: str,
        event_data: Dict[str, Any],
        event_type: str,
    ) -> Optional[AttributionEvent]:
        """
        Process a behavioral event to extract and store attribution data

        Args:
            shop_id: Shop ID
            customer_id: Customer ID
            event_data: Event data from the behavioral event
            event_type: Type of event (page_viewed, product_added_to_cart, etc.)

        Returns:
            Created AttributionEvent or None if no attribution found
        """
        try:
            logger.info(
                f"Processing attribution for event: {event_type}, customer: {customer_id}"
            )
            logger.info(
                f"Event data keys: {list(event_data.keys()) if event_data else 'None'}"
            )

            # Extract attribution data from the event (from Atlas sessionStorage)
            attribution_data = self._extract_attribution_from_event_data(
                event_data, event_type
            )

            if not attribution_data:
                logger.info(f"No attribution data found for event: {event_type}")
                return None

            # Store attribution event
            attribution_event = await self._store_attribution_event(
                shop_id=shop_id,
                customer_id=customer_id,
                attribution_data=attribution_data,
                original_event_data=event_data,
            )

            if attribution_event:
                logger.info(
                    f"Created attribution event for session {attribution_data['ref']}, "
                    f"product {attribution_data['src']}, type {attribution_data['event_type']}"
                )

                # If this is a checkout_completed event, link all attribution events to the order
                if attribution_data["event_type"] == "checkout_completed":
                    await self._link_attribution_to_order(
                        shop_id, customer_id, attribution_data, event_data
                    )

            return attribution_event

        except Exception as e:
            logger.error(f"Failed to process behavioral event for attribution: {e}")
            return None

    def _extract_attribution_from_event_data(
        self, event_data: Dict[str, Any], event_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract attribution data from event data (sent by Atlas from sessionStorage)

        Args:
            event_data: Event data
            event_type: Type of event

        Returns:
            Attribution data dict or None if no attribution found
        """
        try:
            # Check if attribution data is included in the event (from Atlas sessionStorage)
            ref = event_data.get("ref")
            src = event_data.get("src")
            pos = event_data.get("pos")

            logger.info(f"Extracting attribution - ref: {ref}, src: {src}, pos: {pos}")

            if ref:
                attribution_data = {
                    "ref": ref,
                    "src": src or "unknown",
                    "pos": pos or "0",
                    "event_type": event_type,
                }
                logger.info(f"Found attribution data: {attribution_data}")
                return attribution_data

            logger.info("No attribution data found (no ref)")
            return None

        except Exception as e:
            logger.error(f"Failed to extract attribution from event data: {e}")
            return None

    async def _store_attribution_event(
        self,
        shop_id: str,
        customer_id: str,
        attribution_data: Dict[str, Any],
        original_event_data: Dict[str, Any],
    ) -> Optional[AttributionEvent]:
        """
        Store attribution event in the database

        Args:
            shop_id: Shop ID
            customer_id: Customer ID
            attribution_data: Extracted attribution data
            original_event_data: Original event data

        Returns:
            Created AttributionEvent or None if failed
        """
        try:
            if not customer_id:
                logger.warning(f"No customer ID provided for attribution event")
                return None

            # Resolve short ref to full session ID
            full_session_id = await self._resolve_short_ref_to_session_id(
                attribution_data["ref"], shop_id
            )

            if not full_session_id:
                logger.warning(
                    f"Could not resolve short ref {attribution_data['ref']} to full session ID, using short ref as session ID"
                )
                # Use the short ref as the session ID for now
                full_session_id = attribution_data["ref"]

            # Create attribution event
            attribution_event = await self.db.attributionevent.create(
                data={
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "sessionId": full_session_id,
                    "productId": attribution_data["src"],
                    "position": int(attribution_data["pos"]),
                    "eventType": attribution_data["event_type"],
                }
            )

            return attribution_event

        except Exception as e:
            logger.error(f"Failed to store attribution event: {e}")
            return None

    async def extract_order_attribution(self, order_item: Dict[str, Any], shop_id: str):
        """
        Extract attribution data from order items
        This method is called from the main table storage service

        Args:
            order_item: Order item data
            shop_id: Shop ID
        """
        try:
            # This is a placeholder for order-level attribution extraction
            # You can implement order-specific attribution logic here
            logger.info(f"Processing order attribution for shop {shop_id}")

        except Exception as e:
            logger.error(f"Failed to extract order attribution: {e}")

    async def _link_attribution_to_order(
        self,
        shop_id: str,
        customer_id: str,
        attribution_data: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> None:
        """
        Link all attribution events for this customer to the completed order

        Args:
            shop_id: Shop ID
            customer_id: Customer ID
            attribution_data: Attribution data from the checkout_completed event
            event_data: Full event data containing order information
        """
        try:
            # Extract order ID from the checkout_completed event
            order_id = None
            if "data" in event_data and "checkout" in event_data["data"]:
                checkout_data = event_data["data"]["checkout"]
                if "order" in checkout_data and "id" in checkout_data["order"]:
                    order_id = checkout_data["order"]["id"]

            if not order_id:
                logger.warning("No order ID found in checkout_completed event")
                return

            logger.info(f"Linking attribution events to order {order_id}")

            # Find all attribution events for this customer that don't have an order linked yet
            attribution_events = await self.db.attributionevent.find_many(
                where={
                    "customerId": customer_id,
                    "orderId": None,  # Only unlinked events
                }
            )

            # Link each attribution event to the order
            linked_count = 0
            for event in attribution_events:
                await self.db.attributionevent.update(
                    where={"id": event.id},
                    data={
                        "orderId": order_id,
                        "linkedAt": datetime.utcnow(),
                    },
                )
                linked_count += 1

            logger.info(f"Linked {linked_count} attribution events to order {order_id}")

        except Exception as e:
            logger.error(f"Failed to link attribution to order: {e}")

    async def _resolve_short_ref_to_session_id(
        self, short_ref: str, shop_id: str
    ) -> Optional[str]:
        """
        Resolve a short reference to the full session ID by checking all recommendation sessions
        and finding one that hashes to the same short reference

        Args:
            short_ref: Short reference (6 characters)
            shop_id: Shop ID

        Returns:
            Full session ID or None if not found
        """
        try:
            # Get all recommendation sessions for this shop
            sessions = await self.db.recommendationsession.find_many(
                where={"shopId": shop_id},
                take=1000,  # Limit to avoid performance issues
            )

            # Check each session to see if it hashes to our short_ref
            for session in sessions:
                if self._hash_session_id(session.id) == short_ref:
                    return session.id

            logger.warning(
                f"Could not resolve short ref {short_ref} to full session ID"
            )
            return None

        except Exception as e:
            logger.error(f"Failed to resolve short ref {short_ref}: {e}")
            return None

    def _hash_session_id(self, session_id: str) -> str:
        """
        Create a deterministic hash of the session ID (same algorithm as frontend)

        Args:
            session_id: Full session ID

        Returns:
            Short reference (6 characters)
        """
        hash_value = 0
        for char in session_id:
            hash_value = ((hash_value << 5) - hash_value + ord(char)) & 0xFFFFFFFF

        # Convert to base36 and take first 6 characters (same as frontend)
        import math

        if hash_value == 0:
            return "0"

        # Convert to base36
        base36_chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        result = ""
        while hash_value > 0:
            result = base36_chars[hash_value % 36] + result
            hash_value //= 36

        return result[:6]
