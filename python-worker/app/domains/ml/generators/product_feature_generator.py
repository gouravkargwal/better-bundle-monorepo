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

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for product features"""

    async def generate_features(
        self,
        shop_id: str,
        product_id: str,
        context: Dict[str, Any],
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
            collections = context.get("collections", [])

            # Compute 30-day metrics
            metrics_30d = self._compute_30day_metrics(
                product_id, orders, behavioral_events
            )

            # Compute conversion metrics
            conversion_metrics = self._compute_conversion_metrics(metrics_30d)

            # Compute temporal metrics
            temporal_metrics = self._compute_temporal_metrics(
                product_id, orders, behavioral_events
            )

            # Compute price and inventory metrics
            price_inventory_metrics = self._compute_price_inventory_metrics(
                product_data, orders
            )

            # Compute metadata scores
            metadata_scores = self._compute_metadata_scores(product_data)

            # Compute popularity and trending scores
            popularity_trending = self._compute_popularity_trending_scores(
                metrics_30d, temporal_metrics
            )

            # Compute enhanced features from new data
            enhanced_metadata_scores = self._compute_enhanced_metadata_scores(
                product_data
            )
            seo_features = self._compute_seo_features(product_data)
            media_features = self._compute_media_features(product_data)
            store_integration_features = self._compute_store_integration_features(
                product_data
            )

            features = {
                "shopId": shop_id,
                "productId": product_id,
                # 30-day metrics
                "viewCount30d": metrics_30d["view_count"],
                "uniqueViewers30d": metrics_30d["unique_viewers"],
                "cartAddCount30d": metrics_30d["cart_add_count"],
                "cartViewCount30d": metrics_30d["cart_view_count"],
                "cartRemoveCount30d": metrics_30d["cart_remove_count"],
                "purchaseCount30d": metrics_30d["purchase_count"],
                "uniquePurchasers30d": metrics_30d["unique_purchasers"],
                # Conversion metrics
                "viewToCartRate": conversion_metrics["view_to_cart_rate"],
                "cartToPurchaseRate": conversion_metrics["cart_to_purchase_rate"],
                "overallConversionRate": conversion_metrics["overall_conversion_rate"],
                "cartAbandonmentRate": conversion_metrics["cart_abandonment_rate"],
                "cartModificationRate": conversion_metrics["cart_modification_rate"],
                "cartViewToPurchaseRate": conversion_metrics[
                    "cart_view_to_purchase_rate"
                ],
                # Temporal metrics
                "lastViewedAt": temporal_metrics["last_viewed_at"],
                "lastPurchasedAt": temporal_metrics["last_purchased_at"],
                "firstPurchasedAt": temporal_metrics["first_purchased_at"],
                "daysSinceFirstPurchase": temporal_metrics["days_since_first_purchase"],
                "daysSinceLastPurchase": temporal_metrics["days_since_last_purchase"],
                # Price & Inventory
                "avgSellingPrice": price_inventory_metrics["avg_selling_price"],
                "priceVariance": price_inventory_metrics["price_variance"],
                "totalInventory": price_inventory_metrics["total_inventory"],
                "inventoryTurnover": price_inventory_metrics["inventory_turnover"],
                "stockVelocity": price_inventory_metrics["stock_velocity"],
                "priceTier": price_inventory_metrics["price_tier"],
                # Enhanced metadata scores
                "variantComplexity": metadata_scores["variant_complexity"],
                "imageRichness": metadata_scores["image_richness"],
                "tagDiversity": metadata_scores["tag_diversity"],
                "metafieldUtilization": metadata_scores["metafield_utilization"],
                # New enhanced features
                "mediaRichness": enhanced_metadata_scores["media_richness"],
                "seoOptimization": seo_features["seo_optimization"],
                "seoTitleLength": seo_features["seo_title_length"],
                "seoDescriptionLength": seo_features["seo_description_length"],
                "hasVideoContent": media_features["has_video_content"],
                "has3DContent": media_features["has_3d_content"],
                "mediaCount": media_features["media_count"],
                "hasOnlineStoreUrl": store_integration_features["has_online_store_url"],
                "hasPreviewUrl": store_integration_features["has_preview_url"],
                "hasCustomTemplate": store_integration_features["has_custom_template"],
                # Computed scores
                "popularityScore": popularity_trending["popularity_score"],
                "trendingScore": popularity_trending["trending_score"],
                "lastComputedAt": now_utc(),
            }

            logger.debug(
                f"Computed product features for product: {product_id} - "
                f"Views: {features['viewCount30d']}, Purchases: {features['purchaseCount30d']}"
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
                if event_product_id == product_id:
                    recent_events.append(event)

        # Count views and unique viewers
        view_count = 0
        unique_viewers = set()
        cart_add_count = 0
        cart_view_count = 0
        cart_remove_count = 0

        for event in recent_events:
            event_type = event.get("eventType", "")

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
            order_date = self._parse_date(order.get("orderDate"))
            if order_date and order_date >= thirty_days_ago:
                # Check if this order contains the product
                for line_item in order.get("lineItems", []):
                    item_product_id = self._extract_product_id_from_line_item(line_item)
                    if item_product_id == product_id:
                        recent_orders.append(order)
                        customer_id = order.get("customerId")
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
    ) -> Dict[str, Any]:
        """Compute temporal metrics"""

        # Find last view
        last_viewed_at = None
        for event in behavioral_events:
            if event.get("eventType") == "product_viewed":
                event_product_id = self._extract_product_id_from_event(event)
                if event_product_id == product_id:
                    event_time = self._parse_date(event.get("timestamp"))
                    if event_time:
                        if not last_viewed_at or event_time > last_viewed_at:
                            last_viewed_at = event_time

        # Find first and last purchase
        first_purchased_at = None
        last_purchased_at = None

        for order in orders:
            for line_item in order.get("lineItems", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                if item_product_id == product_id:
                    order_date = self._parse_date(order.get("orderDate"))
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
            for line_item in order.get("lineItems", []):
                item_product_id = self._extract_product_id_from_line_item(line_item)
                if item_product_id == product_data.get("productId"):
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
        total_inventory = int(product_data.get("totalInventory", 0))
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

    def _compute_metadata_scores(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute product metadata richness scores (0-1 normalized)"""

        # Variant complexity
        variants = product_data.get("variants", [])
        if isinstance(variants, str):
            try:
                import json

                variants = json.loads(variants)
            except:
                variants = []

        variant_count = len(variants) if isinstance(variants, list) else 0
        variant_complexity = min(variant_count / 10.0, 1.0)  # Normalize to 0-1

        # Image richness
        images = product_data.get("images", [])
        if isinstance(images, str):
            try:
                import json

                images = json.loads(images)
            except:
                images = []

        image_count = len(images) if isinstance(images, list) else 0
        image_richness = min(image_count / 5.0, 1.0)  # Normalize to 0-1

        # Tag diversity
        tags = product_data.get("tags", [])
        if isinstance(tags, str):
            try:
                import json

                tags = json.loads(tags)
            except:
                tags = []

        tag_count = len(tags) if isinstance(tags, list) else 0
        tag_diversity = min(tag_count / 10.0, 1.0)  # Normalize to 0-1

        # Metafield utilization
        metafields = product_data.get("metafields", [])
        if isinstance(metafields, str):
            try:
                import json

                metafields = json.loads(metafields)
            except:
                metafields = []

        metafield_count = len(metafields) if isinstance(metafields, list) else 0
        metafield_utilization = min(metafield_count / 5.0, 1.0)  # Normalize to 0-1

        return {
            "variant_complexity": round(variant_complexity, 3),
            "image_richness": round(image_richness, 3),
            "tag_diversity": round(tag_diversity, 3),
            "metafield_utilization": round(metafield_utilization, 3),
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
        """Extract product ID from behavioral event"""
        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if event_type == "product_viewed":
            product_variant = event_data.get("data", {}).get("productVariant", {})
            product = product_variant.get("product", {})
            return self._extract_id_from_gid(product.get("id", ""))

        elif event_type == "product_added_to_cart":
            cart_line = event_data.get("data", {}).get("cartLine", {})
            merchandise = cart_line.get("merchandise", {})
            product = merchandise.get("product", {})
            return self._extract_id_from_gid(product.get("id", ""))

        return None

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        if "productId" in line_item:
            return str(line_item["productId"])

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            if isinstance(product, dict):
                return self._extract_id_from_gid(product.get("id", ""))

        return ""

    def _extract_session_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from event"""
        event_data = event.get("eventData", {})
        return event_data.get("clientId")

    def _extract_id_from_gid(self, gid: str) -> str:
        """Extract numeric ID from Shopify GID"""
        if not gid:
            return ""
        if "/" in gid:
            return gid.split("/")[-1]
        return gid

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
            "shopId": shop_id,
            "productId": product_id,
            "viewCount30d": 0,
            "uniqueViewers30d": 0,
            "cartAddCount30d": 0,
            "purchaseCount30d": 0,
            "uniquePurchasers30d": 0,
            "viewToCartRate": None,
            "cartToPurchaseRate": None,
            "overallConversionRate": None,
            "lastViewedAt": None,
            "lastPurchasedAt": None,
            "firstPurchasedAt": None,
            "daysSinceFirstPurchase": None,
            "daysSinceLastPurchase": None,
            "avgSellingPrice": None,
            "priceVariance": None,
            "totalInventory": None,
            "inventoryTurnover": None,
            "stockVelocity": None,
            "priceTier": None,
            "variantComplexity": None,
            "imageRichness": None,
            "tagDiversity": None,
            "metafieldUtilization": None,
            "mediaRichness": 0,
            "seoOptimization": 0,
            "seoTitleLength": 0,
            "seoDescriptionLength": 0,
            "hasVideoContent": False,
            "has3DContent": False,
            "mediaCount": 0,
            "hasOnlineStoreUrl": False,
            "hasPreviewUrl": False,
            "hasCustomTemplate": False,
            "popularityScore": 0.0,
            "trendingScore": 0.0,
            "lastComputedAt": now_utc(),
        }

    def _compute_enhanced_metadata_scores(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute enhanced metadata scores from new product fields"""
        try:
            # Media richness score based on media content
            media_data = product_data.get("media", [])
            media_richness = 0

            if media_data:
                # Count different types of media
                video_count = sum(
                    1
                    for media in media_data
                    if media.get("node", {}).get("__typename") == "Video"
                )
                model_3d_count = sum(
                    1
                    for media in media_data
                    if media.get("node", {}).get("__typename") == "Model3d"
                )
                image_count = sum(
                    1
                    for media in media_data
                    if media.get("node", {}).get("__typename") == "MediaImage"
                )

                # Calculate richness score (0-100)
                media_richness = min(
                    100, (video_count * 30 + model_3d_count * 40 + image_count * 10)
                )

            return {
                "media_richness": media_richness,
            }
        except Exception as e:
            logger.error(f"Error computing enhanced metadata scores: {str(e)}")
            return {"media_richness": 0}

    def _compute_seo_features(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute SEO-related features"""
        try:
            seo_title = product_data.get("seoTitle", "")
            seo_description = product_data.get("seoDescription", "")

            # SEO optimization score (0-100)
            seo_optimization = 0
            if seo_title:
                seo_optimization += 30
            if seo_description:
                seo_optimization += 30
            if seo_title and len(seo_title) >= 30 and len(seo_title) <= 60:
                seo_optimization += 20  # Optimal title length
            if (
                seo_description
                and len(seo_description) >= 120
                and len(seo_description) <= 160
            ):
                seo_optimization += 20  # Optimal description length

            return {
                "seo_optimization": seo_optimization,
                "seo_title_length": len(seo_title) if seo_title else 0,
                "seo_description_length": (
                    len(seo_description) if seo_description else 0
                ),
            }
        except Exception as e:
            logger.error(f"Error computing SEO features: {str(e)}")
            return {
                "seo_optimization": 0,
                "seo_title_length": 0,
                "seo_description_length": 0,
            }

    def _compute_media_features(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute media-related features"""
        try:
            media_data = product_data.get("media", [])

            has_video = False
            has_3d = False
            media_count = len(media_data)

            for media in media_data:
                media_type = media.get("node", {}).get("__typename", "")
                if media_type == "Video":
                    has_video = True
                elif media_type == "Model3d":
                    has_3d = True

            return {
                "has_video_content": has_video,
                "has_3d_content": has_3d,
                "media_count": media_count,
            }
        except Exception as e:
            logger.error(f"Error computing media features: {str(e)}")
            return {
                "has_video_content": False,
                "has_3d_content": False,
                "media_count": 0,
            }

    def _compute_store_integration_features(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute store integration features"""
        try:
            return {
                "has_online_store_url": bool(product_data.get("onlineStoreUrl")),
                "has_preview_url": bool(product_data.get("onlineStorePreviewUrl")),
                "has_custom_template": bool(product_data.get("templateSuffix")),
            }
        except Exception as e:
            logger.error(f"Error computing store integration features: {str(e)}")
            return {
                "has_online_store_url": False,
                "has_preview_url": False,
                "has_custom_template": False,
            }
