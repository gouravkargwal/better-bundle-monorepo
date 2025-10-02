"""
Gorse Item Transformer - STATE-OF-THE-ART VERSION
Transforms optimized product features to Gorse item objects with research-backed labels

Key improvements:
- Uses ALL 12 optimized product features from ProductFeatureGenerator
- Lifecycle-aware product segmentation with predictive signals
- Performance-based categorization for recommendation prioritization
- Inventory health signals for business optimization
- Modern e-commerce product intelligence
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.logging import get_logger
from app.shared.helpers import now_utc
import json

logger = get_logger(__name__)


class GorseItemTransformer:
    """Transform optimized product features to Gorse item format with state-of-the-art labels"""

    def __init__(self):
        """Initialize item transformer"""
        pass

    def transform_to_gorse_item(
        self, product_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform optimized product features to Gorse item object

        Args:
            product_features: Optimized ProductFeatures model or dict from database
            shop_id: Shop ID

        Returns:
            Gorse item object with comprehensive labels
        """
        try:
            if hasattr(product_features, "__dict__"):
                product_dict = product_features.__dict__
            else:
                product_dict = product_features

            product_id = product_dict.get("product_id", "")
            if not product_id:
                return None

            # Convert ALL optimized features to state-of-the-art categorical labels
            labels = self._convert_to_comprehensive_labels(product_dict)

            # Get enhanced categories
            categories = self._get_enhanced_categories(product_dict, shop_id)

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
                "Comment": f"Product: {product_id} (using ALL 12 optimized features)",
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

        logger.info(
            f"Transformed {len(gorse_items)} products with comprehensive features for shop {shop_id}"
        )
        return gorse_items

    def _convert_to_comprehensive_labels(
        self, product_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Convert ALL 12 optimized product features to comprehensive categorical labels

        Uses every single optimized feature from ProductFeatureGenerator for maximum signal
        Max 12 labels for optimal Gorse performance

        Args:
            product_dict: ALL optimized product features dictionary from database

        Returns:
            List of comprehensive categorical labels using all features (max 12)
        """
        labels = []

        try:
            # ===== USE ALL 12 OPTIMIZED PRODUCT FEATURES =====

            # 1. PRODUCT LIFECYCLE STAGE (Most critical - from optimized features)
            lifecycle_stage = product_dict.get("product_lifecycle_stage", "dormant")
            labels.append(f"lifecycle:{lifecycle_stage}")

            # 2. INTERACTION VOLUME SCORE (From optimized interaction_volume_score)
            volume_score = float(product_dict.get("interaction_volume_score", 0) or 0)
            if volume_score >= 0.8:
                labels.append("volume:viral")
            elif volume_score >= 0.6:
                labels.append("volume:high")
            elif volume_score >= 0.3:
                labels.append("volume:medium")
            else:
                labels.append("volume:low")

            # 3. PURCHASE VELOCITY SCORE (From optimized purchase_velocity_score)
            velocity_score = float(product_dict.get("purchase_velocity_score", 0) or 0)
            if velocity_score >= 0.8:
                labels.append("velocity:hot")
            elif velocity_score >= 0.5:
                labels.append("velocity:fast")
            elif velocity_score >= 0.2:
                labels.append("velocity:steady")
            else:
                labels.append("velocity:slow")

            # 4. ENGAGEMENT QUALITY SCORE (From optimized engagement_quality_score)
            engagement_score = float(
                product_dict.get("engagement_quality_score", 0) or 0
            )
            if engagement_score >= 0.8:
                labels.append("engagement:exceptional")
            elif engagement_score >= 0.6:
                labels.append("engagement:premium")
            elif engagement_score >= 0.3:
                labels.append("engagement:good")
            else:
                labels.append("engagement:basic")

            # 5. PRICE TIER (From optimized price_tier)
            price_tier = product_dict.get("price_tier", "mid")
            labels.append(f"price:{price_tier}")

            # 6. REVENUE POTENTIAL SCORE (From optimized revenue_potential_score)
            revenue_potential = float(
                product_dict.get("revenue_potential_score", 0) or 0
            )
            if revenue_potential >= 0.8:
                labels.append("revenue:blockbuster")
            elif revenue_potential >= 0.5:
                labels.append("revenue:strong")
            elif revenue_potential >= 0.2:
                labels.append("revenue:moderate")
            else:
                labels.append("revenue:niche")

            # 7. CONVERSION EFFICIENCY (From optimized conversion_efficiency)
            conversion_efficiency = float(
                product_dict.get("conversion_efficiency", 0) or 0
            )
            if conversion_efficiency >= 0.2:
                labels.append("conversion:excellent")
            elif conversion_efficiency >= 0.1:
                labels.append("conversion:good")
            elif conversion_efficiency >= 0.05:
                labels.append("conversion:average")
            else:
                labels.append("conversion:poor")

            # 8. DAYS SINCE LAST PURCHASE (From optimized days_since_last_purchase)
            days_since_last = product_dict.get("days_since_last_purchase")
            if days_since_last is not None:
                if days_since_last <= 7:
                    labels.append("recency:hot")
                elif days_since_last <= 30:
                    labels.append("recency:warm")
                elif days_since_last <= 90:
                    labels.append("recency:cool")
                else:
                    labels.append("recency:cold")

            # 9. ACTIVITY RECENCY SCORE (From optimized activity_recency_score)
            recency_score = float(product_dict.get("activity_recency_score", 0) or 0)
            if recency_score >= 0.8:
                labels.append("activity:trending")
            elif recency_score >= 0.5:
                labels.append("activity:active")
            else:
                labels.append("activity:dormant")

            # 10. TRENDING MOMENTUM (From optimized trending_momentum)
            trending_momentum = float(product_dict.get("trending_momentum", 0) or 0)
            if trending_momentum >= 0.8:
                labels.append("momentum:viral")
            elif trending_momentum >= 0.5:
                labels.append("momentum:rising")
            else:
                labels.append("momentum:stable")

            # 11. INVENTORY HEALTH SCORE (From optimized inventory_health_score)
            inventory_health = float(product_dict.get("inventory_health_score", 0) or 0)
            if inventory_health >= 0.8:
                labels.append("stock:healthy")
            elif inventory_health >= 0.5:
                labels.append("stock:adequate")
            elif inventory_health >= 0.2:
                labels.append("stock:low")
            else:
                labels.append("stock:critical")

            # 12. PRODUCT CATEGORY (From optimized product_category)
            product_category = product_dict.get("product_category")
            if product_category and str(product_category).lower() not in [
                "none",
                "unknown",
                "",
            ]:
                clean_category = str(product_category).lower().replace(" ", "_")[:20]
                labels.append(f"category:{clean_category}")

        except Exception as e:
            logger.error(
                f"Error converting ALL optimized product features to labels: {str(e)}"
            )

        return labels[:12]  # ALL 12 optimized features as labels

    def _get_enhanced_categories(
        self, product_dict: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """Get enhanced categories for the product using optimized features"""
        categories = [f"shop_{shop_id}"]

        # Product category from optimized features
        product_category = product_dict.get("product_category")
        if product_category and str(product_category).lower() not in [
            "none",
            "unknown",
            "",
        ]:
            categories.append(str(product_category))

        # Lifecycle-based categorization
        lifecycle_stage = product_dict.get("product_lifecycle_stage", "dormant")
        categories.append(f"lifecycle:{lifecycle_stage}")

        # Price tier categorization
        price_tier = product_dict.get("price_tier", "mid")
        categories.append(f"price_tier:{price_tier}")

        # Performance-based categorization
        volume_score = float(product_dict.get("interaction_volume_score", 0) or 0)
        if volume_score >= 0.5:
            categories.append("performance:active")
        else:
            categories.append("performance:passive")

        # Revenue tier categorization
        revenue_potential = float(product_dict.get("revenue_potential_score", 0) or 0)
        if revenue_potential >= 0.6:
            categories.append("revenue:high_potential")
        else:
            categories.append("revenue:standard")

        return categories[:6]  # Enhanced categories

    # ===== ADVANCED PRODUCT INTELLIGENCE =====

    def _calculate_comprehensive_recommendation_priority(
        self, product_dict: Dict[str, Any]
    ) -> str:
        """
        Calculate comprehensive recommendation priority using ALL optimized features

        Critical for Gorse's product recommendation ranking
        """
        # Get ALL key optimized scores
        lifecycle_stage = product_dict.get("product_lifecycle_stage", "dormant")
        volume_score = float(product_dict.get("interaction_volume_score", 0) or 0)
        velocity_score = float(product_dict.get("purchase_velocity_score", 0) or 0)
        engagement_score = float(product_dict.get("engagement_quality_score", 0) or 0)
        conversion_efficiency = float(product_dict.get("conversion_efficiency", 0) or 0)
        revenue_potential = float(product_dict.get("revenue_potential_score", 0) or 0)
        inventory_health = float(product_dict.get("inventory_health_score", 0) or 0)
        recency_score = float(product_dict.get("activity_recency_score", 0) or 0)
        trending_momentum = float(product_dict.get("trending_momentum", 0) or 0)

        # Calculate comprehensive priority score
        # Growth and emerging products get lifecycle boost
        if lifecycle_stage in ["growth", "emerging"]:
            lifecycle_boost = 0.3
        elif lifecycle_stage == "mature":
            lifecycle_boost = 0.1
        else:
            lifecycle_boost = 0.0

        # Inventory penalty for critical stock
        inventory_penalty = 0.0 if inventory_health >= 0.3 else -0.3

        # Trending momentum bonus
        trending_bonus = trending_momentum * 0.1

        priority_score = (
            volume_score * 0.15  # User interest
            + velocity_score * 0.20  # Sales performance
            + engagement_score * 0.15  # Engagement quality
            + conversion_efficiency * 0.15  # Conversion quality
            + revenue_potential * 0.20  # Business value
            + inventory_health * 0.10  # Stock availability
            + recency_score * 0.05  # Recent activity
            + lifecycle_boost  # Lifecycle bonus
            + inventory_penalty  # Stock penalty
            + trending_bonus  # Momentum bonus
        )

        # Classify comprehensive priority
        if priority_score >= 0.9:
            return "hero_product"  # Top-tier hero products
        elif priority_score >= 0.75:
            return "featured"  # Featured products
        elif priority_score >= 0.6:
            return "high_priority"  # High-priority recommendations
        elif priority_score >= 0.45:
            return "standard"  # Standard recommendations
        elif priority_score >= 0.3:
            return "secondary"  # Secondary recommendations
        elif priority_score >= 0.15:
            return "niche"  # Niche products
        else:
            return "background"  # Background/maintenance products

    def _calculate_product_health_status(self, product_dict: Dict[str, Any]) -> str:
        """
        Calculate overall product health using multiple optimized features
        """
        engagement_score = float(product_dict.get("engagement_quality_score", 0) or 0)
        velocity_score = float(product_dict.get("purchase_velocity_score", 0) or 0)
        inventory_health = float(product_dict.get("inventory_health_score", 0) or 0)
        recency_score = float(product_dict.get("activity_recency_score", 0) or 0)

        # Calculate health score
        health_score = (
            engagement_score * 0.3
            + velocity_score * 0.3
            + inventory_health * 0.2
            + recency_score * 0.2
        )

        if health_score >= 0.8:
            return "excellent_health"
        elif health_score >= 0.6:
            return "good_health"
        elif health_score >= 0.4:
            return "fair_health"
        elif health_score >= 0.2:
            return "poor_health"
        else:
            return "critical_health"

    def _calculate_market_position(self, product_dict: Dict[str, Any]) -> str:
        """
        Determine market position using engagement, revenue, and lifecycle
        """
        lifecycle_stage = product_dict.get("product_lifecycle_stage", "dormant")
        revenue_potential = float(product_dict.get("revenue_potential_score", 0) or 0)
        volume_score = float(product_dict.get("interaction_volume_score", 0) or 0)

        # Market position logic
        if lifecycle_stage == "growth" and revenue_potential >= 0.7:
            return "rising_star"
        elif lifecycle_stage == "mature" and volume_score >= 0.6:
            return "market_leader"
        elif revenue_potential >= 0.5 and volume_score >= 0.5:
            return "strong_performer"
        elif lifecycle_stage == "emerging":
            return "new_entrant"
        elif lifecycle_stage == "decline":
            return "declining"
        else:
            return "steady_performer"

    def _calculate_customer_appeal(self, product_dict: Dict[str, Any]) -> str:
        """
        Calculate customer appeal using engagement and conversion metrics
        """
        engagement_score = float(product_dict.get("engagement_quality_score", 0) or 0)
        conversion_efficiency = float(product_dict.get("conversion_efficiency", 0) or 0)
        trending_momentum = float(product_dict.get("trending_momentum", 0) or 0)

        # Appeal calculation
        appeal_score = (
            engagement_score * 0.4
            + conversion_efficiency * 0.4
            + trending_momentum * 0.2
        )

        if appeal_score >= 0.8:
            return "highly_appealing"
        elif appeal_score >= 0.6:
            return "appealing"
        elif appeal_score >= 0.4:
            return "moderately_appealing"
        elif appeal_score >= 0.2:
            return "low_appeal"
        else:
            return "minimal_appeal"

    # ===== PREDICTIVE LABELS =====

    def generate_predictive_labels(self, product_dict: Dict[str, Any]) -> List[str]:
        """
        Generate predictive labels for advanced Gorse targeting

        These labels help Gorse make better product recommendations
        """
        predictive_labels = []

        # Recommendation Priority (CRITICAL for Gorse)
        priority = self._calculate_comprehensive_recommendation_priority(product_dict)
        predictive_labels.append(f"priority:{priority}")

        # Product Health Status
        health = self._calculate_product_health_status(product_dict)
        predictive_labels.append(f"health:{health}")

        # Market Position
        position = self._calculate_market_position(product_dict)
        predictive_labels.append(f"position:{position}")

        # Customer Appeal
        appeal = self._calculate_customer_appeal(product_dict)
        predictive_labels.append(f"appeal:{appeal}")

        return predictive_labels

    # ===== BUSINESS INTELLIGENCE LABELS =====

    def generate_business_intelligence_labels(
        self, product_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Generate business intelligence labels for strategic recommendations
        """
        bi_labels = []

        # Revenue Impact Assessment
        revenue_potential = float(product_dict.get("revenue_potential_score", 0) or 0)
        if revenue_potential >= 0.8:
            bi_labels.append("business_impact:high_revenue")
        elif revenue_potential >= 0.5:
            bi_labels.append("business_impact:revenue_driver")
        else:
            bi_labels.append("business_impact:standard_revenue")

        # Inventory Strategy
        inventory_health = float(product_dict.get("inventory_health_score", 0) or 0)
        if inventory_health <= 0.3:
            bi_labels.append("inventory_strategy:clearance_candidate")
        elif inventory_health >= 0.8:
            bi_labels.append("inventory_strategy:well_stocked")

        # Growth Potential
        trending_momentum = float(product_dict.get("trending_momentum", 0) or 0)
        lifecycle_stage = product_dict.get("product_lifecycle_stage", "dormant")

        if trending_momentum >= 0.6 and lifecycle_stage in ["growth", "emerging"]:
            bi_labels.append("growth_potential:high")
        elif trending_momentum >= 0.3:
            bi_labels.append("growth_potential:moderate")
        else:
            bi_labels.append("growth_potential:stable")

        return bi_labels

    # ===== QUALITY CONTROL =====

    def validate_label_quality(self, labels: List[str]) -> List[str]:
        """Ensure label quality and remove conflicts"""
        # Remove duplicate label types
        seen_types = set()
        cleaned_labels = []

        for label in labels:
            label_type = label.split(":")[0]
            if label_type not in seen_types:
                cleaned_labels.append(label)
                seen_types.add(label_type)

        return cleaned_labels[:12]  # Maintain limit

    # ===== ENHANCED TRANSFORMATION WITH ALL FEATURES =====

    def transform_to_comprehensive_gorse_item(
        self, product_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform to comprehensive Gorse item using ALL features and predictive labels
        """
        try:
            base_item = self.transform_to_gorse_item(product_features, shop_id)
            if not base_item:
                return None

            if hasattr(product_features, "__dict__"):
                product_dict = product_features.__dict__
            else:
                product_dict = product_features

            # Add predictive labels
            predictive_labels = self.generate_predictive_labels(product_dict)
            bi_labels = self.generate_business_intelligence_labels(product_dict)

            # Combine all labels
            all_labels = base_item["Labels"] + predictive_labels + bi_labels
            validated_labels = self.validate_label_quality(all_labels)

            base_item["Labels"] = validated_labels
            base_item["Comment"] = (
                f"Product: {product_dict.get('product_id', '')} (comprehensive features + predictive labels)"
            )

            return base_item

        except Exception as e:
            logger.error(f"Failed to create comprehensive Gorse item: {str(e)}")
            return self.transform_to_gorse_item(product_features, shop_id)  # Fallback

    def transform_batch_to_comprehensive_gorse_items(
        self, product_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch to comprehensive Gorse items"""
        gorse_items = []

        for product_features in product_features_list:
            gorse_item = self.transform_to_comprehensive_gorse_item(
                product_features, shop_id
            )
            if gorse_item:
                gorse_items.append(gorse_item)

        logger.info(
            f"Transformed {len(gorse_items)} products with comprehensive features + predictive labels for shop {shop_id}"
        )
        return gorse_items
