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
            logger.info(f"Processing order attribution for shop {shop_id}")

            # Extract note_attributes from the order
            note_attributes = order_item.get("noteAttributes", [])
            if not note_attributes:
                logger.info(
                    f"No note_attributes found in order {order_item.get('orderId')}"
                )
                return

            logger.info(f"Found {len(note_attributes)} note_attributes in order")

            # Extract recommendation attribution data
            attribution_data = {}
            for attr in note_attributes:
                if isinstance(attr, dict):
                    name = attr.get("name", "")
                    value = attr.get("value", "")

                    if name == "bb_recommendation_session_id":
                        attribution_data["session_id"] = value
                    elif name == "bb_recommendation_product_id":
                        attribution_data["product_id"] = value
                    elif name == "bb_recommendation_extension":
                        attribution_data["extension_type"] = value
                    elif name == "bb_recommendation_context":
                        attribution_data["context"] = value
                    elif name == "bb_recommendation_position":
                        attribution_data["position"] = value

            # Check if we have enough attribution data
            if not attribution_data.get("session_id"):
                logger.info(
                    f"No recommendation session ID found in order {order_item.get('orderId')}"
                )
                return

            logger.info(f"Extracted attribution data: {attribution_data}")

            # Create AttributionEvent record
            attribution_event = await self._create_order_attribution_event(
                shop_id=shop_id,
                order_item=order_item,
                attribution_data=attribution_data,
            )

            if attribution_event:
                logger.info(
                    f"Created attribution event {attribution_event.id} for order {order_item.get('orderId')}"
                )

                # Create RecommendationAttribution record for billing
                recommendation_attribution = (
                    await self._create_recommendation_attribution(
                        shop_id=shop_id,
                        order_item=order_item,
                        attribution_data=attribution_data,
                    )
                )

                if recommendation_attribution:
                    logger.info(
                        f"Created recommendation attribution {recommendation_attribution.id} for billing"
                    )

        except Exception as e:
            logger.error(f"Failed to extract order attribution: {e}")

    async def _create_order_attribution_event(
        self, shop_id: str, order_item: Dict[str, Any], attribution_data: Dict[str, Any]
    ) -> Optional[AttributionEvent]:
        """
        Create an AttributionEvent record from order attribution data

        Args:
            shop_id: Shop ID
            order_item: Order item data
            attribution_data: Extracted attribution data

        Returns:
            Created AttributionEvent or None
        """
        try:
            # Extract order and customer information
            order_id = order_item.get("orderId")
            customer_id = order_item.get("customerId")
            customer_email = order_item.get("customerEmail")
            total_amount = order_item.get("totalAmount", 0.0)
            currency_code = order_item.get("currencyCode", "USD")

            # Create attribution event data
            attribution_event_data = {
                "shopId": shop_id,
                "customerId": customer_id,
                "customerEmail": customer_email,
                "sessionId": attribution_data.get("session_id"),
                "productId": attribution_data.get("product_id"),
                "extensionType": attribution_data.get("extension_type", "unknown"),
                "context": attribution_data.get("context", "order"),
                "position": (
                    int(attribution_data.get("position", 0))
                    if attribution_data.get("position")
                    else 0
                ),
                "eventType": "order_completed",
                "revenue": total_amount,
                "currency": currency_code,
                "orderId": order_id,
                "metadata": {
                    "source": "order_attribution",
                    "order_name": order_item.get("orderName"),
                    "order_date": (
                        order_item.get("orderDate").isoformat()
                        if order_item.get("orderDate")
                        else None
                    ),
                    "financial_status": order_item.get("financialStatus"),
                    "fulfillment_status": order_item.get("fulfillmentStatus"),
                },
            }

            logger.info(
                f"Creating attribution event with data: {attribution_event_data}"
            )

            # Create the attribution event
            attribution_event = await self.db.attributionevent.create(
                data=attribution_event_data
            )

            logger.info(
                f"Successfully created attribution event {attribution_event.id}"
            )
            return attribution_event

        except Exception as e:
            logger.error(f"Failed to create order attribution event: {e}")
            return None

    async def _create_recommendation_attribution(
        self, shop_id: str, order_item: Dict[str, Any], attribution_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Create a RecommendationAttribution record for billing revenue tracking

        Args:
            shop_id: Shop ID
            order_item: Order item data
            attribution_data: Extracted attribution data

        Returns:
            Created RecommendationAttribution or None
        """
        try:
            # Extract order and revenue information
            order_id = order_item.get("orderId")
            product_id = attribution_data.get("product_id")
            total_amount = order_item.get("totalAmount", 0.0)
            currency_code = order_item.get("currencyCode", "USD")

            # Create recommendation attribution data for billing
            recommendation_attribution_data = {
                "shopId": shop_id,
                "sessionId": attribution_data.get("session_id"),
                "productId": product_id,
                "orderId": order_id,
                "extensionType": attribution_data.get("extension_type", "unknown"),
                "context": attribution_data.get("context", "order"),
                "position": (
                    int(attribution_data.get("position", 0))
                    if attribution_data.get("position")
                    else 0
                ),
                "revenue": total_amount,
                "attributionSource": "cart_attributes",
                "confidenceScore": 1.0,  # High confidence since it's from cart attributes
                "status": "confirmed",
            }

            logger.info(
                f"Creating recommendation attribution for billing: {recommendation_attribution_data}"
            )

            # Create the recommendation attribution record
            recommendation_attribution = await self.db.recommendationattribution.create(
                data=recommendation_attribution_data
            )

            logger.info(
                f"Successfully created recommendation attribution {recommendation_attribution.id} for billing"
            )
            return recommendation_attribution

        except Exception as e:
            logger.error(
                f"Failed to create recommendation attribution for billing: {e}"
            )
            return None

    async def _link_attribution_to_order(
        self,
        shop_id: str,
        customer_id: str,
        attribution_data: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> None:
        """
        Link all attribution events for this customer to the completed order
        and create RecommendationAttributions records for revenue tracking

        Args:
            shop_id: Shop ID
            customer_id: Customer ID
            attribution_data: Attribution data from the checkout_completed event
            event_data: Full event data containing order information
        """
        try:
            # Extract order ID and revenue data from the checkout_completed event
            order_id = None
            total_price = 0.0
            currency_code = "USD"
            line_items = []

            if "data" in event_data and "checkout" in event_data["data"]:
                checkout_data = event_data["data"]["checkout"]
                if "order" in checkout_data and "id" in checkout_data["order"]:
                    order_id = checkout_data["order"]["id"]

                if (
                    "totalPrice" in checkout_data
                    and "amount" in checkout_data["totalPrice"]
                ):
                    total_price = float(checkout_data["totalPrice"]["amount"])

                if "currencyCode" in checkout_data:
                    currency_code = checkout_data["currencyCode"]

                if "lineItems" in checkout_data:
                    line_items = checkout_data["lineItems"]

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

            # Create RecommendationAttributions records for revenue tracking
            await self._create_recommendation_attributions(
                shop_id,
                order_id,
                attribution_events,
                line_items,
                total_price,
                currency_code,
            )

        except Exception as e:
            logger.error(f"Failed to link attribution to order: {e}")

    async def _create_recommendation_attributions(
        self,
        shop_id: str,
        order_id: str,
        attribution_events: list,
        line_items: list,
        total_price: float,
        currency_code: str,
    ) -> None:
        """
        Create RecommendationAttributions records for revenue tracking

        Args:
            shop_id: Shop ID
            order_id: Order ID
            attribution_events: List of attribution events linked to this order
            line_items: Order line items
            total_price: Total order price
            currency_code: Currency code
        """
        try:
            if not attribution_events:
                logger.warning(f"No attribution events found for order {order_id}")
                return

            # Create a map of product_id to revenue for this order
            product_revenue_map = {}
            for item in line_items:
                if "variant" in item and "product" in item["variant"]:
                    product_id = item["variant"]["product"]["id"]
                    if "finalLinePrice" in item and "amount" in item["finalLinePrice"]:
                        revenue = float(item["finalLinePrice"]["amount"])
                        product_revenue_map[product_id] = revenue

            # If no line item revenue found, distribute total price equally among attributed products
            if not product_revenue_map and attribution_events:
                revenue_per_product = total_price / len(attribution_events)
                for event in attribution_events:
                    product_revenue_map[event.productId] = revenue_per_product

            # Create RecommendationAttributions for each attribution event
            created_count = 0
            for event in attribution_events:
                # Get revenue for this product
                product_revenue = product_revenue_map.get(event.productId, 0.0)

                if product_revenue > 0:
                    try:
                        # Create RecommendationAttribution record
                        await self.db.recommendationattribution.create(
                            data={
                                "shopId": shop_id,
                                "sessionId": event.sessionId,
                                "productId": event.productId,
                                "orderId": order_id,
                                "extensionType": "venus",  # Default to venus extension
                                "context": "profile",  # Default context, could be extracted from session
                                "position": event.position,
                                "revenue": product_revenue,
                                "attributionSource": "customer_behavior",
                                "confidenceScore": 1.0,
                                "attributionDate": datetime.utcnow(),
                                "status": "confirmed",
                            }
                        )
                        created_count += 1
                        logger.info(
                            f"Created RecommendationAttribution: order {order_id}, "
                            f"product {event.productId}, revenue {product_revenue} {currency_code}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to create RecommendationAttribution for product {event.productId}: {e}"
                        )

            logger.info(
                f"Created {created_count} RecommendationAttributions for order {order_id}"
            )

        except Exception as e:
            logger.error(f"Failed to create recommendation attributions: {e}")

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
