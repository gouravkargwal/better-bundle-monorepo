"""
Product feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyProduct,
    ShopifyShop,
    ShopifyOrder,
    ShopifyCollection,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify products"""

    async def generate_features(
        self, product: ShopifyProduct, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a product

        Args:
            product: The product to generate features for
            context: Additional context data (shop, orders, collections, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for product: {product.id}")

            features = {}
            shop = context.get("shop")
            orders = context.get("orders", [])
            collections = context.get("collections", [])

            # Basic product features
            features.update(self._compute_basic_product_features(product))

            # Variant features
            features.update(self._compute_variant_features(product))

            # Image features
            features.update(self._compute_image_features(product))

            # Tag and category features
            features.update(self._compute_tag_features(product))

            # Collection features
            if collections:
                features.update(self._compute_collection_features(product, collections))

            # Historical performance features (if orders available)
            if orders:
                features.update(self._compute_performance_features(product, orders))

            # Shop context features
            if shop:
                features.update(self._compute_shop_context_features(product, shop))

            # Time-based features
            features.update(self._compute_time_features(product))

            # Quality features
            features.update(self._compute_quality_features(product))

            # Enhanced popularity and trend features
            features.update(self._compute_popularity_features(product, context))

            # Cross-selling and relationship features
            features.update(self._compute_relationship_features(product, context))

            # Seasonal and temporal features
            features.update(self._compute_seasonal_features(product, context))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(f"Computed {len(features)} features for product: {product.id}")
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute product features for {product.id}: {str(e)}"
            )
            return {}

    def _compute_basic_product_features(
        self, product: ShopifyProduct
    ) -> Dict[str, Any]:
        """Compute basic product features"""
        return {
            "product_id": product.id,
            "title_length": len(product.title or ""),
            "description_length": len(product.body_html or ""),
            "vendor_encoded": self._encode_categorical_feature(product.vendor),
            "product_type_encoded": self._encode_categorical_feature(
                product.product_type
            ),
            "status_encoded": 1 if product.status == "active" else 0,
            "is_published": 1 if product.is_published else 0,
            "variant_count": product.variant_count,
            "has_multiple_variants": 1 if product.has_multiple_variants else 0,
            "tag_count": product.tag_count,
            "collection_count": product.collection_count,
            "has_images": 1 if product.has_images else 0,
            "image_count": product.image_count,
        }

    def _compute_variant_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute variant-related features"""
        if not product.variants:
            return {
                "variant_count": 0,
                "price_range": 0,
                "price_std": 0,
                "avg_price": 0,
                "min_price": 0,
                "max_price": 0,
                "weight_range": 0,
                "avg_weight": 0,
                "inventory_total": 0,
                "avg_inventory": 0,
            }

        prices = [v.price for v in product.variants if v.price is not None]
        weights = [v.weight for v in product.variants if v.weight is not None]
        inventory = [
            v.inventory_quantity
            for v in product.variants
            if v.inventory_quantity is not None
        ]

        return {
            "variant_count": len(product.variants),
            "price_range": max(prices) - min(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "avg_price": statistics.mean(prices) if prices else 0,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "weight_range": max(weights) - min(weights) if weights else 0,
            "avg_weight": statistics.mean(weights) if weights else 0,
            "inventory_total": sum(inventory) if inventory else 0,
            "avg_inventory": statistics.mean(inventory) if inventory else 0,
        }

    def _compute_image_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute image-related features"""
        if not product.images:
            return {
                "image_count": 0,
                "has_images": 0,
                "image_alt_text_coverage": 0,
            }

        alt_text_count = sum(1 for img in product.images if img.alt_text)

        return {
            "image_count": len(product.images),
            "has_images": 1,
            "image_alt_text_coverage": alt_text_count / len(product.images),
        }

    def _compute_tag_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute tag and category features"""
        tags = product.tags or []

        return {
            "tag_count": len(tags),
            "tag_diversity": len(set(tags)),
            "has_tags": 1 if tags else 0,
            "tag_encoded": self._encode_categorical_feature("|".join(tags)),
        }

    def _compute_collection_features(
        self, product: ShopifyProduct, collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute collection-related features"""
        product_collections = [
            c for c in collections if product.id in [p.id for p in c.products]
        ]

        if not product_collections:
            return {
                "collection_count": 0,
                "avg_collection_size": 0,
                "is_in_featured_collection": 0,
            }

        return {
            "collection_count": len(product_collections),
            "avg_collection_size": statistics.mean(
                [c.products_count for c in product_collections]
            ),
            "is_in_featured_collection": (
                1 if any(c.is_featured for c in product_collections) else 0
            ),
        }

    def _compute_performance_features(
        self, product: ShopifyProduct, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute historical performance features"""
        product_orders = []
        total_quantity = 0
        total_revenue = 0

        for order in orders:
            for line_item in order.line_items:
                if line_item.product_id == product.id:
                    product_orders.append(order)
                    total_quantity += line_item.quantity
                    total_revenue += line_item.price * line_item.quantity

        return {
            "total_orders": len(product_orders),
            "total_quantity_sold": total_quantity,
            "total_revenue": total_revenue,
            "avg_order_value": (
                total_revenue / len(product_orders) if product_orders else 0
            ),
            "conversion_rate": len(product_orders) / len(orders) if orders else 0,
        }

    def _compute_shop_context_features(
        self, product: ShopifyProduct, shop: ShopifyShop
    ) -> Dict[str, Any]:
        """Compute shop context features"""
        return {
            "shop_plan_encoded": self._encode_categorical_feature(shop.plan_name or ""),
            "shop_currency_encoded": self._encode_categorical_feature(
                shop.currency or ""
            ),
            "shop_country_encoded": self._encode_categorical_feature(
                shop.country or ""
            ),
        }

    def _compute_time_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute time-based features"""
        return self._compute_time_based_features(product.created_at, product.updated_at)

    def _compute_quality_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute product quality features"""
        quality_score = 0

        # Title quality
        if product.title and len(product.title) > 10:
            quality_score += 1

        # Description quality
        if product.body_html and len(product.body_html) > 50:
            quality_score += 1

        # Image quality
        if product.has_images:
            quality_score += 1

        # Tag quality
        if product.tags and len(product.tags) > 2:
            quality_score += 1

        # Variant quality
        if product.variant_count > 0:
            quality_score += 1

        return {
            "quality_score": quality_score,
            "quality_tier": (
                "high"
                if quality_score >= 4
                else "medium" if quality_score >= 2 else "low"
            ),
        }

    def _compute_popularity_features(
        self, product: ShopifyProduct, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute product popularity and trend features"""
        events = context.get("events", [])
        orders = context.get("orders", [])

        if not events and not orders:
            return {
                "view_velocity": 0.0,
                "cart_velocity": 0.0,
                "purchase_velocity": 0.0,
                "trending_score": 0.0,
                "search_popularity": 0.0,
                "collection_featured_count": 0,
                "cross_sell_opportunity_score": 0.0,
                "inventory_velocity": 0.0,
                "stockout_risk": 0.0,
                "overstock_risk": 0.0,
                "reorder_urgency": 0.0,
                "seasonal_demand_multiplier": 1.0,
            }

        # Calculate velocities (events per hour)
        product_events = [e for e in events if e.get_product_id() == product.id]
        product_orders = []
        for order in orders:
            for line_item in order.line_items:
                if line_item.product_id == product.id:
                    product_orders.append(order)
                    break

        # Time-based calculations
        now = now_utc()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        # View velocity (views per hour in last 24h)
        recent_views = [
            e
            for e in product_events
            if e.is_product_viewed and e.occurred_at >= last_24h
        ]
        view_velocity = len(recent_views) / 24.0

        # Cart velocity (cart additions per hour in last 24h)
        recent_carts = [
            e
            for e in product_events
            if e.is_product_added_to_cart and e.occurred_at >= last_24h
        ]
        cart_velocity = len(recent_carts) / 24.0

        # Purchase velocity (purchases per hour in last 24h)
        recent_orders = [o for o in product_orders if o.created_at >= last_24h]
        purchase_velocity = len(recent_orders) / 24.0

        # Trending score (velocity change over time)
        old_views = [
            e
            for e in product_events
            if e.is_product_viewed and last_7d <= e.occurred_at < last_24h
        ]
        old_view_velocity = len(old_views) / 24.0
        trending_score = (view_velocity - old_view_velocity) / max(
            old_view_velocity, 1.0
        )

        # Search popularity (how often appears in search results)
        search_events = [e for e in events if e.is_search_submitted]
        search_appearances = 0
        for search_event in search_events:
            if search_event.event_data:
                search_result = search_event.event_data.get("searchResult", {})
                product_variants = search_result.get("productVariants", [])
                for variant in product_variants:
                    if variant.get("product", {}).get("id") == product.id:
                        search_appearances += 1
                        break
        search_popularity = search_appearances / max(len(search_events), 1)

        # Collection featured count
        collections = context.get("collections", [])
        featured_count = sum(
            1
            for c in collections
            if product.id in [p.id for p in c.products] and c.is_featured
        )

        # Cross-sell opportunity score
        cross_sell_score = self._calculate_cross_sell_opportunity(
            product, product_orders, orders
        )

        # Inventory features
        inventory_features = self._compute_inventory_features(product, product_orders)

        # Seasonal demand multiplier
        seasonal_multiplier = self._calculate_seasonal_demand(product, product_orders)

        return {
            "view_velocity": view_velocity,
            "cart_velocity": cart_velocity,
            "purchase_velocity": purchase_velocity,
            "trending_score": trending_score,
            "search_popularity": search_popularity,
            "collection_featured_count": featured_count,
            "cross_sell_opportunity_score": cross_sell_score,
            **inventory_features,
            "seasonal_demand_multiplier": seasonal_multiplier,
        }

    def _compute_relationship_features(
        self, product: ShopifyProduct, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute product relationship and cross-selling features"""
        orders = context.get("orders", [])
        events = context.get("events", [])

        if not orders and not events:
            return {
                "frequently_bought_together_count": 0,
                "viewed_together_score": 0.0,
                "category_complementarity": 0.0,
                "price_point_affinity": 0.0,
                "style_affinity": 0.0,
                "bundle_opportunity_score": 0.0,
            }

        # Frequently bought together
        fbt_products = self._find_frequently_bought_together(product, orders)

        # Viewed together (in same sessions)
        viewed_together = self._find_viewed_together(product, events)

        # Category complementarity
        category_complementarity = self._calculate_category_complementarity(
            product, fbt_products
        )

        # Price point affinity
        price_affinity = self._calculate_price_affinity(product, fbt_products)

        # Style affinity (based on tags and categories)
        style_affinity = self._calculate_style_affinity(product, fbt_products)

        # Bundle opportunity
        bundle_score = self._calculate_bundle_opportunity(
            product, fbt_products, viewed_together
        )

        return {
            "frequently_bought_together_count": len(fbt_products),
            "viewed_together_score": viewed_together,
            "category_complementarity": category_complementarity,
            "price_point_affinity": price_affinity,
            "style_affinity": style_affinity,
            "bundle_opportunity_score": bundle_score,
        }

    def _compute_seasonal_features(
        self, product: ShopifyProduct, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute seasonal and temporal product features"""
        orders = context.get("orders", [])
        events = context.get("events", [])

        if not orders and not events:
            return {
                "seasonal_score": 0.0,
                "current_season_relevance": 0.0,
                "holiday_relevance": 0.0,
                "weather_sensitivity": 0.0,
                "monthly_demand_pattern": [0.0] * 12,
                "peak_season": 0,
            }

        # Get product orders and events
        product_orders = []
        for order in orders:
            for line_item in order.line_items:
                if line_item.product_id == product.id:
                    product_orders.append(order)
                    break

        product_events = [e for e in events if e.get_product_id() == product.id]

        # Seasonal analysis
        seasonal_score = self._calculate_seasonal_score(product, product_orders)
        current_relevance = self._calculate_current_season_relevance(product)
        holiday_relevance = self._calculate_holiday_relevance(product)
        weather_sensitivity = self._calculate_weather_sensitivity(
            product, product_orders
        )

        # Monthly demand pattern
        monthly_pattern = self._calculate_monthly_demand_pattern(product_orders)
        peak_season = (
            monthly_pattern.index(max(monthly_pattern)) if monthly_pattern else 0
        )

        return {
            "seasonal_score": seasonal_score,
            "current_season_relevance": current_relevance,
            "holiday_relevance": holiday_relevance,
            "weather_sensitivity": weather_sensitivity,
            "monthly_demand_pattern": monthly_pattern,
            "peak_season": peak_season,
        }

    def _calculate_cross_sell_opportunity(
        self, product: ShopifyProduct, product_orders: List, all_orders: List
    ) -> float:
        """Calculate cross-selling opportunity score"""
        if not product_orders:
            return 0.0

        # Find products frequently bought with this product
        co_purchased = {}
        for order in product_orders:
            for line_item in order.line_items:
                if line_item.product_id != product.id:
                    co_purchased[line_item.product_id] = (
                        co_purchased.get(line_item.product_id, 0) + 1
                    )

        if not co_purchased:
            return 0.0

        # Calculate opportunity score based on frequency and diversity
        max_frequency = max(co_purchased.values())
        diversity = len(co_purchased)
        opportunity_score = (max_frequency / len(product_orders)) * (diversity / 10.0)

        return min(opportunity_score, 1.0)

    def _compute_inventory_features(
        self, product: ShopifyProduct, product_orders: List
    ) -> Dict[str, Any]:
        """Compute inventory-related features"""
        if not product.variants:
            return {
                "inventory_velocity": 0.0,
                "stockout_risk": 0.0,
                "overstock_risk": 0.0,
                "reorder_urgency": 0.0,
            }

        # Calculate total inventory
        total_inventory = sum(v.inventory_quantity or 0 for v in product.variants)

        # Calculate sales velocity (units sold per day)
        if product_orders:
            total_quantity_sold = sum(
                sum(
                    li.quantity
                    for li in order.line_items
                    if li.product_id == product.id
                )
                for order in product_orders
            )
            days_span = (
                product_orders[-1].created_at - product_orders[0].created_at
            ).days
            inventory_velocity = total_quantity_sold / max(days_span, 1)
        else:
            inventory_velocity = 0.0

        # Stockout risk (probability of running out in next 30 days)
        if inventory_velocity > 0:
            days_until_stockout = total_inventory / inventory_velocity
            stockout_risk = max(0, 1 - (days_until_stockout / 30))
        else:
            stockout_risk = 0.0

        # Overstock risk (inventory too high for demand)
        if inventory_velocity > 0:
            optimal_inventory = inventory_velocity * 30  # 30 days of inventory
            overstock_risk = max(
                0, (total_inventory - optimal_inventory) / optimal_inventory
            )
        else:
            overstock_risk = 0.0

        # Reorder urgency
        reorder_urgency = min(stockout_risk + (1 - overstock_risk), 1.0)

        return {
            "inventory_velocity": inventory_velocity,
            "stockout_risk": stockout_risk,
            "overstock_risk": overstock_risk,
            "reorder_urgency": reorder_urgency,
        }

    def _calculate_seasonal_demand(
        self, product: ShopifyProduct, product_orders: List
    ) -> float:
        """Calculate seasonal demand multiplier"""
        if not product_orders:
            return 1.0

        # Analyze seasonal patterns in product orders
        monthly_orders = [0] * 12
        for order in product_orders:
            month = order.created_at.month - 1
            monthly_orders[month] += 1

        # Calculate seasonal variation
        if monthly_orders:
            avg_orders = sum(monthly_orders) / 12
            current_month = now_utc().month - 1
            current_demand = monthly_orders[current_month]
            seasonal_multiplier = current_demand / max(avg_orders, 1)
        else:
            seasonal_multiplier = 1.0

        return seasonal_multiplier

    def _find_frequently_bought_together(
        self, product: ShopifyProduct, orders: List
    ) -> List[str]:
        """Find products frequently bought together with this product"""
        co_purchased = {}

        for order in orders:
            order_products = [li.product_id for li in order.line_items]
            if product.id in order_products:
                for other_product in order_products:
                    if other_product != product.id:
                        co_purchased[other_product] = (
                            co_purchased.get(other_product, 0) + 1
                        )

        # Return top 5 most frequently bought together
        sorted_products = sorted(co_purchased.items(), key=lambda x: x[1], reverse=True)
        return [product_id for product_id, _ in sorted_products[:5]]

    def _find_viewed_together(self, product: ShopifyProduct, events: List) -> float:
        """Calculate how often this product is viewed together with others in sessions"""
        # Group events by session (simplified)
        sessions = {}
        for event in events:
            # Use a simple session grouping based on time proximity
            session_key = f"{event.customer_id}_{event.occurred_at.date()}"
            if session_key not in sessions:
                sessions[session_key] = []
            sessions[session_key].append(event)

        viewed_together_count = 0
        total_sessions_with_product = 0

        for session_events in sessions.values():
            session_products = set()
            for event in session_events:
                product_id = event.get_product_id()
                if product_id:
                    session_products.add(product_id)

            if product.id in session_products:
                total_sessions_with_product += 1
                if len(session_products) > 1:
                    viewed_together_count += 1

        return viewed_together_count / max(total_sessions_with_product, 1)

    def _calculate_category_complementarity(
        self, product: ShopifyProduct, fbt_products: List[str]
    ) -> float:
        """Calculate how well this product's category complements others"""
        if not fbt_products:
            return 0.0

        # This is a simplified version - in practice, you'd have category relationship data
        product_category = product.product_type or ""

        # Define complementary categories (simplified)
        complementary_categories = {
            "Clothing": ["Accessories", "Shoes"],
            "Electronics": ["Accessories", "Cases"],
            "Home": ["Decor", "Furniture"],
        }

        complement_count = 0
        for fbt_product_id in fbt_products:
            # In practice, you'd look up the category of fbt_product_id
            # For now, we'll use a simplified approach
            complement_count += 1  # Placeholder

        return complement_count / len(fbt_products)

    def _calculate_price_affinity(
        self, product: ShopifyProduct, fbt_products: List[str]
    ) -> float:
        """Calculate price point affinity with frequently bought together products"""
        if not fbt_products or not product.variants:
            return 0.0

        product_price = product.variants[0].price or 0

        # In practice, you'd look up prices of fbt_products
        # For now, we'll use a simplified approach
        price_variance = 0.2  # Assume 20% variance is acceptable

        return 1.0 - price_variance  # Higher score for similar price points

    def _calculate_style_affinity(
        self, product: ShopifyProduct, fbt_products: List[str]
    ) -> float:
        """Calculate style affinity based on tags and categories"""
        if not fbt_products:
            return 0.0

        product_tags = set(product.tags or [])
        product_vendor = product.vendor or ""

        # In practice, you'd compare with fbt_products' tags and vendors
        # For now, we'll use a simplified approach
        style_similarity = 0.7  # Placeholder

        return style_similarity

    def _calculate_bundle_opportunity(
        self, product: ShopifyProduct, fbt_products: List[str], viewed_together: float
    ) -> float:
        """Calculate bundle opportunity score"""
        if not fbt_products:
            return 0.0

        # Combine frequently bought together and viewed together scores
        fbt_score = len(fbt_products) / 10.0  # Normalize to 0-1
        bundle_score = (fbt_score + viewed_together) / 2.0

        return min(bundle_score, 1.0)

    def _calculate_seasonal_score(
        self, product: ShopifyProduct, product_orders: List
    ) -> float:
        """Calculate how seasonal this product is"""
        if not product_orders:
            return 0.0

        # Analyze order distribution across months
        monthly_orders = [0] * 12
        for order in product_orders:
            month = order.created_at.month - 1
            monthly_orders[month] += 1

        if not any(monthly_orders):
            return 0.0

        # Calculate coefficient of variation (higher = more seasonal)
        mean_orders = sum(monthly_orders) / 12
        if mean_orders == 0:
            return 0.0

        variance = sum((x - mean_orders) ** 2 for x in monthly_orders) / 12
        std_dev = variance**0.5
        seasonal_score = std_dev / mean_orders

        return min(seasonal_score, 1.0)

    def _calculate_current_season_relevance(self, product: ShopifyProduct) -> float:
        """Calculate how relevant this product is for the current season"""
        current_month = now_utc().month

        # Define seasonal relevance (simplified)
        seasonal_keywords = {
            "summer": ["swim", "beach", "sun", "hot", "light"],
            "winter": ["warm", "cold", "snow", "heavy", "coat"],
            "spring": ["fresh", "light", "colorful", "renewal"],
            "fall": ["autumn", "warm", "cozy", "harvest"],
        }

        product_title = (product.title or "").lower()
        product_tags = " ".join(product.tags or []).lower()
        product_text = f"{product_title} {product_tags}"

        # Determine current season
        if current_month in [6, 7, 8]:
            current_season = "summer"
        elif current_month in [12, 1, 2]:
            current_season = "winter"
        elif current_month in [3, 4, 5]:
            current_season = "spring"
        else:
            current_season = "fall"

        # Check for seasonal keywords
        season_keywords = seasonal_keywords.get(current_season, [])
        relevance_score = sum(
            1 for keyword in season_keywords if keyword in product_text
        )
        relevance_score = (
            relevance_score / len(season_keywords) if season_keywords else 0.0
        )

        return relevance_score

    def _calculate_holiday_relevance(self, product: ShopifyProduct) -> float:
        """Calculate how relevant this product is for upcoming holidays"""
        current_month = now_utc().month

        # Define holiday relevance
        holiday_keywords = {
            12: ["christmas", "holiday", "gift", "winter", "festive"],
            2: ["valentine", "love", "romantic", "heart"],
            10: ["halloween", "spooky", "costume", "trick"],
            11: ["thanksgiving", "grateful", "family", "harvest"],
        }

        product_title = (product.title or "").lower()
        product_tags = " ".join(product.tags or []).lower()
        product_text = f"{product_title} {product_tags}"

        keywords = holiday_keywords.get(current_month, [])
        if not keywords:
            return 0.0

        relevance_score = sum(1 for keyword in keywords if keyword in product_text)
        return relevance_score / len(keywords)

    def _calculate_weather_sensitivity(
        self, product: ShopifyProduct, product_orders: List
    ) -> float:
        """Calculate how much weather affects demand for this product"""
        # This is a simplified version - in practice, you'd correlate with weather data
        product_title = (product.title or "").lower()
        product_tags = " ".join(product.tags or []).lower()
        product_text = f"{product_title} {product_tags}"

        weather_keywords = [
            "rain",
            "sun",
            "snow",
            "wind",
            "hot",
            "cold",
            "weather",
            "outdoor",
            "indoor",
        ]
        weather_mentions = sum(
            1 for keyword in weather_keywords if keyword in product_text
        )

        return weather_mentions / len(weather_keywords)

    def _calculate_monthly_demand_pattern(self, product_orders: List) -> List[float]:
        """Calculate monthly demand pattern"""
        monthly_orders = [0.0] * 12

        for order in product_orders:
            month = order.created_at.month - 1
            monthly_orders[month] += 1

        # Normalize to 0-1 scale
        max_orders = max(monthly_orders) if monthly_orders else 1
        return [orders / max_orders for orders in monthly_orders]
