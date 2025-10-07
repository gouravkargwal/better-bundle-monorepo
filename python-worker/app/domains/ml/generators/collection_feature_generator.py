"""
Optimized Collection Feature Generator for State-of-the-Art Gorse Integration
Focuses on collection-level signals that actually improve recommendation quality
"""

from typing import Dict, Any, List, Optional
import statistics
from datetime import datetime, timedelta, timezone
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from app.shared.helpers import now_utc
from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CollectionFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art collection feature generator optimized for Gorse collaborative filtering"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, collection: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate optimized collection features for Gorse

        Args:
            collection: The collection data
            context: Additional context data (shop, products, behavioral_events, orders)

        Returns:
            Dictionary with minimal, high-signal collection features for Gorse
        """
        try:
            collection_id = collection.get("collection_id", "")
            logger.debug(
                f"Computing optimized collection features for: {collection_id}"
            )

            # Get data from context
            shop = context.get("shop", {})
            products = context.get("products", [])
            user_interactions = context.get("user_interactions", [])
            orders = context.get("order_data", [])

            # Core Gorse-optimized collection features
            features = {
                "shop_id": shop.get("id", ""),
                "collection_id": collection_id,
                # === CORE COLLECTION SIGNALS ===
                # These are the most predictive for collection-based recommendations
                "collection_engagement_score": self._compute_collection_engagement_score(
                    collection_id, user_interactions
                ),
                "collection_conversion_rate": self._compute_collection_conversion_rate(
                    collection_id, user_interactions, orders
                ),
                "collection_popularity_score": self._compute_collection_popularity_score(
                    collection_id, user_interactions, orders
                ),
                # === COMMERCIAL VIABILITY ===
                # High-level patterns Gorse can use for business value optimization
                "avg_product_value": self._compute_avg_product_value(
                    collection, products
                ),
                "collection_revenue_potential": self._compute_collection_revenue_potential(
                    collection_id, orders, products
                ),
                # === CONTENT SIGNALS ===
                # Collection characteristics for content-based filtering
                "product_diversity_score": self._compute_product_diversity_score(
                    collection, products
                ),
                "collection_size_tier": self._compute_collection_size_tier(collection),
                # === TEMPORAL SIGNALS ===
                # Recent collection performance is most predictive
                "days_since_last_interaction": self._compute_days_since_last_interaction(
                    collection_id, user_interactions
                ),
                "collection_recency_score": self._compute_collection_recency_score(
                    collection_id, user_interactions, orders
                ),
                # === AUTOMATED COLLECTION INDICATOR ===
                # Important for recommendation strategy
                "is_curated_collection": not collection.get("is_automated", False),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized collection features: {str(e)}")
            return self._get_minimal_default_features(collection, context)

    def _compute_collection_engagement_score(
        self, collection_id: str, user_interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute normalized engagement score for collection (0-1)"""
        if not user_interactions:
            return 0.0

        # Filter interactions for this collection (last 30 days)
        thirty_days_ago = now_utc() - timedelta(days=30)
        collection_interactions = []

        for interaction in user_interactions:
            interaction_time = self._parse_datetime(interaction.get("timestamp"))
            if not interaction_time or interaction_time < thirty_days_ago:
                continue

            # Check if interaction is related to this collection
            metadata = interaction.get("metadata", {})

            # Handle different ways collection ID might be stored
            if (
                metadata.get("collection_id") == collection_id
                or collection_id in metadata.get("collection_ids", [])
                or interaction.get("interactionType") == "collection_viewed"
                and self._extract_collection_id_from_interaction(interaction)
                == collection_id
            ):
                collection_interactions.append(interaction)

        if not collection_interactions:
            return 0.0

        # Weight different interaction types
        engagement_points = 0.0
        for interaction in collection_interactions:
            interaction_type = interaction.get("interactionType", "")

            if interaction_type == "collection_viewed":
                engagement_points += 1.0
            elif interaction_type == "product_viewed":  # Product viewed from collection
                engagement_points += 1.5
            elif (
                interaction_type == "product_added_to_cart"
            ):  # Cart add from collection
                engagement_points += 3.0
            elif interaction_type == "checkout_completed":  # Purchase from collection
                engagement_points += 5.0

        # Normalize engagement score (20+ engagement points = max score)
        engagement_score = min(engagement_points / 20.0, 1.0)
        return round(engagement_score, 3)

    def _compute_collection_conversion_rate(
        self,
        collection_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Compute conversion rate from collection views to purchases"""
        collection_views = 0
        collection_purchases = 0

        # Count collection views
        for interaction in user_interactions:
            if (
                interaction.get("interactionType") == "collection_viewed"
                and self._extract_collection_id_from_interaction(interaction)
                == collection_id
            ):
                collection_views += 1

        if collection_views == 0:
            return 0.0

        # Count purchases that followed collection views (simplified approach)
        # In a real implementation, you'd track the customer journey more precisely
        collection_products = self._get_collection_product_ids(collection_id, orders)

        for order in orders:
            line_items = order.get("lineItems", [])
            order_product_ids = {item.get("product_id") for item in line_items}

            # If order contains products from this collection, count as conversion
            if collection_products & order_product_ids:
                collection_purchases += 1

        conversion_rate = collection_purchases / collection_views
        return round(min(1.0, conversion_rate), 3)

    def _compute_collection_popularity_score(
        self,
        collection_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Compute overall popularity score combining views and purchases"""
        engagement_score = self._compute_collection_engagement_score(
            collection_id, user_interactions
        )

        # Count unique users who interacted with collection
        unique_users = set()
        for interaction in user_interactions:
            if (
                self._extract_collection_id_from_interaction(interaction)
                == collection_id
            ):
                customer_id = interaction.get("customer_id")
                if customer_id:
                    unique_users.add(customer_id)

        # Normalize unique users (10+ users = good popularity)
        user_diversity_score = min(len(unique_users) / 10.0, 1.0)

        # Combine engagement and user diversity
        popularity_score = (engagement_score * 0.7) + (user_diversity_score * 0.3)
        return round(popularity_score, 3)

    def _compute_avg_product_value(
        self, collection: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Compute average product value in collection - price tier signal"""
        collection_products = collection.get("products", [])

        if not collection_products:
            return None

        prices = []
        for product in collection_products:
            price_range = product.get("price_range", {})
            if isinstance(price_range, dict):
                min_price = price_range.get("minVariantPrice", {})
                max_price = price_range.get("maxVariantPrice", {})

                if isinstance(min_price, dict) and isinstance(max_price, dict):
                    try:
                        min_amount = float(min_price.get("amount", 0))
                        max_amount = float(max_price.get("amount", 0))
                        avg_price = (min_amount + max_amount) / 2
                        if avg_price > 0:
                            prices.append(avg_price)
                    except (ValueError, TypeError):
                        continue

        if not prices:
            return None

        return round(statistics.mean(prices), 2)

    def _compute_collection_revenue_potential(
        self,
        collection_id: str,
        orders: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
    ) -> float:
        """Compute revenue potential score for collection"""
        collection_products = self._get_collection_product_ids(collection_id, orders)
        collection_revenue = 0.0

        # Calculate revenue from collection products
        for order in orders:
            line_items = order.get("lineItems", [])
            for item in line_items:
                product_id = item.get("product_id")
                if product_id in collection_products:
                    quantity = item.get("quantity", 1)
                    price = float(item.get("price", 0))
                    collection_revenue += price * quantity

        # Normalize revenue potential (1000+ revenue = high potential)
        revenue_potential = min(collection_revenue / 1000.0, 1.0)
        return round(revenue_potential, 3)

    def _compute_product_diversity_score(
        self, collection: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> float:
        """Compute product diversity within collection"""
        collection_products = collection.get("products", [])

        if not collection_products:
            return 0.0

        # Count unique vendors and product types
        vendors = set()
        product_types = set()

        for product in collection_products:
            vendor = product.get("vendor")
            if vendor:
                vendors.add(vendor)

            product_type = product.get("productType")
            if product_type:
                product_types.add(product_type)

        # Normalize diversity (5+ vendors or types = high diversity)
        vendor_diversity = min(len(vendors) / 5.0, 1.0)
        type_diversity = min(len(product_types) / 5.0, 1.0)

        diversity_score = (vendor_diversity + type_diversity) / 2.0
        return round(diversity_score, 3)

    def _compute_collection_size_tier(self, collection: Dict[str, Any]) -> str:
        """Categorize collection by size - important for recommendation strategy"""
        product_count = collection.get("product_count", 0)

        if product_count >= 50:
            return "large"
        elif product_count >= 20:
            return "medium"
        elif product_count >= 5:
            return "small"
        else:
            return "minimal"

    def _compute_days_since_last_interaction(
        self, collection_id: str, user_interactions: List[Dict[str, Any]]
    ) -> Optional[int]:
        """Compute days since last collection interaction"""
        last_interaction_time = None

        for interaction in user_interactions:
            if (
                self._extract_collection_id_from_interaction(interaction)
                == collection_id
            ):
                interaction_time = self._parse_datetime(interaction.get("timestamp"))
                if interaction_time:
                    if (
                        not last_interaction_time
                        or interaction_time > last_interaction_time
                    ):
                        last_interaction_time = interaction_time

        if not last_interaction_time:
            return None

        return (now_utc() - last_interaction_time).days

    def _compute_collection_recency_score(
        self,
        collection_id: str,
        user_interactions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Compute recency score for collection activity (0-1)"""
        days_since_last = self._compute_days_since_last_interaction(
            collection_id, user_interactions
        )

        if days_since_last is None:
            return 0.0

        # Exponential decay: 1.0 for today, 0.5 for 14 days ago, 0.1 for 60 days ago
        recency_score = max(0.0, 1.0 - (days_since_last / 60.0))
        return round(recency_score, 3)

    # Helper methods
    def _extract_collection_id_from_interaction(
        self, interaction: Dict[str, Any]
    ) -> Optional[str]:
        """Extract collection ID from interaction"""
        metadata = interaction.get("metadata", {})

        # Try different possible locations for collection ID
        collection_id = (
            metadata.get("collection_id")
            or metadata.get("collectionId")
            or metadata.get("collection", {}).get("id")
        )

        return collection_id

    def _get_collection_product_ids(
        self, collection_id: str, orders: List[Dict[str, Any]]
    ) -> set:
        """Get set of product IDs that belong to this collection"""
        # This would typically come from your collection-product mapping
        # For now, returning empty set as placeholder
        return set()

    def _parse_datetime(self, datetime_str: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not datetime_str:
            return None

        if isinstance(datetime_str, datetime):
            return datetime_str

        if isinstance(datetime_str, str):
            try:
                return parse_iso_timestamp(datetime_str)
            except:
                return None

        return None

    def _get_minimal_default_features(
        self, collection: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": context.get("shop", {}).get("id", ""),
            "collection_id": collection.get("collection_id", ""),
            "collection_engagement_score": 0.0,
            "collection_conversion_rate": 0.0,
            "collection_popularity_score": 0.0,
            "avg_product_value": None,
            "collection_revenue_potential": 0.0,
            "product_diversity_score": 0.0,
            "collection_size_tier": "minimal",
            "days_since_last_interaction": None,
            "collection_recency_score": 0.0,
            "is_curated_collection": True,
            "last_computed_at": now_utc(),
        }
