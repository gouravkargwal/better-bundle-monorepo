"""
Product-Pair Co-occurrence Feature Generator for ML feature engineering
Aligned with the ProductPairFeatures table schema
"""

import datetime
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductPairFeatureGenerator(BaseFeatureGenerator):
    """
    Feature generator for product-pair co-occurrence, designed for
    market basket analysis and identifying product relationships.
    """

    async def generate_features(
        self,
        shop_id: str,
        product_id1: str,
        product_id2: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generates co-occurrence features for a pair of products.

        Args:
            shop_id: The shop ID.
            product_id1: The first product ID in the pair.
            product_id2: The second product ID in the pair.
            context: Additional context data, primarily `orders` and `behavioral_events`.

        Returns:
            A dictionary of features matching the ProductPairFeatures schema.
        """
        try:
            logger.debug(
                f"Computing product pair features for shop: {shop_id}, "
                f"products: ({product_id1}, {product_id2})"
            )

            # Get raw data from context
            orders = context.get("orders", [])
            behavioral_events = context.get("behavioral_events", [])

            # 1. Co-purchase Analysis from Orders
            co_purchase_count, last_co_purchase_date = self._calculate_co_purchases(
                orders, product_id1, product_id2
            )

            # 2. Co-occurrence Analysis from Behavioral Events
            # Group events by session for efficient analysis
            sessions = self._group_events_by_session(behavioral_events)

            co_view_count, last_co_view_date = self._calculate_co_occurrences(
                sessions, product_id1, product_id2, "views"
            )
            co_cart_count, last_co_cart_date = self._calculate_co_occurrences(
                sessions, product_id1, product_id2, "carts"
            )

            # 3. Calculate Advanced Metrics (Support, Lift)
            # These are typically based on purchases
            metrics = self._calculate_association_metrics(
                orders, co_purchase_count, product_id1, product_id2
            )
            support_score = metrics.get("support", 0.0)
            lift_score = metrics.get("lift", 0.0)

            # 4. Determine the most recent co-occurrence timestamp
            last_co_occurrence = self._get_latest_timestamp(
                [
                    last_co_purchase_date,
                    last_co_view_date,
                    last_co_cart_date,
                ]
            )

            features = {
                "shopId": shop_id,
                "productId1": product_id1,
                "productId2": product_id2,
                "coPurchaseCount": co_purchase_count,
                "coViewCount": co_view_count,
                "coCartCount": co_cart_count,
                "supportScore": support_score,
                "liftScore": lift_score,
                "lastCoOccurrence": last_co_occurrence,
                "lastComputedAt": now_utc(),
            }

            logger.debug(
                f"Computed pair features for ({product_id1}, {product_id2}): "
                f"Co-purchase={co_purchase_count}, Lift={lift_score:.2f}"
            )

            return features

        except Exception as e:
            logger.error(
                f"Failed to compute product pair features for ({product_id1}, {product_id2}): {str(e)}",
                exc_info=True,
            )
            return self._get_default_features(shop_id, product_id1, product_id2)

    def _calculate_co_purchases(
        self, orders: List[Dict[str, Any]], product_id1: str, product_id2: str
    ) -> Tuple[int, Optional[datetime.datetime]]:
        """Counts how many orders contain both products."""
        count = 0
        last_date = None
        target_ids = {product_id1, product_id2}

        for order in orders:
            line_items = order.get("lineItems", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item) for item in line_items
            }

            if target_ids.issubset(product_ids_in_order):
                count += 1
                order_date = self._parse_date(order.get("orderDate"))
                if order_date and (last_date is None or order_date > last_date):
                    last_date = order_date

        return count, last_date

    def _group_events_by_session(
        self, behavioral_events: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Groups behavioral events by session ID for co-occurrence analysis."""
        sessions = defaultdict(
            lambda: {
                "views": set(),
                "carts": set(),
                "cart_views": set(),
                "cart_removes": set(),
                "timestamps": [],
            }
        )

        for event in behavioral_events:
            # Extract session ID from event record
            session_id = event.get("clientId")  # clientId is now stored directly
            if not session_id:
                continue

            event_type = event.get("eventType")
            product_id = self._extract_product_id_from_event(event)

            if not product_id:
                continue

            if event_type == "product_viewed":
                sessions[session_id]["views"].add(product_id)
            elif event_type == "product_added_to_cart":
                sessions[session_id]["carts"].add(product_id)
            elif event_type == "cart_viewed":
                sessions[session_id]["cart_views"].add(product_id)
            elif event_type == "product_removed_from_cart":
                sessions[session_id]["cart_removes"].add(product_id)

            timestamp = self._parse_date(event.get("timestamp"))
            if timestamp:
                sessions[session_id]["timestamps"].append(timestamp)

        return sessions

    def _calculate_co_occurrences(
        self,
        sessions: Dict[str, Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        occurrence_type: str,  # "views" or "carts"
    ) -> Tuple[int, Optional[datetime.datetime]]:
        """Counts sessions where both products were viewed or added to cart."""
        count = 0
        last_date = None
        target_ids = {product_id1, product_id2}

        for session_data in sessions.values():
            if target_ids.issubset(session_data.get(occurrence_type, set())):
                count += 1
                if session_data["timestamps"]:
                    session_max_ts = max(session_data["timestamps"])
                    if last_date is None or session_max_ts > last_date:
                        last_date = session_max_ts
        return count, last_date

    def _calculate_association_metrics(
        self,
        orders: List[Dict[str, Any]],
        co_purchase_count: int,
        product_id1: str,
        product_id2: str,
    ) -> Dict[str, float]:
        """Calculates Support and Lift scores."""
        total_orders = len(orders)
        if total_orders == 0 or co_purchase_count == 0:
            return {"support": 0.0, "lift": 0.0}

        # Support(A, B) = Transactions({A,B}) / Total Transactions
        support_ab = co_purchase_count / total_orders

        # Calculate individual product purchase counts
        p1_purchases = 0
        p2_purchases = 0
        for order in orders:
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item)
                for item in order.get("lineItems", [])
            }
            if product_id1 in product_ids_in_order:
                p1_purchases += 1
            if product_id2 in product_ids_in_order:
                p2_purchases += 1

        if p1_purchases == 0 or p2_purchases == 0:
            return {"support": support_ab, "lift": 0.0}

        # Support(A) = Transactions({A}) / Total Transactions
        support_a = p1_purchases / total_orders
        support_b = p2_purchases / total_orders

        # Lift(A, B) = Support(A, B) / (Support(A) * Support(B))
        denominator = support_a * support_b
        lift = support_ab / denominator if denominator > 0 else 0.0

        return {"support": support_ab, "lift": lift}

    def _get_latest_timestamp(
        self, dates: List[Optional[datetime.datetime]]
    ) -> Optional[datetime.datetime]:
        """Returns the most recent datetime from a list, ignoring Nones."""
        valid_dates = [d for d in dates if d is not None]
        return max(valid_dates) if valid_dates else None

    # --- Utility Methods (reused from your example) ---

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if event_type == "product_viewed":
            product = (
                event_data.get("data", {}).get("productVariant", {}).get("product", {})
            )
            return self._extract_id_from_gid(product.get("id", ""))
        elif event_type == "product_added_to_cart":
            product = (
                event_data.get("data", {})
                .get("cartLine", {})
                .get("merchandise", {})
                .get("product", {})
            )
            return self._extract_id_from_gid(product.get("id", ""))
        return None

    def _extract_id_from_gid(self, gid: str) -> str:
        if not gid:
            return ""
        return gid.split("/")[-1] if "/" in gid else gid

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        if "productId" in line_item:
            return str(line_item["productId"])
        if "id" in line_item:  # Fallback for simpler structures
            return str(line_item["id"])
        return ""

    def _parse_date(self, date_value: Any) -> Optional[datetime.datetime]:
        if not date_value:
            return None
        if isinstance(date_value, datetime.datetime):
            return date_value
        if isinstance(date_value, str):
            try:
                return datetime.datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                return None
        return None

    def _get_default_features(
        self, shop_id: str, product_id1: str, product_id2: str
    ) -> Dict[str, Any]:
        """Returns a default feature set when computation fails."""
        return {
            "shopId": shop_id,
            "productId1": product_id1,
            "productId2": product_id2,
            "coPurchaseCount": 0,
            "coViewCount": 0,
            "coCartCount": 0,
            "supportScore": 0.0,
            "liftScore": 0.0,
            "lastCoOccurrence": None,
            "lastComputedAt": now_utc(),
        }
