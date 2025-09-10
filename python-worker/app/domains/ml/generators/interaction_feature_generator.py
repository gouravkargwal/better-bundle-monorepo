"""
Customer-Product Interaction Feature Generator for ML feature engineering
Aligned with InteractionFeatures table schema
"""

import datetime
from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class InteractionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for customer-product interactions"""

    async def generate_features(
        self,
        shop_id: str,
        customer_id: str,
        product_id: str,
        context: Dict[str, Any],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate interaction features between a customer and product

        Args:
            shop_id: The shop ID
            customer_id: The customer ID
            product_id: The product ID
            context: Additional context data (orders, behavioral_events)

        Returns:
            Dictionary matching InteractionFeatures table schema
        """
        try:
            logger.debug(
                f"Computing interaction features for shop: {shop_id}, "
                f"customer: {customer_id}, product: {product_id}"
            )

            # Get relevant data from context
            behavioral_events = context.get("behavioral_events", [])
            orders = context.get("orders", [])

            # Product IDs are already normalized at data ingestion level
            numeric_product_id = product_id

            # Filter events for this customer-product pair
            product_events = self._filter_product_events(
                behavioral_events, customer_id, numeric_product_id, product_id_mapping
            )

            # Get purchase data
            product_purchases = self._get_product_purchases(
                orders, customer_id, numeric_product_id, product_id_mapping
            )

            # Core event counts
            view_count = self._count_product_views(product_events)
            cart_add_count = self._count_cart_adds(product_events)
            cart_view_count = self._count_cart_views(product_events)
            cart_remove_count = self._count_cart_removes(product_events)
            purchase_count = len(product_purchases)

            # Temporal features
            temporal_features = self._compute_temporal_features(
                product_events, product_purchases
            )

            # Interaction score (weighted combination)
            interaction_score = self._compute_interaction_score(
                view_count, cart_add_count, purchase_count
            )

            # Affinity score (normalized 0-1)
            affinity_score = self._compute_affinity_score(
                view_count, cart_add_count, purchase_count, temporal_features
            )

            features = {
                "shopId": shop_id,
                "customerId": customer_id,
                "productId": product_id,
                "viewCount": view_count,
                "cartAddCount": cart_add_count,
                "cartViewCount": cart_view_count,
                "cartRemoveCount": cart_remove_count,
                "purchaseCount": purchase_count,
                "firstViewDate": temporal_features.get("first_view_date"),
                "lastViewDate": temporal_features.get("last_view_date"),
                "firstPurchaseDate": temporal_features.get("first_purchase_date"),
                "lastPurchaseDate": temporal_features.get("last_purchase_date"),
                "viewToPurchaseDays": temporal_features.get("view_to_purchase_days"),
                "interactionSpanDays": temporal_features.get("interaction_span_days"),
                "interactionScore": interaction_score,
                "affinityScore": affinity_score,
                "lastComputedAt": now_utc(),
            }

            logger.debug(
                f"Computed interaction features for customer: {customer_id}, "
                f"product: {product_id} - Score: {interaction_score:.2f}"
            )

            return features

        except Exception as e:
            logger.error(f"Failed to compute interaction features: {str(e)}")
            return self._get_default_features(shop_id, customer_id, product_id)

    def _filter_product_events(
        self,
        behavioral_events: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter behavioral events for specific customer-product pair"""
        filtered_events = []

        for event in behavioral_events:
            # Check if event is for this customer
            # Customer IDs are already normalized at data ingestion level
            event_customer_id = event.get("customerId", "")
            if event_customer_id != customer_id:
                continue

            # Extract product ID from event data based on event type
            event_product_id = self._extract_product_id_from_event(event)

            # If we have a mapping, use it to map the event product ID to the ProductData product ID
            if product_id_mapping and event_product_id:
                # Check if this event product ID maps to our target product ID
                mapped_product_id = product_id_mapping.get(event_product_id)
                if mapped_product_id == product_id:
                    filtered_events.append(event)
            elif event_product_id == product_id:
                # Fallback to direct comparison if no mapping provided
                filtered_events.append(event)

        return filtered_events

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from behavioral event"""
        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if event_type == "product_viewed":
            # Handle both nested and direct structures
            product_variant = event_data.get("data", {}).get(
                "productVariant", {}
            ) or event_data.get("productVariant", {})
            product = product_variant.get("product", {})
            return product.get("id", "")

        elif event_type == "product_added_to_cart":
            # Handle both nested and direct structures
            cart_line = event_data.get("data", {}).get(
                "cartLine", {}
            ) or event_data.get("cartLine", {})
            merchandise = cart_line.get("merchandise", {})
            product = merchandise.get("product", {})
            return product.get("id", "")

        elif event_type == "checkout_completed":
            # For checkout, we'd need to check all line items
            checkout = event_data.get("data", {}).get("checkout", {}) or event_data.get(
                "checkout", {}
            )
            line_items = checkout.get("lineItems", [])
            for item in line_items:
                variant = item.get("variant", {})
                product = variant.get("product", {})
                product_id = product.get("id", "")
                if product_id:
                    return product_id

        return None

    def _get_product_purchases(
        self,
        orders: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all purchases of a product by a customer"""
        purchases = []

        for order in orders:
            # Check if order is for this customer
            # Customer IDs are already normalized at data ingestion level
            order_customer_id = order.get("customerId", "")
            if order_customer_id != customer_id:
                continue

            # Check line items for this product
            line_items = order.get("lineItems", [])
            for item in line_items:
                # Extract product ID from line item
                # Note: You might need to adjust this based on your line item structure
                item_product_id = self._extract_product_id_from_line_item(item)

                # If we have a mapping, use it to map the item product ID to the ProductData product ID
                if product_id_mapping and item_product_id:
                    # Check if this item product ID maps to our target product ID
                    mapped_product_id = product_id_mapping.get(item_product_id)
                    if mapped_product_id == product_id:
                        purchases.append(
                            {
                                "order_id": order.get("orderId"),
                                "order_date": order.get("orderDate"),
                                "quantity": item.get("quantity", 1),
                                "price": item.get("price", 0.0),
                            }
                        )
                        break  # Only count once per order
                elif item_product_id == product_id:
                    # Fallback to direct comparison if no mapping provided
                    purchases.append(
                        {
                            "order_id": order.get("orderId"),
                            "order_date": order.get("orderDate"),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", 0.0),
                        }
                    )
                    break  # Only count once per order

        return purchases

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        # This depends on your line item structure
        # Might be stored as productId, product.id, or in a variant
        if "productId" in line_item:
            return line_item["productId"]

        # If stored as GID
        if "product" in line_item and isinstance(line_item["product"], dict):
            return line_item["product"].get("id", "")

        # If stored in variant
        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            return product.get("id", "")

        return ""

    def _count_product_views(self, product_events: List[Dict[str, Any]]) -> int:
        """Count product view events"""
        return sum(
            1 for event in product_events if event.get("eventType") == "product_viewed"
        )

    def _count_cart_adds(self, product_events: List[Dict[str, Any]]) -> int:
        """Count add to cart events"""
        return sum(
            1
            for event in product_events
            if event.get("eventType") == "product_added_to_cart"
        )

    def _count_cart_views(self, product_events: List[Dict[str, Any]]) -> int:
        """Count cart view events"""
        return sum(
            1 for event in product_events if event.get("eventType") == "cart_viewed"
        )

    def _count_cart_removes(self, product_events: List[Dict[str, Any]]) -> int:
        """Count product removed from cart events"""
        return sum(
            1
            for event in product_events
            if event.get("eventType") == "product_removed_from_cart"
        )

    def _compute_temporal_features(
        self,
        product_events: List[Dict[str, Any]],
        product_purchases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute temporal features"""
        features = {
            "first_view_date": None,
            "last_view_date": None,
            "first_purchase_date": None,
            "last_purchase_date": None,
            "view_to_purchase_days": None,
            "interaction_span_days": None,
        }

        # Get view dates
        view_events = [
            e for e in product_events if e.get("eventType") == "product_viewed"
        ]

        if view_events:
            view_dates = [self._parse_date(e.get("timestamp")) for e in view_events]
            view_dates = [d for d in view_dates if d]  # Filter None values

            if view_dates:
                features["first_view_date"] = min(view_dates)
                features["last_view_date"] = max(view_dates)

        # Get purchase dates
        if product_purchases:
            purchase_dates = [
                self._parse_date(p.get("order_date")) for p in product_purchases
            ]
            purchase_dates = [d for d in purchase_dates if d]

            if purchase_dates:
                features["first_purchase_date"] = min(purchase_dates)
                features["last_purchase_date"] = max(purchase_dates)

        # Calculate view to purchase days
        if features["first_view_date"] and features["first_purchase_date"]:
            delta = features["first_purchase_date"] - features["first_view_date"]
            features["view_to_purchase_days"] = max(0, delta.days)

        # Calculate interaction span
        all_dates = []
        if features["first_view_date"]:
            all_dates.append(features["first_view_date"])
        if features["last_view_date"]:
            all_dates.append(features["last_view_date"])
        if features["first_purchase_date"]:
            all_dates.append(features["first_purchase_date"])
        if features["last_purchase_date"]:
            all_dates.append(features["last_purchase_date"])

        if len(all_dates) >= 2:
            span = max(all_dates) - min(all_dates)
            features["interaction_span_days"] = span.days

        return features

    def _compute_interaction_score(
        self, view_count: int, cart_add_count: int, purchase_count: int
    ) -> float:
        """
        Compute weighted interaction score
        Formula: views * 1 + cart_adds * 3 + purchases * 7
        """
        return (view_count * 1.0) + (cart_add_count * 3.0) + (purchase_count * 7.0)

    def _compute_affinity_score(
        self,
        view_count: int,
        cart_add_count: int,
        purchase_count: int,
        temporal_features: Dict[str, Any],
    ) -> float:
        """
        Compute normalized affinity score (0-1)
        Takes into account interaction strength and recency
        """
        # Base affinity from interactions
        if view_count == 0:
            return 0.0

        # Conversion rates
        view_to_cart_rate = cart_add_count / max(view_count, 1)
        cart_to_purchase_rate = (
            purchase_count / max(cart_add_count, 1) if cart_add_count > 0 else 0
        )

        # Base score from conversion funnel
        base_score = (view_to_cart_rate * 0.3) + (cart_to_purchase_rate * 0.5)

        # Add purchase bonus
        if purchase_count > 0:
            base_score += 0.2

        # Recency boost
        if temporal_features.get("last_view_date"):
            days_since_last = (now_utc() - temporal_features["last_view_date"]).days
            recency_factor = max(0, 1 - (days_since_last / 365))  # Decay over a year
            base_score *= 0.7 + 0.3 * recency_factor  # 70% base + 30% recency

        # Ensure score is between 0 and 1
        return min(max(base_score, 0.0), 1.0)

    def _parse_date(self, date_value: Any) -> Optional[datetime.datetime]:
        """Parse date from various formats"""
        if not date_value:
            return None

        if isinstance(date_value, datetime.datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                # Handle ISO format with Z timezone
                return datetime.datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
            except:
                return None

        return None

    def _get_default_features(
        self, shop_id: str, customer_id: str, product_id: str
    ) -> Dict[str, Any]:
        """Return default features when computation fails"""
        return {
            "shopId": shop_id,
            "customerId": customer_id,
            "productId": product_id,
            "viewCount": 0,
            "cartAddCount": 0,
            "purchaseCount": 0,
            "firstViewDate": None,
            "lastViewDate": None,
            "firstPurchaseDate": None,
            "lastPurchaseDate": None,
            "viewToPurchaseDays": None,
            "interactionSpanDays": None,
            "interactionScore": 0.0,
            "affinityScore": 0.0,
            "lastComputedAt": now_utc(),
        }
