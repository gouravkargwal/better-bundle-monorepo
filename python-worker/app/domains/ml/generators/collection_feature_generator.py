"""
Collection feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics
from datetime import datetime, timedelta, timezone
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CollectionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify collections"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

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
                f"Computing features for collection: {collection.get('collection_id', 'unknown')}"
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
                        "conversion_rate": None,
                        "revenue_contribution": None,
                        "top_products": [],
                        "top_vendors": [],
                    }
                )

            # SEO and image scores
            features.update(self._compute_seo_score(collection))
            features.update(self._compute_image_score(collection))

            # NEW: Compute enhanced collection features using previously unused fields
            collection_metadata_features = self._compute_collection_metadata_features(
                collection
            )
            collection_lifecycle_features = self._compute_collection_lifecycle_features(
                collection
            )

            # Performance score (composite)
            features.update(self._compute_performance_score(features))

            # Validate and clean features
            features = self.validate_features(features)

            # Add enhanced collection features
            features.update(collection_metadata_features)
            features.update(collection_lifecycle_features)

            # Add lastComputedAt timestamp
            from app.shared.helpers import now_utc

            features["last_computed_at"] = now_utc()

            logger.debug(
                f"Computed {len(features)} features for collection: {collection.get('collection_id', 'unknown')}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute collection features for {collection.get('collection_id', 'unknown')}: {str(e)}"
            )
            return {}

    def _compute_basic_collection_features(
        self, collection: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic collection features"""
        return {
            "shop_id": shop.get("id", "") if shop else "",
            "collection_id": collection.get("collection_id", ""),
            "product_count": collection.get("product_count", 0),
            "is_automated": bool(collection.get("is_automated", False)),
        }

    def _compute_engagement_metrics(
        self, collection: Dict[str, Any], behavioral_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute engagement metrics from behavioral events (30-day window)"""
        collection_id = collection.get("collection_id", "")
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Filter events for this collection in last 30 days
        collection_events = []
        for event in behavioral_events:
            event_time = event.get("timestamp")
            if isinstance(event_time, str):
                event_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            elif not isinstance(event_time, datetime):
                continue

            if event_time >= thirty_days_ago:
                # Check if event is related to this collection
                event_data = event.get("event_data", {})
                if event_data.get(
                    "collection_id"
                ) == collection_id or collection_id in event_data.get(
                    "collection_ids", []
                ):
                    collection_events.append(event)

        # Calculate metrics using adapter pattern
        view_events = [
            e
            for e in collection_events
            if self.adapter_factory.is_view_event(e)
            and e.get("event_type") == "collection_viewed"
        ]
        click_events = [
            e
            for e in collection_events
            if e.get("event_type") == "product_click_from_collection"
        ]
        bounce_events = [
            e for e in collection_events if e.get("event_type") == "bounce"
        ]

        view_count = len(view_events)
        unique_viewers = len(
            set(e.get("customer_id") for e in view_events if e.get("customer_id"))
        )
        click_count = len(click_events)
        bounce_count = len(bounce_events)

        return {
            "view_count_30d": view_count,
            "unique_viewers_30d": unique_viewers,
            "click_through_rate": (
                (click_count / view_count) if view_count > 0 else None
            ),
            "bounce_rate": (bounce_count / view_count) if view_count > 0 else None,
        }

    def _compute_product_metrics(
        self, collection: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute product-related metrics matching schema"""
        collection_products = collection.get("products", [])

        if not collection_products:
            return {
                "avg_product_price": None,
                "min_product_price": None,
                "max_product_price": None,
                "price_range": None,
                "price_variance": None,
            }

        # Extract prices from normalized product data
        prices = []
        vendors = []
        for product in collection_products:
            # Extract price from price_range structure
            price_range = product.get("price_range", {})
            if isinstance(price_range, dict):
                min_price = price_range.get("minVariantPrice", {})
                max_price = price_range.get("maxVariantPrice", {})

                if isinstance(min_price, dict) and isinstance(max_price, dict):
                    min_amount = min_price.get("amount", "0")
                    max_amount = max_price.get("amount", "0")

                    try:
                        min_val = float(min_amount)
                        max_val = float(max_amount)
                        # Use average of min and max price
                        avg_price = (min_val + max_val) / 2
                        if avg_price > 0:
                            prices.append(avg_price)
                    except (ValueError, TypeError):
                        pass

            vendor = product.get("vendor")
            if vendor:
                vendors.append(vendor)

        if not prices:
            return {
                "avg_product_price": None,
                "min_product_price": None,
                "max_product_price": None,
                "price_range": None,
                "price_variance": None,
            }

        # Calculate price metrics
        min_price = min(prices)
        max_price = max(prices)
        avg_price = statistics.mean(prices)
        price_range = max_price - min_price
        price_variance = statistics.variance(prices) if len(prices) > 1 else 0

        return {
            "avg_product_price": avg_price,
            "min_product_price": min_price,
            "max_product_price": max_price,
            "price_range": price_range,
            "price_variance": price_variance,
        }

    def _compute_performance_metrics(
        self,
        collection: Dict[str, Any],
        order_data: List[Dict[str, Any]],
        products: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute performance metrics from order data"""
        collection_id = collection.get("collection_id", "")
        products = products or []

        # Get product IDs directly from collection data (normalized structure)
        collection_products_data = collection.get("products", [])
        collection_product_ids = set()
        product_info = {}

        for product in collection_products_data:
            if not isinstance(product, dict):
                continue

            # Extract product ID (already normalized)
            product_id = product.get("id")
            if product_id:
                collection_product_ids.add(product_id)
                product_info[product_id] = {
                    "vendor": product.get("vendor", ""),
                    "title": product.get("title", ""),
                }

        # Find orders with products from this collection
        collection_orders = []
        collection_revenue = 0.0
        product_sales = {}  # Track product sales for top products
        vendor_sales = {}  # Track vendor sales for top vendors

        for order in order_data:
            line_items = order.get("lineItems", [])
            # Line items are already parsed from database (no JSON parsing needed)

            order_has_collection_product = False
            for line_item in line_items:
                product_id = line_item.get("product_id")

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
            float(order.get("total_price", 0)) for order in order_data
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
            "conversion_rate": conversion_rate,
            "revenue_contribution": revenue_contribution,
            "top_products": top_product_ids if top_product_ids else [],
            "top_vendors": top_vendor_names if top_vendor_names else [],
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
        seo_title = collection.get("seo_title", "")
        if seo_title:
            score += 1

        seo_description = collection.get("seo_description", "")
        if seo_description:
            score += 1

        return {"seo_score": score}  # Max score is 8

    def _compute_image_score(self, collection: Dict[str, Any]) -> Dict[str, Any]:
        """Compute image quality score"""
        score = 0

        # Check if collection has an image
        image_url = collection.get("image_url")
        if image_url:
            score += 3

            # Check if image has alt text
            image_alt = collection.get("image_alt")
            if image_alt and len(image_alt.strip()) > 0:
                score += 2

        return {"image_score": score}  # Max score is 5

    def _compute_performance_score(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute composite performance score"""
        score = 0.0

        # View engagement (30% weight)
        view_count = features.get("view_count_30d", 0)
        if view_count > 0:
            # Normalize view count (log scale for large numbers)
            import math

            normalized_views = min(
                math.log10(view_count + 1) / 4, 1.0
            )  # Cap at 10000 views
            score += normalized_views * 0.3

        # Click-through rate (25% weight)
        ctr = features.get("click_through_rate")
        if ctr is not None:
            # Good CTR is around 2-5%
            normalized_ctr = min(ctr / 0.05, 1.0)  # Cap at 5%
            score += normalized_ctr * 0.25

        # Conversion rate (25% weight)
        conversion_rate = features.get("conversion_rate")
        if conversion_rate is not None:
            # Good conversion rate is around 2-3%
            normalized_conversion = min(conversion_rate / 0.03, 1.0)  # Cap at 3%
            score += normalized_conversion * 0.25

        # Revenue contribution (10% weight)
        revenue_contribution = features.get("revenue_contribution")
        if revenue_contribution is not None:
            # Normalize revenue contribution (good collections contribute 5-10%+)
            normalized_revenue = min(revenue_contribution / 10.0, 1.0)  # Cap at 10%
            score += normalized_revenue * 0.1

        # SEO score (5% weight)
        seo_score = features.get("seo_score", 0)
        normalized_seo = seo_score / 8.0  # Max SEO score is 8
        score += normalized_seo * 0.05

        # Image score (5% weight)
        image_score = features.get("image_score", 0)
        normalized_image = image_score / 5.0  # Max image score is 5
        score += normalized_image * 0.05

        return {"performance_score": score}

    def _compute_collection_metadata_features(
        self, collection: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute collection metadata features using previously unused fields"""
        try:
            # Handle and template features (currently unused)
            handle = collection.get("handle", "")
            template_suffix = collection.get("template_suffix", "")

            # Handle quality score (URL-friendly)
            handle_quality = 0
            if handle and len(handle) > 3:
                handle_quality = min(len(handle) / 10, 10)  # Max 10 points

            # Template customization score
            template_score = 10 if template_suffix else 0

            # Metafields analysis (currently unused)
            metafields = collection.get("metafields", [])
            metafield_count = len(metafields) if isinstance(metafields, list) else 0
            metafield_utilization = min(metafield_count / 5, 1.0)  # Normalize to 0-1

            # Extras analysis (currently unused)
            extras = collection.get("extras", {})
            extras_count = len(extras) if isinstance(extras, dict) else 0
            extras_utilization = min(extras_count / 3, 1.0)  # Normalize to 0-1

            return {
                "handle_quality": handle_quality,
                "template_score": template_score,
                "metafield_utilization": metafield_utilization,
                "extras_utilization": extras_utilization,
                "handle": handle,
                "template_suffix": template_suffix,
                "metafield_count": metafield_count,
                "extras_count": extras_count,
            }
        except Exception as e:
            logger.error(f"Error computing collection metadata features: {str(e)}")
            return {
                "handle_quality": 0,
                "template_score": 0,
                "metafield_utilization": 0.0,
                "extras_utilization": 0.0,
                "handle": "",
                "template_suffix": "",
                "metafield_count": 0,
                "extras_count": 0,
            }

    def _compute_collection_lifecycle_features(
        self, collection: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute collection lifecycle features using previously unused fields"""
        try:
            from app.shared.helpers import now_utc

            # Collection age and update frequency
            created_at = collection.get("created_at")
            updated_at = collection.get("updated_at")

            collection_age = 0
            last_updated_days = 0
            update_frequency = 0.0

            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                collection_age = (now_utc() - created_at).days

            if updated_at:
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(
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

            # Collection maturity score based on age and updates
            maturity_score = 0
            if collection_age > 365:  # More than 1 year old
                maturity_score = 100
            elif collection_age > 180:  # More than 6 months old
                maturity_score = 75
            elif collection_age > 90:  # More than 3 months old
                maturity_score = 50
            elif collection_age > 30:  # More than 1 month old
                maturity_score = 25
            else:
                maturity_score = 10  # New collection

            # Bonus for active maintenance
            if update_frequency > 1.0:  # Updated more than once per month
                maturity_score += 20
            elif update_frequency > 0.5:  # Updated at least twice per month
                maturity_score += 10

            return {
                "collection_age": collection_age,
                "last_updated_days": last_updated_days,
                "update_frequency": round(update_frequency, 2),
                "maturity_score": min(maturity_score, 100),
            }
        except Exception as e:
            logger.error(f"Error computing collection lifecycle features: {str(e)}")
            return {
                "collection_age": 0,
                "last_updated_days": 0,
                "update_frequency": 0.0,
                "maturity_score": 0,
            }

    def _extract_numeric_gid(self, gid: Optional[str]) -> Optional[str]:
        """Extract numeric ID from GraphQL ID"""
        if not gid or not isinstance(gid, str):
            return None
        try:
            if gid.startswith("gid://shopify/"):
                return gid.split("/")[-1]
            return gid
        except Exception:
            return None
