"""
Collection feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics
from datetime import datetime, timedelta
from prisma import Json

from app.core.logging import get_logger

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CollectionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify collections"""

    async def generate_features(
        self, collection: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a collection to match CollectionFeatures schema

        Args:
            collection: The collection to generate features for (from CollectionData)
            context: Additional context data with all required tables:
                - shop: Shop data
                - products: List of ProductData for this collection
                - behavioral_events: List of BehavioralEvents
                - order_data: List of OrderData

        Returns:
            Dictionary of generated features matching CollectionFeatures schema
        """
        try:
            logger.debug(
                f"Computing features for collection: {collection.get('collectionId', 'unknown')}"
            )

            features = {}
            shop = context.get("shop", {})
            products = context.get("products", [])
            behavioral_events = context.get("behavioral_events", [])
            order_data = context.get("order_data", [])

            # Basic collection features
            features.update(self._compute_basic_collection_features(collection, shop))

            # Engagement metrics from behavioral events
            features.update(
                self._compute_engagement_metrics(collection, behavioral_events)
            )

            # Product metrics from products data
            if products:
                features.update(self._compute_product_metrics(collection, products))

            # Performance metrics from orders
            if order_data:
                features.update(
                    self._compute_performance_metrics(collection, order_data, products)
                )
            else:
                # Ensure JSON fields are always set even without order data
                features.update(
                    {
                        "conversionRate": None,
                        "revenueContribution": None,
                        "topProducts": Json([]),
                        "topVendors": Json([]),
                    }
                )

            # SEO and image scores
            features.update(self._compute_seo_score(collection))
            features.update(self._compute_image_score(collection))

            # Performance score (composite)
            features.update(self._compute_performance_score(features))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} features for collection: {collection.get('collectionId', 'unknown')}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute collection features for {collection.get('collectionId', 'unknown')}: {str(e)}"
            )
            return {}

    def _compute_basic_collection_features(
        self, collection: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic collection features"""
        return {
            "shopId": shop.get("id", "") if shop else "",
            "collectionId": collection.get("collectionId", ""),
            "productCount": collection.get("productCount", 0),
            "isAutomated": bool(collection.get("isAutomated", False)),
        }

    def _compute_engagement_metrics(
        self, collection: Dict[str, Any], behavioral_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute engagement metrics from behavioral events (30-day window)"""
        collection_id = collection.get("collectionId", "")
        thirty_days_ago = datetime.now() - timedelta(days=30)

        # Filter events for this collection in last 30 days
        collection_events = []
        for event in behavioral_events:
            event_time = event.get("occurredAt")
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            elif not isinstance(event_time, datetime):
                continue

            if event_time >= thirty_days_ago:
                # Check if event is related to this collection
                event_data = event.get("eventData", {})
                if event_data.get(
                    "collectionId"
                ) == collection_id or collection_id in event_data.get(
                    "collectionIds", []
                ):
                    collection_events.append(event)

        # Calculate metrics
        view_events = [
            e for e in collection_events if e.get("eventType") == "collection_view"
        ]
        click_events = [
            e
            for e in collection_events
            if e.get("eventType") == "product_click_from_collection"
        ]
        bounce_events = [e for e in collection_events if e.get("eventType") == "bounce"]

        view_count = len(view_events)
        unique_viewers = len(
            set(e.get("customerId") for e in view_events if e.get("customerId"))
        )
        click_count = len(click_events)
        bounce_count = len(bounce_events)

        return {
            "viewCount30d": view_count,
            "uniqueViewers30d": unique_viewers,
            "clickThroughRate": (click_count / view_count) if view_count > 0 else None,
            "bounceRate": (bounce_count / view_count) if view_count > 0 else None,
        }

    def _compute_product_metrics(
        self, collection: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute product-related metrics matching schema"""
        collection_id = collection.get("collectionId", "")

        # Filter products that belong to this collection
        collection_products = []
        for product in products:
            collections = product.get("collections", [])
            if isinstance(collections, list):
                collection_ids = [
                    c.get("id") if isinstance(c, dict) else c for c in collections
                ]
                if collection_id in collection_ids:
                    collection_products.append(product)

        if not collection_products:
            return {
                "avgProductPrice": None,
                "minProductPrice": None,
                "maxProductPrice": None,
                "priceRange": None,
                "priceVariance": None,
            }

        # Extract prices
        prices = []
        vendors = []
        for product in collection_products:
            price = product.get("price", 0)
            if price > 0:
                prices.append(float(price))
            vendor = product.get("vendor")
            if vendor:
                vendors.append(vendor)

        if not prices:
            return {
                "avgProductPrice": None,
                "minProductPrice": None,
                "maxProductPrice": None,
                "priceRange": None,
                "priceVariance": None,
            }

        # Calculate price metrics
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)
        price_range = max_price - min_price
        price_variance = statistics.variance(prices) if len(prices) > 1 else 0

        return {
            "avgProductPrice": avg_price,
            "minProductPrice": min_price,
            "maxProductPrice": max_price,
            "priceRange": price_range,
            "priceVariance": price_variance,
        }

    def _compute_performance_metrics(
        self,
        collection: Dict[str, Any],
        order_data: List[Dict[str, Any]],
        products: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute performance metrics from order data"""
        collection_id = collection.get("collectionId", "")
        products = products or []

        # Build product-to-collection mapping and product info lookup
        collection_product_ids = set()
        product_info = {}

        for product in products:
            product_id = product.get("productId")
            if not product_id:
                continue

            product_info[product_id] = {
                "vendor": product.get("vendor", ""),
                "title": product.get("title", ""),
            }

            # Check if product belongs to this collection
            collections = product.get("collections", [])
            if isinstance(collections, str):
                import json

                try:
                    collections = json.loads(collections)
                except:
                    collections = []

            # Check if this collection ID is in the product's collections
            for coll in collections:
                if isinstance(coll, dict):
                    coll_id = coll.get("id") or coll.get("collectionId")
                elif isinstance(coll, str):
                    coll_id = coll
                else:
                    continue

                if coll_id == collection_id:
                    collection_product_ids.add(product_id)
                    break

        # Find orders with products from this collection
        collection_orders = []
        collection_revenue = 0.0
        product_sales = {}  # Track product sales for top products
        vendor_sales = {}  # Track vendor sales for top vendors

        for order in order_data:
            line_items = order.get("lineItems", [])
            if isinstance(line_items, str):
                import json

                try:
                    line_items = json.loads(line_items)
                except:
                    line_items = []

            order_has_collection_product = False
            for line_item in line_items:
                product_id = line_item.get("productId") or line_item.get("product_id")

                # Only include if product belongs to this collection
                if product_id and product_id in collection_product_ids:
                    quantity = line_item.get("quantity", 1)
                    price = float(line_item.get("price", 0))
                    revenue = price * quantity

                    # Track product sales
                    if product_id not in product_sales:
                        product_sales[product_id] = {"quantity": 0, "revenue": 0}
                    product_sales[product_id]["quantity"] += quantity
                    product_sales[product_id]["revenue"] += revenue

                    # Track vendor sales
                    vendor = product_info.get(product_id, {}).get("vendor", "Unknown")
                    if vendor and vendor != "Unknown":
                        if vendor not in vendor_sales:
                            vendor_sales[vendor] = {"quantity": 0, "revenue": 0}
                        vendor_sales[vendor]["quantity"] += quantity
                        vendor_sales[vendor]["revenue"] += revenue

                    collection_revenue += revenue
                    order_has_collection_product = True

            if order_has_collection_product:
                collection_orders.append(order)

        # Calculate conversion rate (needs view count)
        # This is a placeholder - actual calculation would need view data
        conversion_rate = None

        # Calculate revenue contribution by computing total shop revenue from all orders
        total_shop_revenue = sum(
            float(order.get("totalPrice", 0)) for order in order_data
        )
        revenue_contribution = None
        if total_shop_revenue > 0:
            revenue_contribution = (collection_revenue / total_shop_revenue) * 100

        # Get top products and vendors
        top_products = sorted(
            product_sales.items(), key=lambda x: x[1]["revenue"], reverse=True
        )[:5]
        top_product_ids = [p[0] for p in top_products]

        # Get top vendors by revenue
        top_vendors = sorted(
            vendor_sales.items(), key=lambda x: x[1]["revenue"], reverse=True
        )[:5]
        top_vendor_names = [v[0] for v in top_vendors]

        return {
            "conversionRate": conversion_rate,
            "revenueContribution": revenue_contribution,
            "topProducts": Json(top_product_ids if top_product_ids else []),
            "topVendors": Json(top_vendor_names if top_vendor_names else []),
        }

    def _compute_seo_score(self, collection: Dict[str, Any]) -> Dict[str, Any]:
        """Compute SEO score as integer (not string tier)"""
        score = 0

        # Title quality (good length and exists)
        title = collection.get("title", "")
        if title and 10 <= len(title) <= 60:  # Optimal title length
            score += 2
        elif title and len(title) > 5:
            score += 1

        # Description quality
        description = collection.get("description", "")
        if (
            description and 50 <= len(description) <= 160
        ):  # Good meta description length
            score += 2
        elif description and len(description) > 20:
            score += 1

        # Handle quality (URL-friendly)
        handle = collection.get("handle", "")
        if handle and len(handle) > 3:
            score += 1

        # SEO-specific fields
        seo_title = collection.get("seoTitle", "")
        if seo_title:
            score += 1

        seo_description = collection.get("seoDescription", "")
        if seo_description:
            score += 1

        return {"seoScore": score}  # Max score is 8

    def _compute_image_score(self, collection: Dict[str, Any]) -> Dict[str, Any]:
        """Compute image quality score"""
        score = 0

        # Check if collection has an image
        image_url = collection.get("imageUrl")
        if image_url:
            score += 3

            # Check if image has alt text
            image_alt = collection.get("imageAlt")
            if image_alt and len(image_alt.strip()) > 0:
                score += 2

        return {"imageScore": score}  # Max score is 5

    def _compute_performance_score(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute composite performance score"""
        score = 0.0

        # View engagement (30% weight)
        view_count = features.get("viewCount30d", 0)
        if view_count > 0:
            # Normalize view count (log scale for large numbers)
            import math

            normalized_views = min(
                math.log10(view_count + 1) / 4, 1.0
            )  # Cap at 10000 views
            score += normalized_views * 0.3

        # Click-through rate (25% weight)
        ctr = features.get("clickThroughRate")
        if ctr is not None:
            # Good CTR is around 2-5%
            normalized_ctr = min(ctr / 0.05, 1.0)  # Cap at 5%
            score += normalized_ctr * 0.25

        # Conversion rate (25% weight)
        conversion_rate = features.get("conversionRate")
        if conversion_rate is not None:
            # Good conversion rate is around 2-3%
            normalized_conversion = min(conversion_rate / 0.03, 1.0)  # Cap at 3%
            score += normalized_conversion * 0.25

        # Revenue contribution (10% weight)
        revenue_contribution = features.get("revenueContribution")
        if revenue_contribution is not None:
            # Normalize revenue contribution (good collections contribute 5-10%+)
            normalized_revenue = min(revenue_contribution / 10.0, 1.0)  # Cap at 10%
            score += normalized_revenue * 0.1

        # SEO score (5% weight)
        seo_score = features.get("seoScore", 0)
        normalized_seo = seo_score / 8.0  # Max SEO score is 8
        score += normalized_seo * 0.05

        # Image score (5% weight)
        image_score = features.get("imageScore", 0)
        normalized_image = image_score / 5.0  # Max image score is 5
        score += normalized_image * 0.05

        return {"performanceScore": score}
