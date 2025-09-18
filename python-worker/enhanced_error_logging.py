#!/usr/bin/env python3
"""
Enhanced error logging for interaction feature generator
"""
import asyncio
import sys
import os
from typing import Dict, List, Any, Optional

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.domains.ml.generators.interaction_feature_generator import (
    InteractionFeatureGenerator,
)

logger = get_logger(__name__)


class EnhancedInteractionFeatureGenerator(InteractionFeatureGenerator):
    """Enhanced interaction feature generator with comprehensive error logging"""

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from behavioral event with enhanced error logging"""
        try:
            event_type = event.get("interactionType", event.get("eventType", ""))
            event_data = event.get("metadata", event.get("eventData", {}))

            logger.debug(f"Extracting product ID from event type: {event_type}")

            if event_type == "product_viewed":
                # Handle both nested and direct structures
                product_variant = event_data.get("data", {}).get(
                    "productVariant", {}
                ) or event_data.get("productVariant", {})
                product = product_variant.get("product", {})
                product_id = product.get("id", "")

                if product_id:
                    logger.debug(
                        f"Extracted product ID from product_viewed: {product_id}"
                    )
                else:
                    logger.warning(
                        f"No product ID found in product_viewed event: {event}"
                    )

                return product_id

            elif event_type == "product_added_to_cart":
                # Handle both nested and direct structures
                cart_line = event_data.get("data", {}).get(
                    "cartLine", {}
                ) or event_data.get("cartLine", {})
                merchandise = cart_line.get("merchandise", {})
                product = merchandise.get("product", {})
                product_id = product.get("id", "")

                if product_id:
                    logger.debug(
                        f"Extracted product ID from product_added_to_cart: {product_id}"
                    )
                else:
                    logger.warning(
                        f"No product ID found in product_added_to_cart event: {event}"
                    )

                return product_id

            elif event_type == "checkout_completed":
                # For checkout, we'd need to check all line items
                checkout = event_data.get("data", {}).get(
                    "checkout", {}
                ) or event_data.get("checkout", {})
                line_items = checkout.get("lineItems", [])

                if not line_items:
                    logger.warning(
                        f"No line items found in checkout_completed event: {event}"
                    )
                    return None

                for item in line_items:
                    variant = item.get("variant", {})
                    product = variant.get("product", {})
                    product_id = product.get("id", "")
                    if product_id:
                        logger.debug(
                            f"Extracted product ID from checkout_completed: {product_id}"
                        )
                        return product_id

                logger.warning(
                    f"No product ID found in checkout_completed line items: {line_items}"
                )
                return None

            else:
                logger.debug(
                    f"Event type {event_type} not handled for product ID extraction"
                )
                return None

        except Exception as e:
            logger.error(f"Error extracting product ID from event: {str(e)}")
            logger.error(f"Event data: {event}")
            import traceback

            traceback.print_exc()
            return None

    def _filter_product_events(
        self,
        behavioral_events: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter behavioral events for specific customer-product pair with enhanced logging"""
        try:
            logger.debug(
                f"Filtering events for customer {customer_id}, product {product_id}"
            )
            logger.debug(f"Total events to filter: {len(behavioral_events)}")

            filtered_events = []

            for i, event in enumerate(behavioral_events):
                try:
                    # Check if event is for this customer
                    event_customer_id = event.get("customerId", "")
                    if event_customer_id != customer_id:
                        continue

                    # Extract product ID from event data based on event type
                    event_product_id = self._extract_product_id_from_event(event)

                    if not event_product_id:
                        continue

                    # If we have a mapping, use it to map the event product ID to the ProductData product ID
                    if product_id_mapping and event_product_id:
                        # Check if this event product ID maps to our target product ID
                        mapped_product_id = product_id_mapping.get(event_product_id)
                        if mapped_product_id == product_id:
                            filtered_events.append(event)
                            logger.debug(f"Added event {i} to filtered events (mapped)")
                    elif event_product_id == product_id:
                        # Fallback to direct comparison if no mapping provided
                        filtered_events.append(event)
                        logger.debug(f"Added event {i} to filtered events (direct)")

                except Exception as e:
                    logger.error(f"Error processing event {i}: {str(e)}")
                    logger.error(f"Event data: {event}")
                    continue

            logger.debug(
                f"Filtered {len(filtered_events)} events for customer {customer_id}, product {product_id}"
            )
            return filtered_events

        except Exception as e:
            logger.error(f"Error filtering product events: {str(e)}")
            import traceback

            traceback.print_exc()
            return []

    def _get_product_purchases(
        self,
        orders: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all purchases of a product by a customer with enhanced error logging"""
        try:
            logger.debug(
                f"Getting purchases for customer {customer_id}, product {product_id}"
            )
            logger.debug(f"Total orders to check: {len(orders)}")

            purchases = []

            for order_idx, order in enumerate(orders):
                try:
                    # Check if order is for this customer
                    order_customer_id = order.get("customerId", "")
                    if order_customer_id != customer_id:
                        continue

                    # Check line items for this product
                    line_items = order.get("lineItems", [])
                    if line_items is None:
                        logger.debug(f"Order {order_idx} has None line items")
                        line_items = []

                    logger.debug(f"Order {order_idx} has {len(line_items)} line items")

                    for item_idx, item in enumerate(line_items):
                        try:
                            # Extract product ID from line item
                            item_product_id = self._extract_product_id_from_line_item(
                                item
                            )

                            if not item_product_id:
                                logger.debug(
                                    f"Order {order_idx}, item {item_idx}: No product ID found"
                                )
                                continue

                            # If we have a mapping, use it to map the item product ID to the ProductData product ID
                            if product_id_mapping and item_product_id:
                                # Check if this item product ID maps to our target product ID
                                mapped_product_id = product_id_mapping.get(
                                    item_product_id
                                )
                                if mapped_product_id == product_id:
                                    purchase_data = {
                                        "order_id": order.get("orderId"),
                                        "order_date": order.get("orderDate"),
                                        "quantity": item.get("quantity", 1),
                                        "price": item.get("price", 0.0),
                                    }
                                    purchases.append(purchase_data)
                                    logger.debug(
                                        f"Added purchase from order {order_idx}, item {item_idx} (mapped)"
                                    )
                                    break  # Only count once per order
                            elif item_product_id == product_id:
                                # Fallback to direct comparison if no mapping provided
                                purchase_data = {
                                    "order_id": order.get("orderId"),
                                    "order_date": order.get("orderDate"),
                                    "quantity": item.get("quantity", 1),
                                    "price": item.get("price", 0.0),
                                }
                                purchases.append(purchase_data)
                                logger.debug(
                                    f"Added purchase from order {order_idx}, item {item_idx} (direct)"
                                )
                                break  # Only count once per order

                        except Exception as e:
                            logger.error(
                                f"Error processing order {order_idx}, item {item_idx}: {str(e)}"
                            )
                            logger.error(f"Item data: {item}")
                            continue

                except Exception as e:
                    logger.error(f"Error processing order {order_idx}: {str(e)}")
                    logger.error(f"Order data: {order}")
                    continue

            logger.debug(
                f"Found {len(purchases)} purchases for customer {customer_id}, product {product_id}"
            )
            return purchases

        except Exception as e:
            logger.error(f"Error getting product purchases: {str(e)}")
            import traceback

            traceback.print_exc()
            return []

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item with enhanced error logging"""
        try:
            logger.debug(f"Extracting product ID from line item: {line_item}")

            # This depends on your line item structure
            # Might be stored as productId, product.id, or in a variant
            if "productId" in line_item:
                product_id = line_item["productId"]
                logger.debug(f"Found productId: {product_id}")
                return product_id

            # If stored as GID
            if "product" in line_item and isinstance(line_item["product"], dict):
                product_id = line_item["product"].get("id", "")
                if product_id:
                    logger.debug(f"Found product.id: {product_id}")
                    return product_id

            # If stored in variant
            if "variant" in line_item and isinstance(line_item["variant"], dict):
                product = line_item["variant"].get("product", {})
                product_id = product.get("id", "")
                if product_id:
                    logger.debug(f"Found variant.product.id: {product_id}")
                    return product_id

            logger.warning(f"No product ID found in line item: {line_item}")
            return ""

        except Exception as e:
            logger.error(f"Error extracting product ID from line item: {str(e)}")
            logger.error(f"Line item data: {line_item}")
            import traceback

            traceback.print_exc()
            return ""


async def test_enhanced_generator():
    """Test the enhanced generator with comprehensive logging"""
    try:
        db = await get_database()
        shop_id = "cmfnmj5sn0000v3gaipwx948o"
        customer_id = "8619514265739"
        product_id = "7903465537675"

        print(f"Testing Enhanced Interaction Feature Generator")
        print(f"Shop: {shop_id}")
        print(f"Customer: {customer_id}")
        print(f"Product: {product_id}")

        # Get raw data
        behavioral_events = await db.userinteraction.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

        # Convert to dict format
        events_dict = []
        for event in behavioral_events:
            events_dict.append(
                {
                    "interactionType": event.interactionType,
                    "customerId": event.customerId,
                    "metadata": event.metadata,
                }
            )

        orders_dict = []
        for order in orders:
            orders_dict.append(
                {"customerId": order.customerId, "lineItems": order.lineItems}
            )

        # Test enhanced generator
        generator = EnhancedInteractionFeatureGenerator()
        context = {"behavioral_events": events_dict, "orders": orders_dict}

        print(f"\nGenerating features with enhanced logging...")
        features = await generator.generate_features(
            shop_id, customer_id, product_id, context
        )

        print(f"\nResults:")
        print(f"  View Count: {features.get('viewCount', 0)}")
        print(f"  Cart Add Count: {features.get('cartAddCount', 0)}")
        print(f"  Purchase Count: {features.get('purchaseCount', 0)}")
        print(f"  Interaction Score: {features.get('interactionScore', 0)}")
        print(f"  Affinity Score: {features.get('affinityScore', 0)}")

        return True

    except Exception as e:
        logger.error(f"Error in enhanced generator test: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_enhanced_generator())
