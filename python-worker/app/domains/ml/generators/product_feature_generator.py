"""
Optimized Product Feature Generator for State-of-the-Art Gorse Integration
Focuses on product-level signals that actually improve recommendation quality
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
    """State-of-the-art product feature generator optimized for Gorse collaborative filtering"""

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
        Generate optimized product features for Gorse

        Args:
            shop_id: The shop ID
            product_id: The product ID
            context: Contains product_data, orders, behavioral_events
            product_id_mapping: Mapping between different product ID formats

        Returns:
            Dictionary with minimal, high-signal product features for Gorse
        """
        try:
            logger.debug(f"Computing optimized product features for: {product_id}")

            # Get data from context
            product_data = context.get("product_data", {})
            orders = context.get("orders", [])
            user_interactions = context.get("user_interactions", [])

            # Core Gorse-optimized product features
            features = {
                "shop_id": shop_id,
                "product_id": product_id,
                # === CORE ENGAGEMENT SIGNALS ===
                # These are the most predictive for collaborative filtering
                "interaction_volume_score": self._compute_interaction_volume_score(
                    product_id, user_interactions, product_id_mapping
                ),
                "purchase_velocity_score": self._compute_purchase_velocity_score(
                    product_id, orders, product_id_mapping
                ),
                "engagement_quality_score": self._compute_engagement_quality_score(
                    product_id, user_interactions, orders, product_id_mapping
                ),
                # === COMMERCIAL SIGNALS ===
                # High-level patterns Gorse can use for business value optimization
                "price_tier": self._compute_price_tier(
                    product_data, orders, product_id
                ),
                "revenue_potential_score": self._compute_revenue_potential_score(
                    product_id, orders, product_id_mapping
                ),
                "conversion_efficiency": self._compute_conversion_efficiency(
                    product_id, user_interactions, orders, product_id_mapping
                ),
                # === TEMPORAL SIGNALS ===
                # Recent activity is most predictive for recommendations
                "days_since_last_purchase": self._compute_days_since_last_purchase(
                    product_id, orders, product_id_mapping
                ),
                "activity_recency_score": self._compute_activity_recency_score(
                    product_id, user_interactions, orders, product_id_mapping
                ),
                "trending_momentum": self._compute_trending_momentum(
                    product_id, user_interactions, orders, product_id_mapping
                ),
                # === PRODUCT LIFECYCLE ===
                # Critical for understanding product stage and recommendation strategy
                "product_lifecycle_stage": self._compute_product_lifecycle_stage(
                    product_id, orders, user_interactions, product_id_mapping
                ),
                "inventory_health_score": self._compute_inventory_health_score(
                    product_data, orders, product_id
                ),
                # === CATEGORY CONTEXT ===
                # For content-based filtering support
                "product_category": self._extract_product_category(product_data),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized product features: {str(e)}")
            return self._get_minimal_default_features(shop_id, product_id)

    def _compute_interaction_volume_score(
        self,
        product_id: str,
        user_interactions: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute normalized interaction volume (0-1) - core engagement signal"""
        thirty_days_ago = now_utc() - timedelta(days=30)

        # Count recent interactions
        interaction_count = 0
        unique_users = set()

        for interaction in user_interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if not interaction_time or interaction_time < thirty_days_ago:
                continue

            event_product_id = self.adapter_factory.extract_product_id(interaction)
            mapped_product_id = self._map_product_id(
                event_product_id, product_id_mapping
            )

            if mapped_product_id == product_id:
                interaction_count += 1
                customer_id = interaction.get("customer_id")
                if customer_id:
                    unique_users.add(customer_id)

        # Combine volume and user diversity
        volume_score = min(
            interaction_count / 50.0, 1.0
        )  # 50+ interactions = max score
        diversity_score = min(len(unique_users) / 20.0, 1.0)  # 20+ users = max score

        interaction_volume = (volume_score * 0.7) + (diversity_score * 0.3)
        return round(interaction_volume, 3)

    def _compute_purchase_velocity_score(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute purchase velocity (purchases per week) - key commercial signal"""
        thirty_days_ago = now_utc() - timedelta(days=30)

        purchase_count = 0
        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if not order_date or order_date < thirty_days_ago:
                continue

            # Check if order contains this product
            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    purchase_count += 1
                    break

        # Convert to weekly velocity and normalize
        weekly_velocity = (purchase_count * 7) / 30  # purchases per week
        velocity_score = min(weekly_velocity / 5.0, 1.0)  # 5+ per week = max score

        return round(velocity_score, 3)

    def _compute_engagement_quality_score(
        self,
        product_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute engagement quality based on interaction types and conversion"""
        thirty_days_ago = now_utc() - timedelta(days=30)

        # Weight different interaction types
        engagement_points = 0.0
        total_interactions = 0

        for interaction in user_interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if not interaction_time or interaction_time < thirty_days_ago:
                continue

            event_product_id = self.adapter_factory.extract_product_id(interaction)
            mapped_product_id = self._map_product_id(
                event_product_id, product_id_mapping
            )

            if mapped_product_id == product_id:
                total_interactions += 1
                interaction_type = interaction.get("interactionType", "")

                if interaction_type == "product_viewed":
                    engagement_points += 1.0
                elif interaction_type == "product_added_to_cart":
                    engagement_points += 3.0
                elif interaction_type == "checkout_started":
                    engagement_points += 4.0
                elif interaction_type == "checkout_completed":
                    engagement_points += 5.0

        if total_interactions == 0:
            return 0.0

        # Calculate average engagement quality
        avg_engagement_quality = engagement_points / total_interactions
        quality_score = min(avg_engagement_quality / 3.0, 1.0)  # Normalize to 0-1

        return round(quality_score, 3)

    def _compute_price_tier(
        self,
        product_data: Dict[str, Any],
        orders: List[Dict[str, Any]],
        product_id: str,
    ) -> str:
        """Compute price tier - important for user segmentation"""
        # Try to get actual selling price from recent orders
        recent_prices = []
        thirty_days_ago = now_utc() - timedelta(days=30)

        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if not order_date or order_date < thirty_days_ago:
                continue

            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                if item_product_id == product_id:
                    price = float(line_item.get("price", 0.0))
                    if price > 0:
                        recent_prices.append(price)

        # Use average recent price or fallback to product data
        if recent_prices:
            avg_price = statistics.mean(recent_prices)
        else:
            avg_price = float(product_data.get("price", 0.0))

        # Categorize price tier
        if avg_price < 25:
            return "budget"
        elif avg_price < 75:
            return "mid"
        elif avg_price < 200:
            return "premium"
        else:
            return "luxury"

    def _compute_revenue_potential_score(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute revenue potential based on recent performance"""
        thirty_days_ago = now_utc() - timedelta(days=30)
        total_revenue = 0.0

        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if not order_date or order_date < thirty_days_ago:
                continue

            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    price = float(line_item.get("price", 0.0))
                    quantity = int(line_item.get("quantity", 1))
                    total_revenue += price * quantity

        # Normalize revenue potential (500+ = high potential)
        revenue_potential = min(total_revenue / 500.0, 1.0)
        return round(revenue_potential, 3)

    def _compute_conversion_efficiency(
        self,
        product_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute conversion efficiency (purchases / views)"""
        thirty_days_ago = now_utc() - timedelta(days=30)

        view_count = 0
        purchase_count = 0

        # Count views
        for interaction in user_interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if not interaction_time or interaction_time < thirty_days_ago:
                continue

            if interaction.get("interactionType") == "product_viewed":
                event_product_id = self.adapter_factory.extract_product_id(interaction)
                mapped_product_id = self._map_product_id(
                    event_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    view_count += 1

        # Count purchases
        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if not order_date or order_date < thirty_days_ago:
                continue

            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    purchase_count += 1
                    break

        if view_count == 0:
            return 0.0

        conversion_rate = purchase_count / view_count
        return round(min(conversion_rate, 1.0), 3)

    def _compute_days_since_last_purchase(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> Optional[int]:
        """Compute days since last purchase - key recency signal"""
        last_purchase_date = None

        for order in orders:
            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    order_date = self._parse_date(order.get("order_date"))
                    if order_date:
                        if not last_purchase_date or order_date > last_purchase_date:
                            last_purchase_date = order_date
                    break

        if not last_purchase_date:
            return None

        return (now_utc() - last_purchase_date).days

    def _compute_activity_recency_score(
        self,
        product_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute combined activity recency score"""
        days_since_purchase = self._compute_days_since_last_purchase(
            product_id, orders, product_id_mapping
        )

        # Find last interaction
        last_interaction_date = None
        for interaction in user_interactions:
            event_product_id = self.adapter_factory.extract_product_id(interaction)
            mapped_product_id = self._map_product_id(
                event_product_id, product_id_mapping
            )

            if mapped_product_id == product_id:
                interaction_time = self._parse_date(interaction.get("timestamp"))
                if interaction_time:
                    if (
                        not last_interaction_date
                        or interaction_time > last_interaction_date
                    ):
                        last_interaction_date = interaction_time

        days_since_interaction = None
        if last_interaction_date:
            days_since_interaction = (now_utc() - last_interaction_date).days

        # Calculate combined recency score
        recency_scores = []

        if days_since_purchase is not None:
            purchase_recency = max(0.0, 1.0 - (days_since_purchase / 60.0))
            recency_scores.append(purchase_recency)

        if days_since_interaction is not None:
            interaction_recency = max(0.0, 1.0 - (days_since_interaction / 30.0))
            recency_scores.append(interaction_recency)

        if not recency_scores:
            return 0.0

        avg_recency = sum(recency_scores) / len(recency_scores)
        return round(avg_recency, 3)

    def _compute_trending_momentum(
        self,
        product_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> float:
        """Compute trending momentum (recent activity vs historical)"""
        now = now_utc()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        recent_activity = 0
        historical_activity = 0

        # Count interactions in different time windows
        for interaction in user_interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if not interaction_time:
                continue

            event_product_id = self.adapter_factory.extract_product_id(interaction)
            mapped_product_id = self._map_product_id(
                event_product_id, product_id_mapping
            )

            if mapped_product_id == product_id:
                if interaction_time >= seven_days_ago:
                    recent_activity += 1
                elif interaction_time >= thirty_days_ago:
                    historical_activity += 1

        # Count orders in different time windows
        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if not order_date:
                continue

            for line_item in order.get("line_items", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    if order_date >= seven_days_ago:
                        recent_activity += 2  # Weight purchases more
                    elif order_date >= thirty_days_ago:
                        historical_activity += 2
                    break

        # Calculate momentum (recent vs historical activity)
        if historical_activity == 0:
            return 1.0 if recent_activity > 0 else 0.0

        # Adjust for time period difference (7 days vs 23 days)
        historical_daily_avg = historical_activity / 23.0
        recent_daily_avg = recent_activity / 7.0

        if historical_daily_avg == 0:
            return 1.0 if recent_daily_avg > 0 else 0.0

        momentum = min(recent_daily_avg / historical_daily_avg, 2.0)  # Cap at 2x
        return round(momentum / 2.0, 3)  # Normalize to 0-1

    def _compute_product_lifecycle_stage(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> str:
        """Determine product lifecycle stage - critical for recommendation strategy"""
        thirty_days_ago = now_utc() - timedelta(days=30)

        recent_purchases = 0
        recent_interactions = 0

        # Count recent activity
        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if order_date and order_date >= thirty_days_ago:
                for line_item in order.get("line_items", []):
                    item_product_id = self._extract_product_id_from_line_item(line_item)
                    mapped_product_id = self._map_product_id(
                        item_product_id, product_id_mapping
                    )

                    if mapped_product_id == product_id:
                        recent_purchases += 1
                        break

        for interaction in user_interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if interaction_time and interaction_time >= thirty_days_ago:
                event_product_id = self.adapter_factory.extract_product_id(interaction)
                mapped_product_id = self._map_product_id(
                    event_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    recent_interactions += 1

        # Classify lifecycle stage
        if recent_purchases >= 10 or recent_interactions >= 50:
            return "growth"
        elif recent_purchases >= 3 or recent_interactions >= 15:
            return "mature"
        elif recent_purchases >= 1 or recent_interactions >= 5:
            return "emerging"
        else:
            return "dormant"

    def _compute_inventory_health_score(
        self,
        product_data: Dict[str, Any],
        orders: List[Dict[str, Any]],
        product_id: str,
    ) -> float:
        """Compute inventory health score"""
        total_inventory = int(product_data.get("total_inventory", 0))

        if total_inventory <= 0:
            return 0.0  # Out of stock

        # Calculate recent sales velocity
        thirty_days_ago = now_utc() - timedelta(days=30)
        units_sold = 0

        for order in orders:
            order_date = self._parse_date(order.get("order_date"))
            if order_date and order_date >= thirty_days_ago:
                for line_item in order.get("line_items", []):
                    item_product_id = self._extract_product_id_from_line_item(line_item)
                    if item_product_id == product_id:
                        units_sold += int(line_item.get("quantity", 1))

        if units_sold == 0:
            return 1.0  # No sales, so inventory is "healthy" but not moving

        # Calculate months of inventory remaining
        monthly_velocity = (units_sold * 30) / 30  # Units per month
        months_remaining = total_inventory / max(monthly_velocity, 1)

        # Optimal range is 1-3 months of inventory
        if 1 <= months_remaining <= 3:
            return 1.0
        elif months_remaining < 1:
            return max(0.3, months_remaining)  # Low stock warning
        else:
            return max(0.5, 1.0 - (months_remaining - 3) / 12)  # Excess inventory

    def _extract_product_category(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract product category for content-based filtering"""
        return product_data.get("productType") or product_data.get("category")

    # Helper methods
    def _map_product_id(
        self,
        event_product_id: Optional[str],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> Optional[str]:
        """Map event product ID to standard product ID"""
        if not event_product_id:
            return None

        if product_id_mapping:
            return product_id_mapping.get(event_product_id, event_product_id)

        return event_product_id

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        if "product_id" in line_item:
            return str(line_item["product_id"])

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            if isinstance(product, dict):
                return product.get("id", "")

        return ""

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

    def _get_minimal_default_features(
        self, shop_id: str, product_id: str
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": shop_id,
            "product_id": product_id,
            "interaction_volume_score": 0.0,
            "purchase_velocity_score": 0.0,
            "engagement_quality_score": 0.0,
            "price_tier": "mid",
            "revenue_potential_score": 0.0,
            "conversion_efficiency": 0.0,
            "days_since_last_purchase": None,
            "activity_recency_score": 0.0,
            "trending_momentum": 0.0,
            "product_lifecycle_stage": "dormant",
            "inventory_health_score": 0.0,
            "product_category": None,
            "last_computed_at": now_utc(),
        }
