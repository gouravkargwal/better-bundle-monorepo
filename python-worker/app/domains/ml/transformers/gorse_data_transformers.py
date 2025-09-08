"""
Data transformation utilities for Gorse pipeline
Handles label building and data conversion for users and items
"""

import json
import math
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseDataTransformers:
    """Data transformation utilities for Gorse synchronization"""

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def _build_comprehensive_user_labels(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build comprehensive Gorse user labels from all feature tables
        """
        try:
            labels = {
                # From UserFeatures
                "total_purchases": int(user.get("totalPurchases") or 0),
                "total_spent": float(user.get("totalSpent") or 0),
                "avg_order_value": float(user.get("avgOrderValue") or 0),
                "lifetime_value": float(user.get("lifetimeValue") or 0),
                "days_since_last_order": user.get("daysSinceLastOrder"),
                "order_frequency_per_month": float(
                    user.get("orderFrequencyPerMonth") or 0
                ),
                "distinct_products_purchased": int(
                    user.get("distinctProductsPurchased") or 0
                ),
                "distinct_categories_purchased": int(
                    user.get("distinctCategoriesPurchased") or 0
                ),
                "preferred_category": user.get("preferredCategory", "unknown"),
                "preferred_vendor": user.get("preferredVendor", "unknown"),
                "price_preference": user.get("pricePointPreference", "mid"),
                "discount_sensitivity": float(user.get("discountSensitivity") or 0),
                # From CustomerBehaviorFeatures
                "engagement_score": float(user.get("engagementScore") or 0),
                "recency_score": float(user.get("recencyScore") or 0),
                "diversity_score": float(user.get("diversityScore") or 0),
                "behavioral_score": float(user.get("behavioralScore") or 0),
                "session_count": int(user.get("sessionCount") or 0),
                "product_view_count": int(user.get("productViewCount") or 0),
                "cart_add_count": int(user.get("cartAddCount") or 0),
                "search_count": int(user.get("searchCount") or 0),
                "unique_products_viewed": int(user.get("uniqueProductsViewed") or 0),
                "unique_collections_viewed": int(
                    user.get("uniqueCollectionsViewed") or 0
                ),
                "browse_to_cart_rate": (
                    float(user.get("browseToCartRate", 0))
                    if user.get("browseToCartRate")
                    else 0
                ),
                "cart_to_purchase_rate": (
                    float(user.get("cartToPurchaseRate", 0))
                    if user.get("cartToPurchaseRate")
                    else 0
                ),
                "search_to_purchase_rate": (
                    float(user.get("searchToPurchaseRate", 0))
                    if user.get("searchToPurchaseRate")
                    else 0
                ),
                "most_active_hour": user.get("mostActiveHour"),
                "most_active_day": user.get("mostActiveDay"),
                "device_type": user.get("deviceType", "unknown"),
                "primary_referrer": user.get("primaryReferrer", "direct"),
                # From aggregated InteractionFeatures
                "total_interaction_score": float(
                    user.get("total_interaction_score") or 0
                ),
                "avg_affinity_score": float(user.get("avg_affinity_score") or 0),
                # From aggregated SessionFeatures
                "completed_sessions": int(user.get("completed_sessions") or 0),
                "avg_session_duration": float(user.get("avg_session_duration") or 0),
                # Computed segments
                "customer_segment": self._calculate_customer_segment(user),
                "is_active": bool((user.get("daysSinceLastOrder") or 365) < 30),
                "is_high_value": bool((user.get("lifetimeValue") or 0) > 500),
                "is_frequent_buyer": bool(
                    (user.get("orderFrequencyPerMonth") or 0) > 1
                ),
                # Optimized features for better recommendations
                "purchase_power": min(float(user.get("totalSpent") or 0) / 5000, 1.0),
                "purchase_frequency": min(
                    int(user.get("totalPurchases") or 0) / 50, 1.0
                ),
                "recency_tier": self._calculate_recency_tier(
                    user.get("daysSinceLastOrder")
                ),
                "is_active_30d": int((user.get("daysSinceLastOrder") or 999) < 30),
                "is_active_7d": int((user.get("daysSinceLastOrder") or 999) < 7),
                "engagement_level": min(
                    (
                        (user.get("productViewCount") or 0)
                        + (user.get("cartAddCount") or 0) * 3
                    )
                    / 100,
                    1.0,
                ),
                "category_diversity": min(
                    (user.get("distinctCategoriesPurchased") or 0) / 5, 1.0
                ),
                "price_tier": self._encode_price_tier(user.get("pricePointPreference")),
                "discount_affinity": min(
                    float(user.get("discountSensitivity") or 0) * 2, 1.0
                ),
                "conversion_score": self._calculate_conversion_score(user),
                "lifecycle_stage": self._encode_lifecycle_stage(user),
                "customer_value_tier": self._calculate_value_tier(
                    float(user.get("totalSpent") or 0),
                    int(user.get("totalPurchases") or 0),
                ),
            }

            # Remove None values
            return {k: v for k, v in labels.items() if v is not None}
        except Exception as e:
            logger.error(
                f"Error building user labels for user {user.get('customerId', 'unknown')}: {str(e)}"
            )
            logger.error(f"User data keys: {list(user.keys())}")
            logger.error(f"User data sample: {dict(list(user.items())[:10])}")

            raise

    def _calculate_customer_segment(self, user: Dict[str, Any]) -> str:
        """Calculate customer segment based on user data"""
        lifetime_value = float(user.get("lifetimeValue") or 0)
        order_frequency = float(user.get("orderFrequencyPerMonth") or 0)
        days_since_last_order = user.get("daysSinceLastOrder", 999)

        # High-value, frequent customers
        if lifetime_value > 1000 and order_frequency > 2:
            return "vip"

        # High-value but less frequent
        elif lifetime_value > 500 and order_frequency > 1:
            return "premium"

        # Active customers with some value
        elif days_since_last_order < 30 and lifetime_value > 100:
            return "active"

        # Recent customers
        elif days_since_last_order < 90:
            return "recent"

        # Inactive customers
        else:
            return "inactive"

    def _build_comprehensive_item_labels(
        self, product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build comprehensive Gorse item labels from all feature tables
        """
        labels = {
            # From ProductFeatures
            "view_count_30d": int(product.get("viewCount30d", 0)),
            "unique_viewers_30d": int(product.get("uniqueViewers30d", 0)),
            "cart_add_count_30d": int(product.get("cartAddCount30d", 0)),
            "purchase_count_30d": int(product.get("purchaseCount30d", 0)),
            "unique_purchasers_30d": int(product.get("uniquePurchasers30d", 0)),
            "view_to_cart_rate": (
                float(product.get("viewToCartRate", 0))
                if product.get("viewToCartRate")
                else 0
            ),
            "cart_to_purchase_rate": (
                float(product.get("cartToPurchaseRate", 0))
                if product.get("cartToPurchaseRate")
                else 0
            ),
            "overall_conversion_rate": (
                float(product.get("overallConversionRate", 0))
                if product.get("overallConversionRate")
                else 0
            ),
            "days_since_last_purchase": product.get("daysSinceLastPurchase"),
            "days_since_first_purchase": product.get("daysSinceFirstPurchase"),
            "avg_selling_price": (
                float(product.get("avgSellingPrice", 0))
                if product.get("avgSellingPrice")
                else 0
            ),
            "price_variance": (
                float(product.get("priceVariance", 0))
                if product.get("priceVariance")
                else 0
            ),
            "inventory_turnover": (
                float(product.get("inventoryTurnover", 0))
                if product.get("inventoryTurnover")
                else 0
            ),
            "stock_velocity": (
                float(product.get("stockVelocity", 0))
                if product.get("stockVelocity")
                else 0
            ),
            "price_tier": product.get("priceTier", "mid"),
            "popularity_score": float(product.get("popularityScore", 0)),
            "trending_score": float(product.get("trendingScore", 0)),
            "variant_complexity": (
                float(product.get("variantComplexity", 0))
                if product.get("variantComplexity")
                else 0
            ),
            "image_richness": (
                float(product.get("imageRichness", 0))
                if product.get("imageRichness")
                else 0
            ),
            "tag_diversity": (
                float(product.get("tagDiversity", 0))
                if product.get("tagDiversity")
                else 0
            ),
            # From ProductData
            "product_type": product.get("productType", "unknown"),
            "vendor": product.get("vendor", "unknown"),
            "in_stock": bool(product.get("totalInventory", 0) > 0),
            "has_discount": self._calculate_has_discount(product),
            # Collection features (from CollectionFeatures table)
            "collection_count": (
                len(product.get("collections", []))
                if isinstance(product.get("collections"), list)
                else 0
            ),
            "collection_quality_score": float(
                product.get("collection_performance_score", 0.5)
            ),
            "cross_collection_score": float(
                product.get("collection_conversion_rate", 0.0)
            ),
            "is_in_manual_collections": bool(product.get("collections")),
            "is_in_automated_collections": False,  # Would need to check CollectionData.isAutomated
            # From aggregated ProductPairFeatures
            "avg_lift_score": float(product.get("avg_lift_score", 0)),
            "frequently_bought_with_count": int(
                product.get("frequently_bought_with_count", 0)
            ),
            # From aggregated SearchProductFeatures
            "search_ctr": float(product.get("search_ctr", 0)),
            "search_conversion_rate": float(product.get("search_conversion_rate", 0)),
            # Computed flags
            "is_new": self._calculate_is_new(product),
            "is_bestseller": bool(product.get("purchase_count_30d", 0) > 10),
            "is_trending": bool(product.get("trending_score", 0) > 0.7),
            "needs_restock": bool(
                product.get("total_inventory", 1) < 10
                and product.get("stock_velocity", 0) > 0.5
            ),
            # Optimized features for better recommendations
            "performance_score": self._calculate_performance_score(product),
            "freshness_score": self._calculate_freshness_score(product),
            "price_bucket": self._bucket_price(
                float(product.get("avgSellingPrice") or product.get("price") or 0)
            ),
            "has_discount": int(bool(product.get("compareAtPrice"))),
            "stock_level": min(int(product.get("totalInventory", 0)) / 100, 1.0),
        }

        # Add tags if available
        if product.get("tags"):
            tags = product["tags"]
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []
            if isinstance(tags, list) and tags:
                labels["tags"] = "|".join(tags[:5])  # Limit to 5 tags

        # Remove None values
        return {k: v for k, v in labels.items() if v is not None}

    def _calculate_is_new(self, product: Dict[str, Any]) -> bool:
        """Calculate is_new flag based on creation date or first purchase"""
        # Prioritize purchase data if available
        days_since_first_purchase = product.get("daysSinceFirstPurchase")
        if days_since_first_purchase is not None:
            return days_since_first_purchase < 30

        # Fallback to product creation date
        created_at = product.get("productCreatedAt")
        if created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except:
                    return False
            if isinstance(created_at, datetime):
                return (now_utc() - created_at).days < 30

        return False

    def _calculate_has_discount(self, product: Dict[str, Any]) -> bool:
        """Calculate has_discount flag with fallbacks"""
        compare_at_price = product.get("compareAtPrice")
        if compare_at_price is None or compare_at_price <= 0:
            return False

        # Use avgSellingPrice if available (more accurate)
        avg_selling_price = product.get("avgSellingPrice")
        if avg_selling_price is not None:
            return float(compare_at_price) > float(avg_selling_price)

        # Fallback to list price
        price = product.get("price")
        if price is not None:
            return float(compare_at_price) > float(price)

        return False

    def _calculate_recency_tier(self, days_since_last: Optional[int]) -> int:
        """Calculate recency tier (0-4)"""
        if days_since_last is None:
            return 0
        if days_since_last < 7:
            return 4
        elif days_since_last < 30:
            return 3
        elif days_since_last < 90:
            return 2
        elif days_since_last < 180:
            return 1
        else:
            return 0

    def _encode_price_tier(self, price_pref: Optional[str]) -> int:
        """Encode price tier as number"""
        tiers = {"budget": 0, "mid": 1, "premium": 2, "luxury": 3}
        return tiers.get(price_pref, 1)

    def _calculate_conversion_score(self, user: Dict[str, Any]) -> float:
        """Calculate user's conversion propensity"""
        browse_to_cart = float(user.get("browseToCartRate") or 0)
        cart_to_purchase = float(user.get("cartToPurchaseRate") or 0)

        # Weight purchase conversion higher
        return min(browse_to_cart * 0.3 + cart_to_purchase * 0.7, 1.0)

    def _encode_lifecycle_stage(self, user: Dict[str, Any]) -> int:
        """Encode customer lifecycle stage"""
        total_spent = float(user.get("totalSpent") or 0)
        days_since_last = user.get("daysSinceLastOrder") or 999
        frequency = float(user.get("orderFrequencyPerMonth") or 0)

        if total_spent > 1000 and days_since_last < 30:
            return 5  # Champions
        elif frequency > 1 and days_since_last < 60:
            return 4  # Loyal
        elif total_spent > 100 and days_since_last < 90:
            return 3  # Potential
        elif days_since_last < 180:
            return 2  # At risk
        elif total_spent > 0:
            return 1  # Lost
        else:
            return 0  # New

    def _calculate_value_tier(self, total_spent: float, total_purchases: int) -> int:
        """Calculate customer value tier"""
        if total_spent > 2000 or total_purchases > 20:
            return 3  # High value
        elif total_spent > 500 or total_purchases > 5:
            return 2  # Medium value
        elif total_spent > 0:
            return 1  # Low value
        else:
            return 0  # No value yet

    def _calculate_performance_score(self, product: Dict[str, Any]) -> float:
        """Calculate unified product performance score"""
        views = int(product.get("viewCount30d", 0))
        purchases = int(product.get("purchaseCount30d", 0))
        conversion = float(product.get("overallConversionRate") or 0)

        # Log scale for views, linear for purchases
        view_score = min(math.log10(views + 1) / 3, 1.0) if views > 0 else 0
        purchase_score = min(purchases / 20, 1.0)

        # Weighted combination
        return view_score * 0.2 + purchase_score * 0.5 + conversion * 30

    def _calculate_freshness_score(self, product: Dict[str, Any]) -> float:
        """Calculate product freshness with decay"""
        # Prioritize purchase data for freshness
        days_since_purchase = product.get("daysSinceFirstPurchase")
        if days_since_purchase is not None:
            # Exponential decay over 90 days
            return max(0, 1.0 - (days_since_purchase / 90) ** 2)

        # Fallback to creation date if no purchase data
        created_at = product.get("productCreatedAt")
        if created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except:
                    return 1.0  # Default to fresh if parse fails
            if isinstance(created_at, datetime):
                days_since_creation = (now_utc() - created_at).days
                return max(0, 1.0 - (days_since_creation / 90) ** 2)

        return 1.0

    def _bucket_price(self, price: float) -> int:
        """Bucket price into categories"""
        if price < 25:
            return 0
        elif price < 75:
            return 1
        elif price < 150:
            return 2
        elif price < 300:
            return 3
        else:
            return 4

    def _apply_time_decay(self, timestamp: Any) -> float:
        """Apply time decay to feedback weight"""
        if not timestamp:
            return 1.0

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except:
                return 1.0

        days_old = (now_utc() - timestamp).days

        # Exponential decay with 30-day half-life
        return 0.5 ** (days_old / 30)

    def _extract_simple_categories(self, product: Dict[str, Any]) -> List[str]:
        """Extract simplified categories"""
        categories = []

        # Just use product type as main category
        if product.get("productType"):
            categories.append(str(product["productType"]))

        # Add collections if available
        collections = product.get("collections", [])
        if isinstance(collections, str):
            try:
                collections = json.loads(collections)
            except:
                collections = []

        # Limit to 3 categories
        for coll in collections[:2]:
            if isinstance(coll, dict) and coll.get("id"):
                categories.append(str(coll["id"]))

        return categories

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from event data"""
        # Check various possible fields for product ID
        product_id = event.get("product_id") or event.get("productId")
        if product_id:
            return str(product_id)

        # Check in properties
        properties = event.get("properties", {})
        product_id = properties.get("product_id") or properties.get("productId")
        if product_id:
            return str(product_id)

        return None
