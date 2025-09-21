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

    def __init__(self):
        """Initialize Gorse data transformers"""
        pass

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
                # NEW: Enhanced customer demographic features
                "customer_email": user.get("customerEmail", ""),
                "customer_first_name": user.get("customerFirstName", ""),
                "customer_last_name": user.get("customerLastName", ""),
                "customer_verified_email": bool(
                    user.get("customerVerifiedEmail", False)
                ),
                "customer_tax_exempt": bool(user.get("customerTaxExempt", False)),
                "customer_currency_code": user.get("customerCurrencyCode", "USD"),
                "customer_locale": user.get("customerLocale", "en"),
                # NEW: Enhanced device and location features
                "browser_type": user.get("browserType", "unknown"),
                "os_type": user.get("osType", "unknown"),
                "screen_resolution": user.get("screenResolution", "unknown"),
                "country": user.get("country", "unknown"),
                "region": user.get("region", "unknown"),
                "city": user.get("city", "unknown"),
                "timezone": user.get("timezone", "unknown"),
                "language": user.get("language", "en"),
                "referrer_type": user.get("referrerType", "direct"),
                "traffic_source": user.get("trafficSource", "direct"),
                "device_consistency": float(user.get("deviceConsistency", 0)),
                # NEW: Additional CustomerBehaviorFeatures fields
                "total_unified_sessions": int(user.get("totalUnifiedSessions", 0)),
                "cross_session_span_days": int(user.get("crossSessionSpanDays", 0)),
                "session_frequency_score": float(user.get("sessionFrequencyScore", 0)),
                "device_diversity": int(user.get("deviceDiversity", 0)),
                "avg_session_duration": float(user.get("avgSessionDuration", 0)),
                "extension_engagement_score": float(
                    user.get("extensionEngagementScore", 0)
                ),
                "recommendation_click_rate": float(
                    user.get("recommendationClickRate", 0)
                ),
                "upsell_interaction_count": int(user.get("upsellInteractionCount", 0)),
                "total_interactions_in_sessions": int(
                    user.get("totalInteractionsInSessions", 0)
                ),
                "avg_interactions_per_session": float(
                    user.get("avgInteractionsPerSession", 0)
                ),
                "session_engagement_score": float(
                    user.get("sessionEngagementScore", 0)
                ),
                "multi_touch_attribution_score": float(
                    user.get("multiTouchAttributionScore", 0)
                ),
                "attribution_revenue": float(user.get("attributionRevenue", 0)),
                "conversion_path_length": int(user.get("conversionPathLength", 0)),
                # From aggregated InteractionFeatures
                "total_interaction_score": float(
                    user.get("total_interaction_score") or 0
                ),
                "avg_affinity_score": float(user.get("avg_affinity_score") or 0),
                # From aggregated SessionFeatures
                "completed_sessions": int(user.get("completed_sessions") or 0),
                "avg_session_duration": float(user.get("avg_session_duration") or 0),
                # From aggregated InteractionFeatures
                "total_interactions": int(user.get("total_interactions") or 0),
                "avg_interaction_score": float(user.get("avg_interaction_score") or 0),
                "product_affinity_score": float(
                    user.get("product_affinity_score") or 0
                ),
                # From aggregated CollectionFeatures
                "collections_viewed": int(user.get("collections_viewed") or 0),
                "collection_engagement": float(user.get("collection_engagement") or 0),
                # Computed segments
                "customer_segment": self._calculate_customer_segment(user),
                "is_active": bool((user.get("daysSinceLastOrder") or 365) < 30),
                "is_high_value": bool((user.get("lifetimeValue") or 0) > 500),
                "is_frequent_buyer": bool(
                    (user.get("orderFrequencyPerMonth") or 0) > 1
                ),
                # NEW: Enhanced customer segments using new data
                "is_verified_customer": bool(user.get("customerVerifiedEmail", False)),
                "is_tax_exempt": bool(user.get("customerTaxExempt", False)),
                "geographic_segment": self._calculate_geographic_segment(user),
                "device_segment": self._calculate_device_segment(user),
                "traffic_source_segment": self._calculate_traffic_source_segment(user),
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
                # Enhanced Customer Features (from Order API)
                "customer_state": user.get("customerState", "unknown"),
                "is_verified_email": int(user.get("isVerifiedEmail", False)),
                # NEW: Enhanced features from unified analytics
                # Cross-session features
                "total_unified_sessions": int(user.get("totalUnifiedSessions", 0)),
                "cross_session_span_days": int(user.get("crossSessionSpanDays", 0)),
                "session_frequency_score": float(user.get("sessionFrequencyScore", 0)),
                "device_diversity": int(user.get("deviceDiversity", 0)),
                "avg_session_duration_unified": float(
                    user.get("avgSessionDuration", 0) or 0
                ),
                # Extension-specific features
                "phoenix_interaction_count": int(
                    user.get("phoenixInteractionCount", 0)
                ),
                "apollo_interaction_count": int(user.get("apolloInteractionCount", 0)),
                "venus_interaction_count": int(user.get("venusInteractionCount", 0)),
                "atlas_interaction_count": int(user.get("atlasInteractionCount", 0)),
                "extension_engagement_score": float(
                    user.get("extensionEngagementScore", 0)
                ),
                "recommendation_click_rate": float(
                    user.get("recommendationClickRate", 0)
                ),
                "upsell_interaction_count": int(user.get("upsellInteractionCount", 0)),
                # Enhanced session metrics
                "total_interactions_in_sessions": int(
                    user.get("totalInteractionsInSessions", 0)
                ),
                "avg_interactions_per_session": float(
                    user.get("avgInteractionsPerSession", 0)
                ),
                "session_engagement_score": float(
                    user.get("sessionEngagementScore", 0)
                ),
                # Attribution features
                "multi_touch_attribution_score": float(
                    user.get("multiTouchAttributionScore", 0)
                ),
                "attribution_revenue": float(user.get("attributionRevenue", 0)),
                "conversion_path_length": int(user.get("conversionPathLength", 0)),
                "customer_age": user.get("customerAge"),
                "has_default_address": int(user.get("hasDefaultAddress", False)),
                "geographic_region": user.get("geographicRegion", "unknown"),
                "currency_preference": user.get("currencyPreference", "USD"),
                "customer_health_score": int(user.get("customerHealthScore", 0)),
                # NEW: Refund Metrics
                "refunded_orders": int(user.get("refundedOrders", 0)),
                "refund_rate": float(user.get("refundRate", 0.0)),
                "total_refunded_amount": float(user.get("totalRefundedAmount", 0.0)),
                "net_lifetime_value": float(user.get("netLifetimeValue", 0.0)),
                "is_high_risk_customer": int(float(user.get("refundRate", 0.0)) > 0.25),
                "is_low_risk_customer": int(float(user.get("refundRate", 0.0)) < 0.05),
                "refund_risk_tier": self._calculate_refund_risk_tier(
                    user.get("refundRate")
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
        days_since_last_order = user.get("daysSinceLastOrder")

        # Handle None values for days_since_last_order
        if days_since_last_order is None:
            days_since_last_order = 999  # Treat as inactive if no data

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
            # NEW: Enhanced product features using previously unused fields
            "content_richness_score": int(product.get("contentRichnessScore", 0)),
            "description_length": int(product.get("descriptionLength", 0)),
            "description_html_length": int(product.get("descriptionHtmlLength", 0)),
            "product_age": product.get("productAge"),
            "last_updated_days": product.get("lastUpdatedDays"),
            "update_frequency": float(product.get("updateFrequency", 0)),
            "product_type": product.get("productType", "unknown"),
            "category_complexity": float(product.get("categoryComplexity", 0)),
            "availability_score": float(product.get("availabilityScore", 0)),
            "status_stability": float(product.get("statusStability", 0)),
            # From InteractionFeatures (aggregated)
            "total_interactions": int(product.get("totalInteractions", 0)),
            "interaction_score": float(product.get("interactionScore", 0)),
            "affinity_score": float(product.get("affinityScore", 0)),
            "refund_risk_score": float(product.get("refundRiskScore", 0)),
            "net_purchase_value": float(product.get("netPurchaseValue", 0)),
            # From SessionFeatures (aggregated)
            "session_engagement": float(product.get("sessionEngagement", 0)),
            "checkout_completion_rate": float(product.get("checkoutCompletionRate", 0)),
            "cart_abandonment_rate": float(product.get("cartAbandonmentRate", 0)),
            # From SearchProductFeatures (aggregated)
            "search_impressions": int(product.get("searchImpressions", 0)),
            "search_clicks": int(product.get("searchClicks", 0)),
            "search_purchases": int(product.get("searchPurchases", 0)),
            "search_ctr": float(product.get("searchCTR", 0)),
            "search_conversion_rate": float(product.get("searchConversionRate", 0)),
            # From ProductFeatures - additional fields
            "cart_abandonment_rate": float(product.get("cartAbandonmentRate", 0)),
            "cart_modification_rate": float(product.get("cartModificationRate", 0)),
            "cart_view_to_purchase_rate": float(
                product.get("cartViewToPurchaseRate", 0)
            ),
            "seo_optimization": float(product.get("seoOptimization", 0)),
            "seo_title_length": int(product.get("seoTitleLength", 0)),
            "seo_description_length": int(product.get("seoDescriptionLength", 0)),
            "has_video_content": bool(product.get("hasVideoContent", False)),
            "has_3d_content": bool(product.get("has3DContent", False)),
            "media_count": int(product.get("mediaCount", 0)),
            "has_online_store_url": bool(product.get("hasOnlineStoreUrl", False)),
            "has_preview_url": bool(product.get("hasPreviewUrl", False)),
            "has_custom_template": bool(product.get("hasCustomTemplate", False)),
            "metafield_utilization": float(product.get("metafieldUtilization", 0)),
            "media_richness": float(product.get("mediaRichness", 0)),
            "refunded_orders": int(product.get("refundedOrders", 0)),
            "refund_rate": float(product.get("refundRate", 0)),
            "total_refunded_amount": float(product.get("totalRefundedAmount", 0)),
            "net_revenue": float(product.get("netRevenue", 0)),
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
            "vendor": product.get("vendor", "unknown"),
            "in_stock": bool(product.get("totalInventory", 0) > 0),
            "has_discount": self._calculate_has_discount(product),
            # NEW: Enhanced product segments using new data
            "content_quality_segment": self._calculate_content_quality_segment(product),
            "lifecycle_segment": self._calculate_product_lifecycle_segment(product),
            "availability_segment": self._calculate_availability_segment(product),
            # Collection features (from CollectionFeatures table)
            "collection_count": (
                len(product.get("collections", []))
                if isinstance(product.get("collections"), list)
                else 0
            ),
            # NEW: Enhanced collection features using previously unused fields
            "handle_quality": float(product.get("handleQuality", 0)),
            "template_score": int(product.get("templateScore", 0)),
            "seo_optimization_score": float(product.get("seoOptimizationScore", 0)),
            "collection_age": product.get("collectionAge"),
            "collection_update_frequency": float(product.get("updateFrequency", 0)),
            "lifecycle_stage": product.get("lifecycleStage", "unknown"),
            # NEW: Enhanced product features using previously unused fields
            "content_richness_score": int(product.get("contentRichnessScore", 0)),
            "description_length": int(product.get("descriptionLength", 0)),
            "description_html_length": int(product.get("descriptionHtmlLength", 0)),
            "product_age": product.get("productAge"),
            "last_updated_days": product.get("lastUpdatedDays"),
            "update_frequency": float(product.get("updateFrequency", 0)),
            "product_type": product.get("productType", "unknown"),
            "category_complexity": float(product.get("categoryComplexity", 0)),
            "availability_score": float(product.get("availabilityScore", 0)),
            "status_stability": float(product.get("statusStability", 0)),
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
            # Enhanced Product Features (from new Shopify data)
            "media_richness": float(product.get("mediaRichness", 0)),
            "seo_optimization": float(product.get("seoOptimization", 0)),
            "seo_title_length": int(product.get("seoTitleLength", 0)),
            "seo_description_length": int(product.get("seoDescriptionLength", 0)),
            "has_video_content": int(product.get("hasVideoContent", False)),
            "has_3d_content": int(product.get("has3DContent", False)),
            "media_count": int(product.get("mediaCount", 0)),
            "has_online_store_url": int(product.get("hasOnlineStoreUrl", False)),
            "has_preview_url": int(product.get("hasPreviewUrl", False)),
            "has_custom_template": int(product.get("hasCustomTemplate", False)),
            # NEW: Refund Metrics
            "refunded_orders": int(product.get("refundedOrders", 0)),
            "refund_rate": float(product.get("refundRate", 0.0)),
            "total_refunded_amount": float(product.get("totalRefundedAmount", 0.0)),
            "net_revenue": float(product.get("netRevenue", 0.0)),
            "refund_risk_score": float(product.get("refundRiskScore", 0.0)),
            "is_high_risk_product": int(
                float(product.get("refundRiskScore", 0.0)) > 70
            ),
            "is_low_risk_product": int(float(product.get("refundRiskScore", 0.0)) < 30),
            "refund_risk_tier": self._calculate_product_refund_risk_tier(
                product.get("refundRiskScore")
            ),
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

    def _extract_product_id_from_event(
        self, event_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract product ID from various event data structures"""
        try:
            if not isinstance(event_data, dict):
                return None

            # Check for direct product ID
            if "product" in event_data and isinstance(event_data["product"], dict):
                product_id = event_data["product"].get("id")
                if product_id and "Product" in product_id:
                    return product_id

            # Check for productVariant (product_viewed events)
            if "productVariant" in event_data and isinstance(
                event_data["productVariant"], dict
            ):
                # First try to get the product ID directly from the product field
                product = event_data["productVariant"].get("product", {})
                if isinstance(product, dict) and product.get("id"):
                    return product.get("id")

                # Fallback to converting variant ID
                variant_id = event_data["productVariant"].get("id")
                if variant_id:
                    return self._convert_variant_to_product_id(variant_id)

            # Check for cartLine.merchandise (cart events)
            if "cartLine" in event_data and isinstance(event_data["cartLine"], dict):
                merchandise = event_data["cartLine"].get("merchandise", {})
                if isinstance(merchandise, dict):
                    variant_id = merchandise.get("id")
                    if variant_id:
                        return self._convert_variant_to_product_id(variant_id)

            # Check for merchandise (direct cart events)
            if "merchandise" in event_data and isinstance(
                event_data["merchandise"], dict
            ):
                variant_id = event_data["merchandise"].get("id")
                if variant_id:
                    return self._convert_variant_to_product_id(variant_id)

            # Check for lineItems in checkout events
            if "lineItems" in event_data and isinstance(event_data["lineItems"], list):
                for line_item in event_data["lineItems"]:
                    if isinstance(line_item, dict) and "variant" in line_item:
                        variant = line_item["variant"]
                        if isinstance(variant, dict):
                            variant_id = variant.get("id")
                            if variant_id:
                                return self._convert_variant_to_product_id(variant_id)

            # Fallback to direct product ID fields
            product_id = event_data.get("product_id") or event_data.get("productId")
            if product_id:
                return str(product_id)

            return None
        except Exception as e:
            logger.error(f"Failed to extract product ID: {e}")
            return None

    def _convert_variant_to_product_id(self, variant_id: str) -> Optional[str]:
        """Convert product variant ID to product ID"""
        try:
            if not variant_id or "ProductVariant" not in variant_id:
                return None

            # Extract the numeric ID from the variant ID
            # Format: gid://shopify/ProductVariant/123456789
            parts = variant_id.split("/")
            if len(parts) >= 4:
                variant_num = parts[-1]
                # Convert variant ID to product ID (this is a simplified approach)
                # In a real implementation, you might need to look up the actual product ID
                # from the database or use a more sophisticated mapping
                return f"gid://shopify/Product/{variant_num}"

            return None
        except Exception as e:
            logger.error(f"Failed to convert variant to product ID: {e}")
            return None

    def transform_user_features_to_labels(self, user) -> Dict[str, Any]:
        """Transform user features to Gorse labels"""
        try:
            # Convert user object to dict if needed
            if hasattr(user, "__dict__"):
                user_dict = user.__dict__
            else:
                user_dict = user

            return self._build_comprehensive_user_labels(user_dict)
        except Exception as e:
            logger.error(f"Failed to transform user features: {str(e)}")
            return {}

    def transform_product_features_to_labels(
        self, product, product_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Transform product features to Gorse labels"""
        try:
            # Convert product object to dict if needed
            if hasattr(product, "__dict__"):
                product_dict = product.__dict__
            else:
                product_dict = product

            # Merge with additional product info if provided
            if product_info:
                product_dict.update(product_info)

            return self._build_comprehensive_item_labels(product_dict)
        except Exception as e:
            logger.error(f"Failed to transform product features: {str(e)}")
            return {}

    def transform_behavioral_event_to_feedback(
        self, event, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform behavioral event to Gorse feedback"""
        try:
            feedback_list = []

            # Convert event object to dict if needed
            if hasattr(event, "__dict__"):
                event_dict = event.__dict__
            else:
                event_dict = event

            event_type = event_dict.get("eventType", "")
            client_id = event_dict.get("clientId", "")
            timestamp = event_dict.get("timestamp", now_utc())

            # Extract productId from eventData JSON field
            product_id = self._extract_product_id_from_event(event_dict)

            # Skip if missing required fields
            if not client_id or not product_id:
                return feedback_list

            # Map event types to feedback types
            feedback_type_map = {
                "product_viewed": "view",
                "product_added_to_cart": "cart_add",
                "product_removed_from_cart": "cart_remove",
                "checkout_started": "checkout",
                "order_completed": "purchase",
            }

            feedback_type = feedback_type_map.get(event_type)
            if not feedback_type:
                return feedback_list

            # Create feedback record
            feedback = {
                "feedbackType": feedback_type,
                "userId": f"shop_{shop_id}_{client_id}",
                "itemId": f"shop_{shop_id}_{product_id}",
                "timestamp": (
                    timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp)
                ),
            }

            feedback_list.append(feedback)
            return feedback_list

        except Exception as e:
            logger.error(f"Failed to transform behavioral event: {str(e)}")
            return []

    def transform_order_to_feedback(self, order, shop_id: str) -> List[Dict[str, Any]]:
        """Transform order to Gorse feedback"""
        try:
            feedback_list = []

            # Convert order object to dict if needed
            if hasattr(order, "__dict__"):
                order_dict = order.__dict__
            else:
                order_dict = order

            customer_id = order_dict.get("customerId", "")
            order_date = order_dict.get("orderDate", now_utc())
            line_items = order_dict.get("lineItems", [])
            financial_status = order_dict.get("financialStatus", "")
            total_refunded_amount = float(order_dict.get("totalRefundedAmount", 0.0))

            # Skip if missing customer ID
            if not customer_id:
                return feedback_list

            # Create feedback for each line item
            for item in line_items:
                if isinstance(item, dict):
                    product_id = item.get("productId", "")
                    quantity = item.get("quantity", 1)
                    line_total = float(item.get("lineTotal", 0.0))
                else:
                    # Handle object attributes
                    product_id = getattr(item, "productId", "")
                    quantity = getattr(item, "quantity", 1)
                    line_total = float(getattr(item, "lineTotal", 0.0))

                if not product_id:
                    continue

                # Determine feedback type based on financial status
                if financial_status == "refunded" and total_refunded_amount > 0:
                    # Create negative refund feedback
                    feedback = {
                        "feedbackType": "refund",
                        "userId": f"shop_{shop_id}_{customer_id}",
                        "itemId": f"shop_{shop_id}_{product_id}",
                        "timestamp": (
                            order_date.isoformat()
                            if hasattr(order_date, "isoformat")
                            else str(order_date)
                        ),
                        "labels": {
                            "weight": -5.0,  # Negative weight for refunds
                            "refund_amount": line_total,
                            "refund_reason": "order_refunded",
                        },
                    }
                else:
                    # Create positive purchase feedback
                    feedback = {
                        "feedbackType": "purchase",
                        "userId": f"shop_{shop_id}_{customer_id}",
                        "itemId": f"shop_{shop_id}_{product_id}",
                        "timestamp": (
                            order_date.isoformat()
                            if hasattr(order_date, "isoformat")
                            else str(order_date)
                        ),
                        "labels": {
                            "weight": 1.0,  # Positive weight for purchases
                            "purchase_amount": line_total,
                            "quantity": quantity,
                        },
                    }

                feedback_list.append(feedback)

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to transform order to feedback: {str(e)}")
            return []

    def _extract_product_id_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from behavioral event eventData"""
        try:
            event_type = event.get("eventType", "")
            event_data = event.get("eventData", {})

            # Handle string eventData
            if isinstance(event_data, str):
                try:
                    import json

                    event_data = json.loads(event_data)
                except:
                    return None

            if event_type == "product_viewed":
                product_variant = event_data.get("data", {}).get("productVariant", {})
                product = product_variant.get("product", {})
                return self._extract_id_from_gid(product.get("id", ""))

            elif event_type == "product_added_to_cart":
                cart_line = event_data.get("data", {}).get("cartLine", {})
                merchandise = cart_line.get("merchandise", {})
                product = merchandise.get("product", {})
                return self._extract_id_from_gid(product.get("id", ""))

            elif event_type == "product_removed_from_cart":
                cart_line = event_data.get("data", {}).get("cartLine", {})
                merchandise = cart_line.get("merchandise", {})
                product = merchandise.get("product", {})
                return self._extract_id_from_gid(product.get("id", ""))

            elif event_type == "checkout_started":
                # Checkout events might not have product info
                return None

            elif event_type == "checkout_completed":
                # Checkout completed events might not have product info
                return None

            return None

        except Exception as e:
            logger.error(f"Failed to extract product ID from event: {str(e)}")
            return None

    def _extract_id_from_gid(self, gid: str) -> str:
        """Extract numeric ID from Shopify GID"""
        if not gid:
            return ""

        # Handle GID format: gid://shopify/Product/123456
        if "/" in gid:
            return gid.split("/")[-1]

        return gid

    def transform_session_features_to_gorse(
        self, session, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Transform session features to Gorse session data"""
        try:
            # Convert session object to dict if needed
            if hasattr(session, "__dict__"):
                session_dict = session.__dict__
            else:
                session_dict = session

            if not session_dict.get("customerId"):
                return None

            return {
                "userId": f"shop_{shop_id}_{session_dict['customerId']}",
                "sessionId": f"shop_{shop_id}_{session_dict.get('sessionId', 'unknown')}",
                "timestamp": session_dict.get("lastComputedAt", now_utc()).isoformat(),
                "labels": {
                    "session_duration": session_dict.get("sessionDuration", 0),
                    "page_views": session_dict.get("pageViews", 0),
                    "products_viewed": session_dict.get("productsViewed", 0),
                    "cart_adds": session_dict.get("cartAdds", 0),
                    "conversion": session_dict.get("conversion", False),
                    "bounce_rate": session_dict.get("bounceRate", 0),
                    "avg_time_on_page": session_dict.get("avgTimeOnPage", 0),
                },
            }
        except Exception as e:
            logger.error(f"Failed to transform session features: {str(e)}")
            return None

    def transform_product_pair_features_to_feedback(
        self, pair, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform product pair features to Gorse feedback for item-to-item recommendations"""
        try:
            feedback_list = []

            # Convert pair object to dict if needed
            if hasattr(pair, "__dict__"):
                pair_dict = pair.__dict__
            else:
                pair_dict = pair

            co_occurrence_strength = pair_dict.get("coOccurrenceStrength", 0)
            if co_occurrence_strength <= 0:
                return feedback_list

            # Create bidirectional feedback for item-to-item recommendations
            feedback_list.extend(
                [
                    {
                        "feedbackType": "co_occurrence",
                        "userId": f"shop_{shop_id}_system",  # System-generated feedback
                        "itemId": f"shop_{shop_id}_{pair_dict['productId1']}",
                        "timestamp": pair_dict.get(
                            "lastComputedAt", now_utc()
                        ).isoformat(),
                        "labels": {
                            "related_item": f"shop_{shop_id}_{pair_dict['productId2']}",
                            "strength": co_occurrence_strength,
                            "lift_score": pair_dict.get("liftScore", 0),
                            "confidence": pair_dict.get("confidence", 0),
                        },
                    },
                    {
                        "feedbackType": "co_occurrence",
                        "userId": f"shop_{shop_id}_system",
                        "itemId": f"shop_{shop_id}_{pair_dict['productId2']}",
                        "timestamp": pair_dict.get(
                            "lastComputedAt", now_utc()
                        ).isoformat(),
                        "labels": {
                            "related_item": f"shop_{shop_id}_{pair_dict['productId1']}",
                            "strength": co_occurrence_strength,
                            "lift_score": pair_dict.get("liftScore", 0),
                            "confidence": pair_dict.get("confidence", 0),
                        },
                    },
                ]
            )

            return feedback_list
        except Exception as e:
            logger.error(f"Failed to transform product pair features: {str(e)}")
            return []

    def transform_search_product_features_to_feedback(
        self, search_product, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Transform search product features to Gorse feedback for search-based recommendations"""
        try:
            # Convert search_product object to dict if needed
            if hasattr(search_product, "__dict__"):
                search_dict = search_product.__dict__
            else:
                search_dict = search_product

            correlation_strength = search_dict.get("correlationStrength", 0)
            if correlation_strength <= 0:
                return None

            return {
                "feedbackType": "search_result",
                "userId": f"shop_{shop_id}_search",  # Search-based feedback
                "itemId": f"shop_{shop_id}_{search_dict['productId']}",
                "timestamp": search_dict.get("lastComputedAt", now_utc()).isoformat(),
                "labels": {
                    "search_query": search_dict.get("searchQuery", ""),
                    "correlation_strength": correlation_strength,
                    "search_context": True,
                    "ctr": search_dict.get("ctr", 0),
                    "conversion_rate": search_dict.get("conversionRate", 0),
                    "search_volume": search_dict.get("searchVolume", 0),
                },
            }
        except Exception as e:
            logger.error(f"Failed to transform search product features: {str(e)}")
            return None

    def transform_collection_features_to_item(
        self, collection, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Transform collection features to Gorse item for collection-based recommendations"""
        try:
            # Convert collection object to dict if needed
            if hasattr(collection, "__dict__"):
                collection_dict = collection.__dict__
            else:
                collection_dict = collection

            collection_id = collection_dict.get("collectionId", "")
            if not collection_id:
                return None

            # Build collection item for Gorse
            collection_item = {
                "ItemId": f"shop_{shop_id}_collection_{collection_id}",
                "Categories": [
                    f"shop_{shop_id}",
                    "Collections",
                    collection_dict.get("collectionType", "manual"),
                ],
                "Labels": [
                    f"product_count:{collection_dict.get('productCount', 0)}",
                    f"is_automated:{int(collection_dict.get('isAutomated', False))}",
                    f"view_count_30d:{collection_dict.get('viewCount30d', 0)}",
                    f"unique_viewers_30d:{collection_dict.get('uniqueViewers30d', 0)}",
                    f"click_through_rate:{collection_dict.get('clickThroughRate', 0)}",
                    f"bounce_rate:{collection_dict.get('bounceRate', 0)}",
                    f"avg_product_price:{collection_dict.get('avgProductPrice', 0)}",
                    f"min_product_price:{collection_dict.get('minProductPrice', 0)}",
                    f"max_product_price:{collection_dict.get('maxProductPrice', 0)}",
                    f"price_range:{collection_dict.get('priceRange', 0)}",
                    f"price_variance:{collection_dict.get('priceVariance', 0)}",
                    f"conversion_rate:{collection_dict.get('conversionRate', 0)}",
                    f"revenue_contribution:{collection_dict.get('revenueContribution', 0)}",
                    f"seo_score:{collection_dict.get('seoScore', 0)}",
                    f"image_score:{collection_dict.get('imageScore', 0)}",
                    f"performance_score:{collection_dict.get('performanceScore', 0)}",
                ],
                "IsHidden": False,
                "Timestamp": collection_dict.get(
                    "lastComputedAt", now_utc()
                ).isoformat(),
                "Comment": f"Collection: {collection_id}",
            }

            return collection_item
        except Exception as e:
            logger.error(f"Failed to transform collection features: {str(e)}")
            return None

    def transform_customer_behavior_to_user_features(
        self, behavior, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Transform customer behavior features to enhanced Gorse user features"""
        try:
            # Convert behavior object to dict if needed
            if hasattr(behavior, "__dict__"):
                behavior_dict = behavior.__dict__
            else:
                behavior_dict = behavior

            customer_id = behavior_dict.get("customerId", "")
            if not customer_id:
                return None

            # Build enhanced user features for Gorse
            enhanced_user = {
                "UserId": f"shop_{shop_id}_{customer_id}",
                "Labels": [
                    # Session metrics
                    f"session_count:{behavior_dict.get('sessionCount', 0)}",
                    f"avg_session_duration:{behavior_dict.get('avgSessionDuration', 0)}",
                    f"avg_events_per_session:{behavior_dict.get('avgEventsPerSession', 0)}",
                    # Event counts
                    f"total_event_count:{behavior_dict.get('totalEventCount', 0)}",
                    f"product_view_count:{behavior_dict.get('productViewCount', 0)}",
                    f"collection_view_count:{behavior_dict.get('collectionViewCount', 0)}",
                    f"cart_add_count:{behavior_dict.get('cartAddCount', 0)}",
                    f"cart_view_count:{behavior_dict.get('cartViewCount', 0)}",
                    f"cart_remove_count:{behavior_dict.get('cartRemoveCount', 0)}",
                    f"search_count:{behavior_dict.get('searchCount', 0)}",
                    f"checkout_start_count:{behavior_dict.get('checkoutStartCount', 0)}",
                    f"purchase_count:{behavior_dict.get('purchaseCount', 0)}",
                    # Temporal patterns
                    f"days_since_first_event:{behavior_dict.get('daysSinceFirstEvent', 0)}",
                    f"days_since_last_event:{behavior_dict.get('daysSinceLastEvent', 0)}",
                    f"most_active_hour:{behavior_dict.get('mostActiveHour', 0)}",
                    f"most_active_day:{behavior_dict.get('mostActiveDay', 0)}",
                    # Behavior patterns
                    f"unique_products_viewed:{behavior_dict.get('uniqueProductsViewed', 0)}",
                    f"unique_collections_viewed:{behavior_dict.get('uniqueCollectionsViewed', 0)}",
                    f"device_type:{behavior_dict.get('deviceType', 'unknown')}",
                    f"primary_referrer:{behavior_dict.get('primaryReferrer', 'direct')}",
                    # Conversion metrics
                    f"browse_to_cart_rate:{behavior_dict.get('browseToCartRate', 0)}",
                    f"cart_to_purchase_rate:{behavior_dict.get('cartToPurchaseRate', 0)}",
                    f"search_to_purchase_rate:{behavior_dict.get('searchToPurchaseRate', 0)}",
                    # Computed scores
                    f"engagement_score:{behavior_dict.get('engagementScore', 0)}",
                    f"recency_score:{behavior_dict.get('recencyScore', 0)}",
                    f"diversity_score:{behavior_dict.get('diversityScore', 0)}",
                    f"behavioral_score:{behavior_dict.get('behavioralScore', 0)}",
                    # NEW: Enhanced features from unified analytics
                    # Cross-session features
                    f"total_unified_sessions:{behavior_dict.get('totalUnifiedSessions', 0)}",
                    f"cross_session_span_days:{behavior_dict.get('crossSessionSpanDays', 0)}",
                    f"session_frequency_score:{behavior_dict.get('sessionFrequencyScore', 0)}",
                    f"device_diversity:{behavior_dict.get('deviceDiversity', 0)}",
                    f"avg_session_duration_unified:{behavior_dict.get('avgSessionDuration', 0)}",
                    # Extension-specific features
                    f"phoenix_interaction_count:{behavior_dict.get('phoenixInteractionCount', 0)}",
                    f"apollo_interaction_count:{behavior_dict.get('apolloInteractionCount', 0)}",
                    f"venus_interaction_count:{behavior_dict.get('venusInteractionCount', 0)}",
                    f"atlas_interaction_count:{behavior_dict.get('atlasInteractionCount', 0)}",
                    f"extension_engagement_score:{behavior_dict.get('extensionEngagementScore', 0)}",
                    f"recommendation_click_rate:{behavior_dict.get('recommendationClickRate', 0)}",
                    f"upsell_interaction_count:{behavior_dict.get('upsellInteractionCount', 0)}",
                    # Enhanced session metrics
                    f"total_interactions_in_sessions:{behavior_dict.get('totalInteractionsInSessions', 0)}",
                    f"avg_interactions_per_session:{behavior_dict.get('avgInteractionsPerSession', 0)}",
                    f"session_engagement_score:{behavior_dict.get('sessionEngagementScore', 0)}",
                    # Attribution features
                    f"multi_touch_attribution_score:{behavior_dict.get('multiTouchAttributionScore', 0)}",
                    f"attribution_revenue:{behavior_dict.get('attributionRevenue', 0)}",
                    f"conversion_path_length:{behavior_dict.get('conversionPathLength', 0)}",
                ],
                "Subscribe": [],
                "Comment": f"Enhanced behavior features for customer {customer_id}",
            }

            return enhanced_user
        except Exception as e:
            logger.error(f"Failed to transform customer behavior features: {str(e)}")
            return None

    def _calculate_refund_risk_tier(self, refund_rate: Optional[float]) -> str:
        """Calculate refund risk tier for customers"""
        if refund_rate is None:
            return "unknown"

        if refund_rate > 0.5:
            return "very_high"
        elif refund_rate > 0.25:
            return "high"
        elif refund_rate > 0.1:
            return "medium"
        elif refund_rate > 0.05:
            return "low"
        elif refund_rate > 0:
            return "very_low"
        else:
            return "none"

    def _calculate_product_refund_risk_tier(
        self, refund_risk_score: Optional[float]
    ) -> str:
        """Calculate refund risk tier for products"""
        if refund_risk_score is None:
            return "unknown"

        if refund_risk_score > 80:
            return "very_high"
        elif refund_risk_score > 60:
            return "high"
        elif refund_risk_score > 40:
            return "medium"
        elif refund_risk_score > 20:
            return "low"
        elif refund_risk_score > 0:
            return "very_low"
        else:
            return "none"

    def _calculate_geographic_segment(self, user: Dict[str, Any]) -> str:
        """Calculate geographic segment based on location data"""
        try:
            country = user.get("country", "").lower()
            region = user.get("region", "").lower()

            if not country or country == "unknown":
                return "unknown"

            # Major markets
            if country in ["us", "united states", "usa"]:
                return "north_america"
            elif country in ["ca", "canada"]:
                return "north_america"
            elif country in ["gb", "uk", "united kingdom", "great britain"]:
                return "europe"
            elif country in ["de", "germany", "deutschland"]:
                return "europe"
            elif country in ["fr", "france"]:
                return "europe"
            elif country in ["au", "australia"]:
                return "oceania"
            elif country in ["jp", "japan"]:
                return "asia"
            elif country in ["cn", "china"]:
                return "asia"
            else:
                return "other"
        except Exception as e:
            logger.error(f"Error calculating geographic segment: {e}")
            return "unknown"

    def _calculate_device_segment(self, user: Dict[str, Any]) -> str:
        """Calculate device segment based on device data"""
        try:
            device_type = user.get("deviceType", "").lower()
            browser_type = user.get("browserType", "").lower()
            os_type = user.get("osType", "").lower()

            if not device_type or device_type == "unknown":
                return "unknown"

            # Mobile-first segmentation
            if device_type in ["mobile", "phone", "smartphone"]:
                return "mobile_primary"
            elif device_type in ["tablet", "ipad"]:
                return "tablet_primary"
            elif device_type in ["desktop", "computer", "pc"]:
                return "desktop_primary"
            else:
                return "other"
        except Exception as e:
            logger.error(f"Error calculating device segment: {e}")
            return "unknown"

    def _calculate_traffic_source_segment(self, user: Dict[str, Any]) -> str:
        """Calculate traffic source segment based on referrer data"""
        try:
            traffic_source = user.get("trafficSource", "").lower()
            referrer_type = user.get("referrerType", "").lower()

            if not traffic_source or traffic_source == "unknown":
                return "unknown"

            # Traffic source segmentation
            if traffic_source in ["organic", "search"]:
                return "organic_search"
            elif traffic_source in ["social", "facebook", "instagram", "twitter"]:
                return "social_media"
            elif traffic_source in ["email", "newsletter"]:
                return "email_marketing"
            elif traffic_source in ["paid", "advertising", "ads"]:
                return "paid_advertising"
            elif traffic_source in ["direct", "direct_traffic"]:
                return "direct_traffic"
            elif traffic_source in ["referral", "referrer"]:
                return "referral"
            else:
                return "other"
        except Exception as e:
            logger.error(f"Error calculating traffic source segment: {e}")
            return "unknown"

    def _calculate_content_quality_segment(self, product: Dict[str, Any]) -> str:
        """Calculate content quality segment based on product content data"""
        try:
            content_richness = int(product.get("contentRichnessScore", 0))
            description_length = int(product.get("descriptionLength", 0))
            description_html_length = int(product.get("descriptionHtmlLength", 0))

            # High quality content
            if content_richness > 80 and description_length > 200:
                return "high_quality"
            elif content_richness > 60 and description_length > 100:
                return "medium_quality"
            elif content_richness > 40 and description_length > 50:
                return "basic_quality"
            else:
                return "low_quality"
        except Exception as e:
            logger.error(f"Error calculating content quality segment: {e}")
            return "unknown"

    def _calculate_product_lifecycle_segment(self, product: Dict[str, Any]) -> str:
        """Calculate product lifecycle segment based on age and update frequency"""
        try:
            product_age = product.get("productAge")
            update_frequency = float(product.get("updateFrequency", 0))

            if product_age is None:
                return "unknown"

            # Lifecycle segmentation
            if product_age < 30:  # Less than 30 days
                return "new_product"
            elif product_age < 90:  # Less than 3 months
                return "recent_product"
            elif product_age < 365:  # Less than 1 year
                return "established_product"
            elif update_frequency > 0.5:  # Frequently updated
                return "active_product"
            else:
                return "mature_product"
        except Exception as e:
            logger.error(f"Error calculating product lifecycle segment: {e}")
            return "unknown"

    def _calculate_availability_segment(self, product: Dict[str, Any]) -> str:
        """Calculate availability segment based on inventory and status data"""
        try:
            availability_score = float(product.get("availabilityScore", 0))
            status_stability = float(product.get("statusStability", 0))
            total_inventory = int(product.get("totalInventory", 0))

            # High availability
            if (
                availability_score > 80
                and status_stability > 80
                and total_inventory > 10
            ):
                return "high_availability"
            elif (
                availability_score > 60
                and status_stability > 60
                and total_inventory > 0
            ):
                return "medium_availability"
            elif availability_score > 40 and status_stability > 40:
                return "low_availability"
            else:
                return "unavailable"
        except Exception as e:
            logger.error(f"Error calculating availability segment: {e}")
            return "unknown"
