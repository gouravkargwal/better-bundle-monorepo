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
from ...generators.base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductFeatureComputer(BaseFeatureGenerator):
    """Feature generator for product features"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def compute(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            # Get data from context
            product_data = data.get("product_data", {})
            orders = data.get("orders", [])
            user_interactions = data.get("user_interactions", [])

            # Compute 30-day metrics
            metrics_30d = self._compute_30day_metrics(
                product_id, orders, user_interactions, product_id_mapping
            )

            logger.info(f"Metrics 30d: {metrics_30d}")

            # # Compute conversion metrics
            # conversion_metrics = self._compute_conversion_metrics(metrics_30d)

            # # Compute temporal metrics
            # temporal_metrics = self._compute_temporal_metrics(
            #     product_id, orders, behavioral_events, product_id_mapping
            # )

            # Compute price and inventory metrics
            # price_inventory_metrics = self._compute_price_inventory_metrics(
            #     product_data, orders
            # )

            # Compute metadata scores
            # metadata_scores = self._compute_metadata_scores(product_data)

            # Compute popularity and trending scores
            # popularity_trending = self._compute_popularity_trending_scores(
            #     metrics_30d, temporal_metrics
            # )

            # Compute refund metrics (NEW)
            # refund_metrics = self._compute_refund_metrics(
            #     product_id, orders, product_id_mapping
            # )

            # Compute enhanced features from new data
            # enhanced_metadata_scores = self._compute_enhanced_metadata_scores(
            #     product_data
            # )
            # seo_features = self._compute_seo_features(product_data)
            # media_features = self._compute_media_features(product_data)
            # store_integration_features = self._compute_store_integration_features(
            #     product_data
            # )

            # NEW: Compute enhanced features using previously unused fields
            # content_quality_features = self._compute_content_quality_features(
            #     product_data
            # )
            # product_lifecycle_features = self._compute_product_lifecycle_features(
            #     product_data
            # )
            # category_features = self._compute_category_features(product_data)
            # availability_features = self._compute_availability_features(product_data)

            # features = {
            #     "shop_id": shop_id,
            #     "product_id": product_id,
            #     # 30-day metrics
            #     "view_count_30d": metrics_30d["view_count"],
            #     "unique_viewers_30d": metrics_30d["unique_viewers"],
            #     "cart_add_count_30d": metrics_30d["cart_add_count"],
            #     "cart_view_count_30d": metrics_30d["cart_view_count"],
            #     "cart_remove_count_30d": metrics_30d["cart_remove_count"],
            #     "purchase_count_30d": metrics_30d["purchase_count"],
            #     "unique_purchasers_30d": metrics_30d["unique_purchasers"],
            #     # Conversion metrics
            #     "view_to_cart_rate": conversion_metrics["view_to_cart_rate"],
            #     "cart_to_purchase_rate": conversion_metrics["cart_to_purchase_rate"],
            #     "overall_conversion_rate": conversion_metrics[
            #         "overall_conversion_rate"
            #     ],
            #     "cart_abandonment_rate": conversion_metrics["cart_abandonment_rate"],
            #     "cart_modification_rate": conversion_metrics["cart_modification_rate"],
            #     "cart_view_to_purchase_rate": conversion_metrics[
            #         "cart_view_to_purchase_rate"
            #     ],
            #     # Temporal metrics
            #     "last_viewed_at": temporal_metrics["last_viewed_at"],
            #     "last_purchased_at": temporal_metrics["last_purchased_at"],
            #     "first_purchased_at": temporal_metrics["first_purchased_at"],
            #     "days_since_first_purchase": temporal_metrics[
            #         "days_since_first_purchase"
            #     ],
            #     "days_since_last_purchase": temporal_metrics[
            #         "days_since_last_purchase"
            #     ],
            #     # Price & Inventory
            #     "avg_selling_price": price_inventory_metrics["avg_selling_price"],
            #     "price_variance": price_inventory_metrics["price_variance"],
            #     "total_inventory": price_inventory_metrics["total_inventory"],
            #     "inventory_turnover": price_inventory_metrics["inventory_turnover"],
            #     "stock_velocity": price_inventory_metrics["stock_velocity"],
            #     "price_tier": price_inventory_metrics["price_tier"],
            #     # Enhanced metadata scores
            #     "variant_complexity": metadata_scores["variant_complexity"],
            #     "image_richness": metadata_scores["image_richness"],
            #     "tag_diversity": metadata_scores["tag_diversity"],
            #     "metafield_utilization": metadata_scores["metafield_utilization"],
            #     # New enhanced features
            #     "media_richness": enhanced_metadata_scores["media_richness"],
            #     "seo_optimization": seo_features["seo_optimization"],
            #     "seo_title_length": seo_features["seo_title_length"],
            #     "seo_description_length": seo_features["seo_description_length"],
            #     "has_video_content": media_features["has_video_content"],
            #     "has_3d_content": media_features["has_3d_content"],
            #     "media_count": media_features["media_count"],
            #     "has_online_store_url": store_integration_features[
            #         "has_online_store_url"
            #     ],
            #     "has_preview_url": store_integration_features["has_preview_url"],
            #     "has_custom_template": store_integration_features[
            #         "has_custom_template"
            #     ],
            #     # Computed scores
            #     "popularity_score": popularity_trending["popularity_score"],
            #     "trending_score": popularity_trending["trending_score"],
            #     # Refund metrics (NEW)
            #     "refunded_orders": refund_metrics["refunded_orders"],
            #     "refund_rate": refund_metrics["refund_rate"],
            #     "total_refunded_amount": refund_metrics["total_refunded_amount"],
            #     "net_revenue": refund_metrics["net_revenue"],
            #     "refund_risk_score": refund_metrics["refund_risk_score"],
            #     # NEW: Enhanced features using previously unused fields
            #     "content_richness_score": content_quality_features[
            #         "content_richness_score"
            #     ],
            #     "description_length": content_quality_features["description_length"],
            #     "description_html_length": content_quality_features[
            #         "description_html_length"
            #     ],
            #     "product_age": product_lifecycle_features["product_age"],
            #     "last_updated_days": product_lifecycle_features["last_updated_days"],
            #     "update_frequency": product_lifecycle_features["update_frequency"],
            #     "product_type": category_features["product_type"],
            #     "category_complexity": category_features["category_complexity"],
            #     "availability_score": availability_features["availability_score"],
            #     "status_stability": availability_features["status_stability"],
            #     "last_computed_at": now_utc(),
            # }

            # logger.debug(
            #     f"Computed product features for product: {product_id} - "
            #     f"Views: {features['view_count_30d']}, Purchases: {features['purchase_count_30d']}"
            # )

            # return features

        except Exception as e:
            logger.error(f"Failed to compute product features: {str(e)}")
            # return self._get_default_features(shop_id, product_id)

    def _compute_30day_metrics(
        self,
        product_id: str,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
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

    def _compute_metadata_scores(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute product metadata richness scores (0-1 normalized)"""

        # Compute counts from actual data (proper place for this computation)
        variants = product_data.get("variants", [])
        variant_count = len(variants) if isinstance(variants, list) else 0
        variant_complexity = min(variant_count / 10.0, 1.0)  # Normalize to 0-1

        images = product_data.get("images", [])
        image_count = len(images) if isinstance(images, list) else 0
        image_richness = min(image_count / 5.0, 1.0)  # Normalize to 0-1

        tags = product_data.get("tags", [])
        tag_count = len(tags) if isinstance(tags, list) else 0
        tag_diversity = min(tag_count / 10.0, 1.0)  # Normalize to 0-1

        # Metafield utilization (data already parsed from database)
        metafields = product_data.get("metafields", [])

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
            "variant_complexity": None,
            "image_richness": None,
            "tag_diversity": None,
            "metafield_utilization": None,
            "media_richness": 0,
            "seo_optimization": 0,
            "seo_title_length": 0,
            "seo_description_length": 0,
            "has_video_content": False,
            "has_3d_content": False,
            "media_count": 0,
            "has_online_store_url": False,
            "has_preview_url": False,
            "has_custom_template": False,
            "popularity_score": 0.0,
            "trending_score": 0.0,
            # Refund metrics (NEW)
            "refunded_orders": 0,
            "refund_rate": 0.0,
            "total_refunded_amount": 0.0,
            "net_revenue": 0.0,
            "refund_risk_score": 0.0,
            # NEW: Enhanced features using previously unused fields
            "content_richness_score": 0,
            "description_length": 0,
            "description_html_length": 0,
            "product_age": 0,
            "last_updated_days": 0,
            "update_frequency": 0.0,
            "product_type": "",
            "category_complexity": 0,
            "availability_score": 0,
            "status_stability": 0,
            "last_computed_at": now_utc(),
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
            seo_title = product_data.get("seo_title", "")
            seo_description = product_data.get("seo_description", "")

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
                "has_online_store_url": bool(product_data.get("online_store_url")),
                "has_preview_url": bool(product_data.get("online_store_preview_url")),
                "has_custom_template": bool(product_data.get("template_suffix")),
            }
        except Exception as e:
            logger.error(f"Error computing store integration features: {str(e)}")
            return {
                "has_online_store_url": False,
                "has_preview_url": False,
                "has_custom_template": False,
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
                    "refunded_orders": 0,
                    "refund_rate": 0.0,
                    "total_refunded_amount": 0.0,
                    "net_revenue": 0.0,
                    "refund_risk_score": 0.0,
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

            # Calculate refund risk score (0-100, higher = more risky)
            refund_risk_score = 0.0
            if total_orders > 0:
                if refund_rate > 0.5:  # More than 50% refund rate
                    refund_risk_score = 90
                elif refund_rate > 0.25:  # More than 25% refund rate
                    refund_risk_score = 70
                elif refund_rate > 0.1:  # More than 10% refund rate
                    refund_risk_score = 50
                elif refund_rate > 0.05:  # More than 5% refund rate
                    refund_risk_score = 30
                elif refund_rate > 0:  # Any refunds
                    refund_risk_score = 10

            return {
                "refunded_orders": refunded_orders,
                "refund_rate": round(refund_rate, 3),
                "total_refunded_amount": round(total_refunded_amount, 2),
                "net_revenue": round(net_revenue, 2),
                "refund_risk_score": refund_risk_score,
            }

        except Exception as e:
            logger.error(f"Failed to compute refund metrics: {str(e)}")
            return {
                "refunded_orders": 0,
                "refund_rate": 0.0,
                "total_refunded_amount": 0.0,
                "net_revenue": 0.0,
                "refund_risk_score": 0.0,
            }

    def _compute_content_quality_features(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute content quality features using previously unused fields"""
        try:
            # Description analysis (currently unused)
            description = product_data.get("description", "")
            description_html = product_data.get("description_html", "")

            description_length = len(description) if description else 0
            description_html_length = len(description_html) if description_html else 0

            # Content richness score (0-100)
            content_richness_score = 0
            if description_length > 0:
                content_richness_score += min(
                    description_length / 10, 50
                )  # Max 50 points for description
            if description_html_length > 0:
                content_richness_score += min(
                    description_html_length / 20, 30
                )  # Max 30 points for HTML
            if description_length > 100 and description_html_length > 50:
                content_richness_score += 20  # Bonus for rich content

            return {
                "content_richness_score": min(content_richness_score, 100),
                "description_length": description_length,
                "description_html_length": description_html_length,
            }
        except Exception as e:
            logger.error(f"Error computing content quality features: {str(e)}")
            return {
                "content_richness_score": 0,
                "description_length": 0,
                "description_html_length": 0,
            }

    def _compute_product_lifecycle_features(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute product lifecycle features using previously unused fields"""
        try:
            created_at = product_data.get("created_at")
            updated_at = product_data.get("updated_at")

            product_age = 0
            last_updated_days = 0
            update_frequency = 0.0

            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                product_age = (now_utc() - created_at).days

            if updated_at:
                if isinstance(updated_at, str):
                    updated_at = datetime.datetime.fromisoformat(
                        updated_at.replace("Z", "+00:00")
                    )
                last_updated_days = (now_utc() - updated_at).days

                # Calculate update frequency (updates per month)
                if created_at and updated_at > created_at:
                    days_since_creation = (updated_at - created_at).days
                    if days_since_creation > 0:
                        update_frequency = (
                            30.0 / days_since_creation
                        )  # Updates per month

            return {
                "product_age": product_age,
                "last_updated_days": last_updated_days,
                "update_frequency": round(update_frequency, 2),
            }
        except Exception as e:
            logger.error(f"Error computing product lifecycle features: {str(e)}")
            return {
                "product_age": 0,
                "last_updated_days": 0,
                "update_frequency": 0.0,
            }

    def _compute_category_features(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute category features using previously unused fields"""
        try:
            product_type = product_data.get("product_type", "")

            # Category complexity score based on product type
            category_complexity = 0
            if product_type:
                # Simple categorization based on common product types
                if any(
                    keyword in product_type.lower()
                    for keyword in ["electronics", "technology", "computer"]
                ):
                    category_complexity = 80  # High complexity
                elif any(
                    keyword in product_type.lower()
                    for keyword in ["clothing", "fashion", "apparel"]
                ):
                    category_complexity = 60  # Medium-high complexity
                elif any(
                    keyword in product_type.lower()
                    for keyword in ["book", "media", "digital"]
                ):
                    category_complexity = 40  # Medium complexity
                elif any(
                    keyword in product_type.lower()
                    for keyword in ["food", "beverage", "consumable"]
                ):
                    category_complexity = 30  # Low-medium complexity
                else:
                    category_complexity = 50  # Default medium complexity

            return {
                "product_type": product_type,
                "category_complexity": category_complexity,
            }
        except Exception as e:
            logger.error(f"Error computing category features: {str(e)}")
            return {
                "product_type": "",
                "category_complexity": 0,
            }

    def _compute_availability_features(
        self, product_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute availability features using previously unused fields"""
        try:
            status = product_data.get("status", "")
            is_active = product_data.get("is_active", True)

            # Availability score (0-100)
            availability_score = 0
            if is_active:
                availability_score += 50  # Base score for active products
            if status and status.upper() == "ACTIVE":
                availability_score += 30  # Bonus for explicit active status
            elif status and status.upper() == "DRAFT":
                availability_score += 10  # Lower score for draft products
            elif status and status.upper() == "ARCHIVED":
                availability_score = 0  # No score for archived products

            # Status stability (how stable the product status is)
            status_stability = 100 if status and status.upper() == "ACTIVE" else 50

            return {
                "availability_score": min(availability_score, 100),
                "status_stability": status_stability,
            }
        except Exception as e:
            logger.error(f"Error computing availability features: {str(e)}")
            return {
                "availability_score": 0,
                "status_stability": 0,
            }
