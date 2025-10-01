"""
Gorse Collection Transformer - OPTIMIZED VERSION
Transforms collection features to Gorse item objects

Key improvements:
- Performance-based collection tiers
- Engagement quality metrics
- Curation quality signals
"""

from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseCollectionTransformer:
    """Transform collection features to Gorse item format with optimized labels"""

    def __init__(self):
        """Initialize collection transformer"""
        pass

    def transform_to_gorse_item(
        self, collection_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform collection features to Gorse item object

        Collections are treated as items in Gorse for collection-based recommendations
        """
        try:
            if hasattr(collection_features, "__dict__"):
                collection_dict = collection_features.__dict__
            else:
                collection_dict = collection_features

            collection_id = collection_dict.get("collection_id", "")
            if not collection_id:
                logger.warning("No collection_id found in collection features")
                return None

            # Convert numeric features to optimized categorical labels
            labels = self._convert_to_optimized_labels(collection_dict)

            # Get categories
            categories = self._get_categories(collection_dict, shop_id)

            collection_item = {
                "ItemId": f"shop_{shop_id}_collection_{collection_id}",
                "IsHidden": False,
                "Categories": categories,
                "Labels": labels,
                "Timestamp": (
                    collection_dict.get("last_computed_at", now_utc()).isoformat()
                    if hasattr(collection_dict.get("last_computed_at"), "isoformat")
                    else now_utc().isoformat()
                ),
                "Comment": f"Collection: {collection_id}",
            }

            logger.debug(
                f"Transformed collection {collection_id} with {len(labels)} labels"
            )

            return collection_item

        except Exception as e:
            logger.error(f"Failed to transform collection features: {str(e)}")
            return None

    def transform_batch_to_gorse_items(
        self, collection_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple collection features to Gorse item objects"""
        gorse_items = []

        for collection_features in collection_features_list:
            gorse_item = self.transform_to_gorse_item(collection_features, shop_id)
            if gorse_item:
                gorse_items.append(gorse_item)

        logger.info(f"Transformed {len(gorse_items)} collections for shop {shop_id}")
        return gorse_items

    def _convert_to_optimized_labels(
        self, collection_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Convert numeric collection features to optimized categorical labels

        Max 12 labels for collections (less complex than products)
        """
        labels = []

        try:
            # 1. COLLECTION PERFORMANCE (Overall quality)
            performance = self._calculate_collection_performance(collection_dict)
            labels.append(f"performance:{performance}")

            # 2. CURATION TYPE
            is_automated = collection_dict.get("is_automated", False)
            if is_automated:
                labels.append("curation:automated")
            else:
                labels.append("curation:manual")

            # 3. COLLECTION SIZE
            product_count = int(collection_dict.get("product_count") or 0)
            if product_count >= 50:
                labels.append("size:large")
            elif product_count >= 20:
                labels.append("size:medium")
            elif product_count >= 5:
                labels.append("size:small")
            else:
                labels.append("size:minimal")

            # 4. ENGAGEMENT QUALITY (View-to-click performance)
            engagement = self._calculate_engagement_quality(collection_dict)
            labels.append(f"engagement:{engagement}")

            # 5. CONVERSION QUALITY
            conversion = float(collection_dict.get("conversion_rate") or 0)
            if conversion >= 0.15:
                labels.append("conversion:excellent")
            elif conversion >= 0.10:
                labels.append("conversion:good")
            elif conversion >= 0.05:
                labels.append("conversion:average")
            else:
                labels.append("conversion:poor")

            # 6. PRICE RANGE POSITIONING
            avg_price = float(collection_dict.get("avg_product_price") or 0)
            if avg_price >= 200:
                labels.append("price_range:premium")
            elif avg_price >= 75:
                labels.append("price_range:mid")
            else:
                labels.append("price_range:budget")

            # 7. VISITOR QUALITY (Bounce rate indicator)
            bounce = float(collection_dict.get("bounce_rate") or 0)
            if bounce >= 0.70:
                labels.append("bounce:high")
            elif bounce >= 0.40:
                labels.append("bounce:medium")
            else:
                labels.append("bounce:low")

            # 8. CLICK-THROUGH RATE
            ctr = float(collection_dict.get("click_through_rate") or 0)
            if ctr >= 0.20:
                labels.append("ctr:high")
            elif ctr >= 0.10:
                labels.append("ctr:medium")
            else:
                labels.append("ctr:low")

            # 9. REVENUE CONTRIBUTION
            revenue_contrib = float(collection_dict.get("revenue_contribution") or 0)
            if revenue_contrib >= 0.20:
                labels.append("revenue:top")
            elif revenue_contrib >= 0.10:
                labels.append("revenue:significant")
            elif revenue_contrib >= 0.05:
                labels.append("revenue:moderate")
            else:
                labels.append("revenue:minimal")

            # 10. POPULARITY TIER
            views = int(collection_dict.get("view_count_30d") or 0)
            if views >= 1000:
                labels.append("popularity:high")
            elif views >= 100:
                labels.append("popularity:medium")
            elif views > 0:
                labels.append("popularity:low")
            else:
                labels.append("popularity:new")

        except Exception as e:
            logger.error(
                f"Error converting collection features to optimized labels: {str(e)}"
            )

        return labels[:12]

    def _calculate_collection_performance(self, collection_dict: Dict[str, Any]) -> str:
        """Calculate overall collection performance score"""
        conversion = float(collection_dict.get("conversion_rate", 0) or 0)
        ctr = float(collection_dict.get("click_through_rate", 0) or 0)
        bounce = float(collection_dict.get("bounce_rate", 0) or 0)

        # Higher conversion and CTR = good, higher bounce = bad
        score = (conversion * 10 * 0.5) + (ctr * 0.3) + ((1 - bounce) * 0.2)

        if score >= 0.7:
            return "excellent"
        elif score >= 0.5:
            return "good"
        elif score >= 0.3:
            return "average"
        else:
            return "poor"

    def _calculate_engagement_quality(self, collection_dict: Dict[str, Any]) -> str:
        """Calculate visitor engagement quality"""
        views = int(collection_dict.get("view_count_30d") or 0)
        unique_viewers = int(collection_dict.get("unique_viewers_30d") or 0)
        ctr = float(collection_dict.get("click_through_rate") or 0)

        if views == 0:
            return "new"

        # High CTR and good unique viewer ratio = quality engagement
        if ctr >= 0.20 and unique_viewers >= 50:
            return "high"
        elif ctr >= 0.10 and unique_viewers >= 20:
            return "medium"
        else:
            return "low"

    def _get_categories(
        self, collection_dict: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """Get categories for the collection"""
        categories = [f"shop_{shop_id}", "Collections"]

        # Add collection type
        if collection_dict.get("is_automated"):
            categories.append("automated")
        else:
            categories.append("manual")

        return categories[:5]
