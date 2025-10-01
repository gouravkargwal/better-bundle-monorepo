"""
Gorse Item Transformer - OPTIMIZED VERSION
Transforms product features to Gorse item objects with research-backed labels

Key improvements:
- Performance-based labels (conversion, revenue)
- Product lifecycle stages
- Inventory urgency signals
- Better actionable segments
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.logging import get_logger
from app.shared.helpers import now_utc
import json

logger = get_logger(__name__)


class GorseItemTransformer:
    """Transform product features to Gorse item format with optimized labels"""

    def __init__(self):
        """Initialize item transformer"""
        pass

    def transform_to_gorse_item(
        self, product_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform product features to Gorse item object with optimized labels
        """
        try:
            if hasattr(product_features, "__dict__"):
                product_dict = product_features.__dict__
            else:
                product_dict = product_features

            product_id = product_dict.get("product_id", "")
            if not product_id:
                return None

            # Convert numeric features to optimized categorical labels
            labels = self._convert_to_optimized_labels(product_dict)

            # Get categories
            categories = self._get_categories(product_dict, shop_id)

            return {
                "ItemId": f"shop_{shop_id}_{product_id}",
                "IsHidden": product_dict.get("is_hidden", False),
                "Categories": categories,
                "Labels": labels,
                "Timestamp": (
                    product_dict.get("last_computed_at", now_utc()).isoformat()
                    if hasattr(product_dict.get("last_computed_at"), "isoformat")
                    else now_utc().isoformat()
                ),
                "Comment": f"Product: {product_id}",
            }

        except Exception as e:
            logger.error(f"Failed to transform product features: {str(e)}")
            return None

    def transform_batch_to_gorse_items(
        self, product_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple product features to Gorse item objects"""
        gorse_items = []

        for product_features in product_features_list:
            gorse_item = self.transform_to_gorse_item(product_features, shop_id)
            if gorse_item:
                gorse_items.append(gorse_item)

        logger.info(f"Transformed {len(gorse_items)} items for shop {shop_id}")
        return gorse_items

    def _convert_to_optimized_labels(self, product_dict: Dict[str, Any]) -> List[str]:
        """Convert numeric product features to optimized categorical labels (max 15)"""
        labels = []

        try:
            # 1. PERFORMANCE TIER (Most important - combines multiple metrics)
            performance = self._calculate_performance_tier(product_dict)
            labels.append(f"performance:{performance}")

            # 2. PRICE POSITIONING (Relative to catalog)
            price_position = self._calculate_price_positioning(
                price=product_dict.get("price")
                or product_dict.get("avg_selling_price"),
                category=product_dict.get("product_type"),
            )
            labels.append(f"price_pos:{price_position}")

            # 3. SALES VELOCITY (How fast it's selling)
            velocity = self._calculate_sales_velocity(product_dict)
            labels.append(f"velocity:{velocity}")

            # 4. PRODUCT LIFECYCLE (New, growth, mature, decline)
            lifecycle = self._calculate_product_lifecycle(product_dict)
            labels.append(f"lifecycle:{lifecycle}")

            # 5. VENDOR (Brand affinity)
            vendor = product_dict.get("vendor")
            if vendor and vendor != "unknown":
                clean_vendor = str(vendor).lower().replace(" ", "_")[:30]
                labels.append(f"vendor:{clean_vendor}")

            # 6. PRODUCT TYPE/CATEGORY
            product_type = product_dict.get("product_type")
            if product_type and product_type != "unknown":
                clean_type = str(product_type).lower().replace(" ", "_")[:30]
                labels.append(f"type:{clean_type}")

            # 7. INVENTORY STATUS (Urgency signal)
            inventory_status = self._calculate_inventory_status(product_dict)
            labels.append(f"stock:{inventory_status}")

            # 8. DISCOUNT STATUS (Deal seeking)
            discount_status = self._calculate_discount_status(product_dict)
            if discount_status:
                labels.append(f"discount:{discount_status}")

            # 9. CONVERSION QUALITY (How well views convert)
            conversion_quality = self._calculate_conversion_quality(product_dict)
            labels.append(f"conversion:{conversion_quality}")

            # 10. ENGAGEMENT LEVEL (View-to-cart performance)
            engagement = self._calculate_product_engagement(product_dict)
            labels.append(f"engagement:{engagement}")

            # 11. REVENUE CONTRIBUTION (Top sellers vs long tail)
            revenue_contrib = self._calculate_revenue_tier(product_dict)
            labels.append(f"revenue:{revenue_contrib}")

            # 12. RISK PROFILE (Refund/return risk)
            risk = self._calculate_product_risk(product_dict)
            labels.append(f"risk:{risk}")

            # 13. TRENDING STATUS (Momentum)
            trending = float(product_dict.get("trending_score", 0) or 0)
            if trending >= 0.7:
                labels.append("trending:hot")
            elif trending >= 0.4:
                labels.append("trending:rising")

            # 14. COLLECTION MEMBERSHIP (If part of curated collections)
            collections = product_dict.get("collections", [])
            if isinstance(collections, str):
                try:
                    collections = json.loads(collections)
                except:
                    collections = []

            if isinstance(collections, list) and len(collections) > 0:
                labels.append("curated:yes")
            else:
                labels.append("curated:no")

            # 15. SEASONALITY (If you have seasonal data)
            # This would require additional logic based on your business

        except Exception as e:
            logger.error(
                f"Error converting product features to optimized labels: {str(e)}"
            )

        return labels[:15]

    def _calculate_performance_tier(self, product_dict: Dict[str, Any]) -> str:
        """
        Calculate overall product performance combining conversion, sales, and engagement
        """
        conversion = float(product_dict.get("overall_conversion_rate", 0) or 0)
        purchases = int(product_dict.get("purchase_count_30d", 0) or 0)
        views = int(product_dict.get("view_count_30d", 0) or 0)

        # Calculate composite score
        conversion_score = min(conversion * 10, 1.0)  # Normalize to 0-1
        popularity_score = min(purchases / 50, 1.0)  # Normalize
        visibility_score = min(views / 1000, 1.0)  # Normalize

        total_score = (
            conversion_score * 0.4 + popularity_score * 0.4 + visibility_score * 0.2
        )

        if total_score >= 0.7:
            return "star"  # Best performers
        elif total_score >= 0.5:
            return "strong"
        elif total_score >= 0.3:
            return "moderate"
        else:
            return "underperforming"

    def _calculate_price_positioning(
        self, price: Optional[float], category: Optional[str]
    ) -> str:
        """Calculate price positioning relative to catalog"""
        if not price or price <= 0:
            return "unknown"

        # Simple absolute tiers (you can make this category-relative if needed)
        if price >= 300:
            return "ultra_premium"
        elif price >= 150:
            return "premium"
        elif price >= 75:
            return "mid_range"
        elif price >= 25:
            return "value"
        else:
            return "budget"

    def _calculate_sales_velocity(self, product_dict: Dict[str, Any]) -> str:
        """Calculate how fast product is selling"""
        purchases_30d = int(product_dict.get("purchase_count_30d", 0) or 0)
        days_since_first_purchase = product_dict.get("days_since_first_purchase")

        if not days_since_first_purchase or days_since_first_purchase <= 0:
            return "new"

        # Calculate daily velocity
        daily_velocity = purchases_30d / min(days_since_first_purchase, 30)

        if daily_velocity >= 2:
            return "fast"
        elif daily_velocity >= 0.5:
            return "steady"
        elif daily_velocity > 0:
            return "slow"
        else:
            return "stagnant"

    def _calculate_product_lifecycle(self, product_dict: Dict[str, Any]) -> str:
        """Determine product lifecycle stage"""
        days_since_first_purchase = product_dict.get("days_since_first_purchase")
        purchases_30d = int(product_dict.get("purchase_count_30d", 0) or 0)
        trending = float(product_dict.get("trending_score", 0) or 0)

        if days_since_first_purchase is None or days_since_first_purchase <= 30:
            return "new"
        elif trending >= 0.6 and purchases_30d >= 10:
            return "growth"
        elif purchases_30d >= 20:
            return "mature"
        elif purchases_30d < 5 and days_since_first_purchase >= 90:
            return "decline"
        else:
            return "stable"

    def _calculate_inventory_status(self, product_dict: Dict[str, Any]) -> str:
        """Calculate inventory urgency"""
        inventory = int(product_dict.get("total_inventory", 0) or 0)
        velocity = float(product_dict.get("stock_velocity", 0) or 0)

        if inventory == 0:
            return "out_of_stock"
        elif inventory <= 5 and velocity > 0.5:
            return "urgent"  # Low stock, selling fast
        elif inventory <= 10:
            return "low"
        elif inventory <= 50:
            return "moderate"
        else:
            return "abundant"

    def _calculate_discount_status(self, product_dict: Dict[str, Any]) -> Optional[str]:
        """Calculate discount status"""
        compare_at = float(product_dict.get("compare_at_price", 0) or 0)
        price = float(
            product_dict.get("price", 0)
            or product_dict.get("avg_selling_price", 0)
            or 0
        )

        if not compare_at or not price or compare_at <= price:
            return "none"

        discount_pct = ((compare_at - price) / compare_at) * 100

        if discount_pct >= 50:
            return "deep"
        elif discount_pct >= 30:
            return "significant"
        elif discount_pct >= 15:
            return "moderate"
        else:
            return "slight"

    def _calculate_conversion_quality(self, product_dict: Dict[str, Any]) -> str:
        """How well views convert to purchases"""
        conversion = float(product_dict.get("overall_conversion_rate", 0) or 0)

        if conversion >= 0.15:
            return "excellent"
        elif conversion >= 0.10:
            return "good"
        elif conversion >= 0.05:
            return "average"
        else:
            return "poor"

    def _calculate_product_engagement(self, product_dict: Dict[str, Any]) -> str:
        """View-to-cart performance"""
        view_to_cart = float(product_dict.get("view_to_cart_rate", 0) or 0)

        if view_to_cart >= 0.30:
            return "high"
        elif view_to_cart >= 0.15:
            return "medium"
        else:
            return "low"

    def _calculate_revenue_tier(self, product_dict: Dict[str, Any]) -> str:
        """Revenue contribution classification"""
        revenue_30d = float(product_dict.get("total_revenue", 0) or 0)

        if revenue_30d >= 10000:
            return "top"
        elif revenue_30d >= 1000:
            return "high"
        elif revenue_30d >= 100:
            return "moderate"
        else:
            return "long_tail"

    def _calculate_product_risk(self, product_dict: Dict[str, Any]) -> str:
        """Refund/return risk"""
        refund_rate = float(product_dict.get("refund_rate", 0) or 0)

        if refund_rate >= 0.3:
            return "high"
        elif refund_rate >= 0.1:
            return "medium"
        else:
            return "low"

    def _get_categories(self, product_dict: Dict[str, Any], shop_id: str) -> List[str]:
        """Get categories for the product"""
        categories = [f"shop_{shop_id}"]

        product_type = product_dict.get("product_type")
        if product_type and product_type != "unknown":
            categories.append(str(product_type))

        vendor = product_dict.get("vendor")
        if vendor and vendor != "unknown":
            categories.append(f"vendor:{vendor}")

        return categories[:5]
