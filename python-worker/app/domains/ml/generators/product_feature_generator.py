"""
Product Feature Generator for Gorse integration
Computes features from products, orders, and behavioral events
"""

import datetime
from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for product features"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self,
        shop_id: str,
        product_id: str,
        context: Dict[str, Any],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate product features

        Args:
            shop_id: The shop ID
            product_id: The product ID
            context: Contains product_data, orders, behavioral_events, collections

        Returns:
            Dictionary matching ProductFeatures table schema
        """
        try:
            logger.debug(
                f"Computing product features for shop: {shop_id}, product: {product_id}"
            )

            # Get data from context
            product_data = context.get("product_data", {})
            orders = context.get("orders", [])
            behavioral_events = context.get("behavioral_events", [])

            # Compute 30-day metrics
            metrics_30d = self._compute_30day_metrics(
                product_id, orders, behavioral_events, product_id_mapping
            )

            # Compute conversion metrics
            conversion_metrics = self._compute_conversion_metrics(metrics_30d)

            # Compute temporal metrics
            temporal_metrics = self._compute_temporal_metrics(
                product_id, orders, behavioral_events, product_id_mapping
            )

            # Compute price and inventory metrics
            price_inventory_metrics = self._compute_price_inventory_metrics(
                product_data, orders
            )
            # Compute popularity and trending scores
            popularity_trending = self._compute_popularity_trending_scores(
                metrics_30d, temporal_metrics
            )

            # Compute refund metrics (NEW)
            refund_metrics = self._compute_refund_metrics(
                product_id, orders, product_id_mapping
            )

            features = {
                "shop_id": shop_id,
                "product_id": product_id,
                # 30-day metrics
                "view_count_30d": metrics_30d["view_count"],
                "unique_viewers_30d": metrics_30d["unique_viewers"],
                "cart_add_count_30d": metrics_30d["cart_add_count"],
                "cart_view_count_30d": metrics_30d["cart_view_count"],
                "cart_remove_count_30d": metrics_30d["cart_remove_count"],
                "purchase_count_30d": metrics_30d["purchase_count"],
                "unique_purchasers_30d": metrics_30d["unique_purchasers"],
                # Conversion metrics
                "view_to_cart_rate": conversion_metrics["view_to_cart_rate"],
                "cart_to_purchase_rate": conversion_metrics["cart_to_purchase_rate"],
                "overall_conversion_rate": conversion_metrics[
                    "overall_conversion_rate"
                ],
                "cart_abandonment_rate": conversion_metrics["cart_abandonment_rate"],
                "cart_modification_rate": conversion_metrics["cart_modification_rate"],
                "cart_view_to_purchase_rate": conversion_metrics[
                    "cart_view_to_purchase_rate"
                ],
                # Temporal metrics
                "last_viewed_at": temporal_metrics["last_viewed_at"],
                "last_purchased_at": temporal_metrics["last_purchased_at"],
                "first_purchased_at": temporal_metrics["first_purchased_at"],
                "days_since_first_purchase": temporal_metrics[
                    "days_since_first_purchase"
                ],
                "days_since_last_purchase": temporal_metrics[
                    "days_since_last_purchase"
                ],
                # Price & Inventory
                "avg_selling_price": price_inventory_metrics["avg_selling_price"],
                "price_variance": price_inventory_metrics["price_variance"],
                "total_inventory": price_inventory_metrics["total_inventory"],
                "inventory_turnover": price_inventory_metrics["inventory_turnover"],
                "stock_velocity": price_inventory_metrics["stock_velocity"],
                "price_tier": price_inventory_metrics["price_tier"],
                # Computed scores
                "popularity_score": popularity_trending["popularity_score"],
                "trending_score": popularity_trending["trending_score"],
                # Refund metrics (NEW)
                "refund_rate": refund_metrics["refund_rate"],
                "net_revenue": refund_metrics["net_revenue"],
                "last_computed_at": now_utc(),
            }

            logger.debug(
                f"Computed product features for product: {product_id} - "
                f"Views: {features['view_count_30d']}, Purchases: {features['purchase_count_30d']}"
            )

            return features

        except Exception as e:
            logger.error(f"Failed to compute product features: {str(e)}")
            return self._get_default_features(shop_id, product_id)

    def _compute_30day_metrics(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        behavioral_events: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Compute 30-day window metrics"""

        now = now_utc()
        thirty_days_ago = now - timedelta(days=30)

        # Filter events in 30-day window
        recent_events = []
        for event in behavioral_events:
            event_time = self._parse_date(event.get("timestamp"))
            if event_time and event_time >= thirty_days_ago:
                event_product_id = self._extract_product_id_from_event(event)
                # Use product ID mapping to match behavioral event product ID to ProductData product ID
                if product_id_mapping and event_product_id:
                    mapped_product_id = product_id_mapping.get(event_product_id)
                    if mapped_product_id == product_id:
                        recent_events.append(event)
                elif event_product_id == product_id:
                    recent_events.append(event)

        # Count views and unique viewers
        view_count = 0
        unique_viewers = set()
        cart_add_count = 0
        cart_view_count = 0
        cart_remove_count = 0

        for event in recent_events:
            event_type = event.get("interactionType", event.get("eventType", ""))

            if event_type == "product_viewed":
                view_count += 1
                customer_id = event.get("customerId")
                if customer_id:
                    unique_viewers.add(customer_id)
                else:
                    # Use session ID for anonymous users
                    session_id = self._extract_session_id(event)
                    if session_id:
                        unique_viewers.add(f"session_{session_id}")

            elif event_type == "product_added_to_cart":
                cart_add_count += 1

            elif event_type == "cart_viewed":
                cart_view_count += 1

            elif event_type == "product_removed_from_cart":
                cart_remove_count += 1

        # Filter orders in 30-day window
        recent_orders = []
        unique_purchasers = set()

        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if order_date and order_date >= thirty_days_ago:
                # Check if this order contains the product
                for line_item in order.get("line_items", []):
                    item_product_id = self._extract_product_id_from_line_item(line_item)
                    # Use product ID mapping to match order product ID to ProductData product ID
                    if product_id_mapping and item_product_id:
                        mapped_product_id = product_id_mapping.get(item_product_id)
                        if mapped_product_id == product_id:
                            recent_orders.append(order)
                            customer_id = order.get("customer_id")
                            if customer_id:
                                unique_purchasers.add(customer_id)
                            break
                    elif item_product_id == product_id:
                        recent_orders.append(order)
                        customer_id = order.get("customer_id")
                        if customer_id:
                            unique_purchasers.add(customer_id)
                        break

        return {
            "view_count": view_count,
            "unique_viewers": len(unique_viewers),
            "cart_add_count": cart_add_count,
            "cart_view_count": cart_view_count,
            "cart_remove_count": cart_remove_count,
            "purchase_count": len(recent_orders),
            "unique_purchasers": len(unique_purchasers),
        }

    def _compute_conversion_metrics(
        self, metrics_30d: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute conversion rates from 30-day metrics"""

        view_count = metrics_30d["view_count"]
        cart_add_count = metrics_30d["cart_add_count"]
        cart_view_count = metrics_30d["cart_view_count"]
        cart_remove_count = metrics_30d["cart_remove_count"]
        purchase_count = metrics_30d["purchase_count"]

        view_to_cart_rate = (
            cart_add_count / max(view_count, 1) if view_count > 0 else 0.0
        )
        cart_to_purchase_rate = (
            purchase_count / max(cart_add_count, 1) if cart_add_count > 0 else 0.0
        )
        overall_conversion_rate = (
            purchase_count / max(view_count, 1) if view_count > 0 else 0.0
        )

        # New cart-specific metrics
        cart_abandonment_rate = (
            (cart_add_count - purchase_count) / max(cart_add_count, 1)
            if cart_add_count > 0
            else 0.0
        )
        cart_modification_rate = (
            cart_remove_count / max(cart_add_count, 1) if cart_add_count > 0 else 0.0
        )
        cart_view_to_purchase_rate = (
            purchase_count / max(cart_view_count, 1) if cart_view_count > 0 else 0.0
        )

        return {
            "view_to_cart_rate": round(view_to_cart_rate, 4),
            "cart_to_purchase_rate": round(cart_to_purchase_rate, 4),
            "overall_conversion_rate": round(overall_conversion_rate, 4),
            "cart_abandonment_rate": round(cart_abandonment_rate, 4),
            "cart_modification_rate": round(cart_modification_rate, 4),
            "cart_view_to_purchase_rate": round(cart_view_to_purchase_rate, 4),
        }

    def _compute_temporal_metrics(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        behavioral_events: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Compute temporal metrics"""

        # Find last view
        last_viewed_at = None
        for event in behavioral_events:
            if (
                event.get("interactionType", event.get("eventType", ""))
                == "product_viewed"
            ):
                event_product_id = self._extract_product_id_from_event(event)
                # Use product ID mapping to match behavioral event product ID to ProductData product ID
                if product_id_mapping and event_product_id:
                    mapped_product_id = product_id_mapping.get(event_product_id)
                    if mapped_product_id == product_id:
                        event_time = self._parse_date(event.get("timestamp"))
                        if event_time:
                            if not last_viewed_at or event_time > last_viewed_at:
                                last_viewed_at = event_time
                elif event_product_id == product_id:
                    event_time = self._parse_date(event.get("timestamp"))
                    if event_time:
                        if not last_viewed_at or event_time > last_viewed_at:
                            last_viewed_at = event_time

        # Find first and last purchase
        first_purchased_at = None
        last_purchased_at = None

        for order in orders:
            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                # Use product ID mapping to match order product ID to ProductData product ID
                if product_id_mapping and item_product_id:
                    mapped_product_id = product_id_mapping.get(item_product_id)
                    if mapped_product_id == product_id:
                        order_date = self._parse_date(order.get("order_date"))
                        if order_date:
                            if (
                                not first_purchased_at
                                or order_date < first_purchased_at
                            ):
                                first_purchased_at = order_date
                            if not last_purchased_at or order_date > last_purchased_at:
                                last_purchased_at = order_date
                        break
                elif item_product_id == product_id:
                    order_date = self._parse_date(order.get("order_date"))
                    if order_date:
                        if not first_purchased_at or order_date < first_purchased_at:
                            first_purchased_at = order_date
                        if not last_purchased_at or order_date > last_purchased_at:
                            last_purchased_at = order_date
                    break

        # Calculate days since
        days_since_first_purchase = None
        days_since_last_purchase = None

        if first_purchased_at:
            days_since_first_purchase = (now_utc() - first_purchased_at).days

        if last_purchased_at:
            days_since_last_purchase = (now_utc() - last_purchased_at).days

        return {
            "last_viewed_at": last_viewed_at,
            "last_purchased_at": last_purchased_at,
            "first_purchased_at": first_purchased_at,
            "days_since_first_purchase": days_since_first_purchase,
            "days_since_last_purchase": days_since_last_purchase,
        }

    def _compute_price_inventory_metrics(
        self, product_data: Dict[str, Any], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute price and inventory metrics"""

        # Get actual selling prices from orders
        selling_prices = []
        total_quantity_sold = 0

        for order in orders:
            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                if item_product_id == product_data.get("product_id"):
                    price = float(line_item.get("price", 0.0))
                    quantity = int(line_item.get("quantity", 1))
                    selling_prices.extend([price] * quantity)
                    total_quantity_sold += quantity

        # Calculate price metrics
        if selling_prices:
            avg_selling_price = statistics.mean(selling_prices)
            price_variance = (
                statistics.variance(selling_prices) if len(selling_prices) > 1 else 0.0
            )
        else:
            # Use product data price as fallback
            avg_selling_price = float(product_data.get("price", 0.0))
            price_variance = 0.0

        # Calculate inventory turnover
        total_inventory = int(product_data.get("total_inventory", 0))
        if total_inventory > 0 and total_quantity_sold > 0:
            # Simplified: assuming data covers 30 days
            inventory_turnover = total_quantity_sold / total_inventory
            stock_velocity = total_quantity_sold / 30.0  # Units per day
        else:
            inventory_turnover = 0.0
            stock_velocity = 0.0

        # Determine price tier
        price_tier = self._calculate_price_tier(avg_selling_price)

        return {
            "avg_selling_price": round(avg_selling_price, 2),
            "price_variance": round(price_variance, 2),
            "total_inventory": total_inventory,  # Include totalInventory from ProductData
            "inventory_turnover": round(inventory_turnover, 4),
            "stock_velocity": round(stock_velocity, 2),
            "price_tier": price_tier,
        }

    def _compute_popularity_trending_scores(
        self, metrics_30d: Dict[str, Any], temporal_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute popularity and trending scores"""

        # Popularity score based on views and purchases
        view_score = min(metrics_30d["view_count"] / 100.0, 1.0)  # Normalize
        purchase_score = min(metrics_30d["purchase_count"] / 10.0, 1.0)  # Normalize

        # Weighted combination
        popularity_score = (view_score * 0.3) + (purchase_score * 0.7)

        # Trending score based on recency
        trending_score = 0.0

        if temporal_metrics["last_viewed_at"]:
            days_since_view = (now_utc() - temporal_metrics["last_viewed_at"]).days
            view_recency = max(0, 1 - (days_since_view / 7))  # Decay over 7 days
            trending_score += view_recency * 0.5

        if temporal_metrics["last_purchased_at"]:
            days_since_purchase = (
                now_utc() - temporal_metrics["last_purchased_at"]
            ).days
            purchase_recency = max(
                0, 1 - (days_since_purchase / 7)
            )  # Decay over 7 days
            trending_score += purchase_recency * 0.5

        return {
            "popularity_score": round(popularity_score, 3),
            "trending_score": round(trending_score, 3),
        }

    def _calculate_price_tier(self, price: float) -> str:
        """Calculate price tier"""
        if price < 25:
            return "budget"
        elif price < 75:
            return "mid"
        elif price < 200:
            return "premium"
        else:
            return "luxury"

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from behavioral event using adapter pattern"""
        return self.adapter_factory.extract_product_id(event)

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        if "product_id" in line_item:
            return str(line_item["product_id"])

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            if isinstance(product, dict):
                return product.get("id", "")

        return ""

    def _extract_session_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from event"""
        event_data = event.get("eventData", {})
        return event_data.get("client_id")

    def _parse_date(self, date_value: Any) -> Optional[datetime.datetime]:
        """Parse date from various formats"""
        if not date_value:
            return None

        if isinstance(date_value, datetime.datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                return datetime.datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
            except:
                return None

        return None

    def _get_default_features(self, shop_id: str, product_id: str) -> Dict[str, Any]:
        """Return default features when computation fails"""
        return {
            "shop_id": shop_id,
            "product_id": product_id,
            "view_count_30d": 0,
            "unique_viewers_30d": 0,
            "cart_add_count_30d": 0,
            "purchase_count_30d": 0,
            "unique_purchasers_30d": 0,
            "view_to_cart_rate": None,
            "cart_to_purchase_rate": None,
            "overall_conversion_rate": None,
            "last_viewed_at": None,
            "last_purchased_at": None,
            "first_purchased_at": None,
            "days_since_first_purchase": None,
            "days_since_last_purchase": None,
            "avg_selling_price": None,
            "price_variance": None,
            "total_inventory": None,
            "inventory_turnover": None,
            "stock_velocity": None,
            "price_tier": None,
            "popularity_score": 0.0,
            "trending_score": 0.0,
            "refund_rate": 0.0,
            "net_revenue": 0.0,
            "last_computed_at": now_utc(),
        }

    def _compute_refund_metrics(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Compute refund-related metrics for a product"""
        try:
            if not orders:
                return {
                    "refund_rate": 0.0,
                    "net_revenue": 0.0,
                }

            # Find orders containing this product
            product_orders = []
            total_revenue = 0.0
            total_refunded_amount = 0.0
            refunded_orders = 0

            for order in orders:
                line_items = order.get("line_items", [])
                order_contains_product = False
                order_revenue = 0.0

                for item in line_items:
                    # Extract product ID from line item
                    item_product_id = self._extract_product_id_from_line_item(item)

                    # Check if this item belongs to our target product
                    if product_id_mapping and item_product_id:
                        mapped_product_id = product_id_mapping.get(item_product_id)
                        if mapped_product_id == product_id:
                            order_contains_product = True
                            quantity = int(item.get("quantity", 1))
                            price = float(item.get("price", 0.0))
                            order_revenue += price * quantity
                    elif item_product_id == product_id:
                        order_contains_product = True
                        quantity = int(item.get("quantity", 1))
                        price = float(item.get("price", 0.0))
                        order_revenue += price * quantity

                if order_contains_product:
                    product_orders.append(order)
                    total_revenue += order_revenue

                    # Check if this order was refunded
                    financial_status = order.get("financial_status")
                    if financial_status == "refunded":
                        refunded_orders += 1
                        # Use totalRefundedAmount if available, otherwise use order_revenue
                        refunded_amount = float(
                            order.get("total_refunded_amount", order_revenue)
                        )
                        total_refunded_amount += refunded_amount

            # Calculate metrics
            total_orders = len(product_orders)
            refund_rate = refunded_orders / total_orders if total_orders > 0 else 0.0
            net_revenue = total_revenue - total_refunded_amount

            return {
                "refund_rate": round(refund_rate, 3),
                "net_revenue": round(net_revenue, 2),
            }

        except Exception as e:
            logger.error(f"Failed to compute refund metrics: {str(e)}")
            return {
                "refund_rate": 0.0,
                "net_revenue": 0.0,
            }
