from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseCollectionTransformer:
    """Transform optimized collection features to Gorse item format with state-of-the-art labels"""

    def __init__(self):
        """Initialize collection transformer"""
        pass

    def transform_to_gorse_item(
        self, collection_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform optimized collection features to Gorse item object

        Collections are treated as items in Gorse for collection-based recommendations

        Args:
            collection_features: Optimized CollectionFeatures model or dict from database
            shop_id: Shop ID

        Returns:
            Gorse item object for collection with comprehensive labels
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

            # Convert ALL optimized features to state-of-the-art categorical labels
            labels = self._convert_to_comprehensive_labels(collection_dict)

            # Get enhanced categories
            categories = self._get_enhanced_categories(collection_dict, shop_id)

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
                "Comment": f"Collection: {collection_id} (using ALL optimized features)",
            }

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

        return gorse_items

    def _convert_to_comprehensive_labels(
        self, collection_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Convert ALL optimized collection features to comprehensive categorical labels

        Uses every optimized feature from CollectionFeatureGenerator for maximum signal
        Max 10 labels for optimal Gorse performance (collections are simpler than products)

        Args:
            collection_dict: ALL optimized collection features dictionary from database

        Returns:
            List of comprehensive categorical labels using all features (max 10)
        """
        labels = []

        try:
            # ===== USE ALL OPTIMIZED COLLECTION FEATURES =====

            # 1. COLLECTION ENGAGEMENT TIER (From optimized collection_engagement_score)
            engagement_score = float(
                collection_dict.get("collection_engagement_score", 0) or 0
            )
            if engagement_score >= 0.8:
                labels.append("engagement:exceptional")
            elif engagement_score >= 0.6:
                labels.append("engagement:premium")
            elif engagement_score >= 0.4:
                labels.append("engagement:strong")
            elif engagement_score >= 0.2:
                labels.append("engagement:moderate")
            else:
                labels.append("engagement:developing")

            # 2. CONVERSION PERFORMANCE (From optimized collection_conversion_rate)
            conversion_rate = float(
                collection_dict.get("collection_conversion_rate", 0) or 0
            )
            if conversion_rate >= 0.20:
                labels.append("conversion:excellent")
            elif conversion_rate >= 0.15:
                labels.append("conversion:high_performing")
            elif conversion_rate >= 0.10:
                labels.append("conversion:solid")
            elif conversion_rate >= 0.05:
                labels.append("conversion:developing")
            else:
                labels.append("conversion:low")

            # 3. POPULARITY STATUS (From optimized collection_popularity_score)
            popularity_score = float(
                collection_dict.get("collection_popularity_score", 0) or 0
            )
            if popularity_score >= 0.8:
                labels.append("popularity:viral")
            elif popularity_score >= 0.6:
                labels.append("popularity:trending")
            elif popularity_score >= 0.4:
                labels.append("popularity:popular")
            elif popularity_score >= 0.2:
                labels.append("popularity:emerging")
            else:
                labels.append("popularity:niche")

            # 4. REVENUE IMPACT (From optimized collection_revenue_potential)
            revenue_potential = float(
                collection_dict.get("collection_revenue_potential", 0) or 0
            )
            if revenue_potential >= 0.8:
                labels.append("revenue:blockbuster")
            elif revenue_potential >= 0.6:
                labels.append("revenue:high_impact")
            elif revenue_potential >= 0.4:
                labels.append("revenue:profitable")
            elif revenue_potential >= 0.2:
                labels.append("revenue:contributing")
            else:
                labels.append("revenue:minimal")

            # 5. COLLECTION SIZE TIER (From optimized collection_size_tier)
            size_tier = collection_dict.get("collection_size_tier", "minimal")
            labels.append(f"size:{size_tier}")

            # 6. CURATION QUALITY (From optimized is_curated_collection)
            is_curated = collection_dict.get("is_curated_collection", True)
            if is_curated:
                labels.append("curation:curated")
            else:
                labels.append("curation:automated")

            # 7. PRODUCT DIVERSITY (From optimized product_diversity_score)
            diversity_score = float(
                collection_dict.get("product_diversity_score", 0) or 0
            )
            if diversity_score >= 0.8:
                labels.append("diversity:very_diverse")
            elif diversity_score >= 0.6:
                labels.append("diversity:high_variety")
            elif diversity_score >= 0.4:
                labels.append("diversity:varied")
            elif diversity_score >= 0.2:
                labels.append("diversity:moderate")
            else:
                labels.append("diversity:focused")

            # 8. ACTIVITY RECENCY (From optimized collection_recency_score)
            recency_score = float(
                collection_dict.get("collection_recency_score", 0) or 0
            )
            if recency_score >= 0.8:
                labels.append("activity:very_active")
            elif recency_score >= 0.6:
                labels.append("activity:active")
            elif recency_score >= 0.3:
                labels.append("activity:moderate")
            else:
                labels.append("activity:dormant")

            # 9. VALUE POSITIONING (From optimized avg_product_value)
            avg_product_value = collection_dict.get("avg_product_value")
            if avg_product_value is not None:
                if avg_product_value >= 300:
                    labels.append("value_tier:luxury")
                elif avg_product_value >= 150:
                    labels.append("value_tier:premium")
                elif avg_product_value >= 75:
                    labels.append("value_tier:mid_market")
                elif avg_product_value >= 25:
                    labels.append("value_tier:accessible")
                else:
                    labels.append("value_tier:budget")
            else:
                labels.append("value_tier:mixed")

            # 10. RECOMMENDATION PRIORITY (Composite priority for Gorse - CRITICAL)
            rec_priority = self._calculate_comprehensive_recommendation_priority(
                collection_dict
            )
            labels.append(f"priority:{rec_priority}")

        except Exception as e:
            logger.error(
                f"Error converting ALL optimized collection features to labels: {str(e)}"
            )

        return labels[:10]  # ALL optimized features as labels (max 10)

    def _calculate_comprehensive_recommendation_priority(
        self, collection_dict: Dict[str, Any]
    ) -> str:
        """
        Calculate comprehensive recommendation priority using ALL optimized collection features

        Critical for Gorse's collection recommendation ranking and business strategy
        """
        # Get ALL key optimized scores
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        popularity_score = float(
            collection_dict.get("collection_popularity_score", 0) or 0
        )
        conversion_rate = float(
            collection_dict.get("collection_conversion_rate", 0) or 0
        )
        revenue_potential = float(
            collection_dict.get("collection_revenue_potential", 0) or 0
        )
        recency_score = float(collection_dict.get("collection_recency_score", 0) or 0)
        diversity_score = float(collection_dict.get("product_diversity_score", 0) or 0)
        size_tier = collection_dict.get("collection_size_tier", "minimal")
        is_curated = collection_dict.get("is_curated_collection", True)
        avg_product_value = collection_dict.get("avg_product_value", 0) or 0

        # Calculate comprehensive priority score with business-focused weighting
        priority_score = (
            engagement_score * 0.20  # User engagement quality
            + conversion_rate * 0.25  # Business conversion (highest weight)
            + revenue_potential * 0.20  # Revenue impact
            + popularity_score * 0.15  # User interest
            + recency_score * 0.10  # Recent activity
            + diversity_score * 0.05  # Content quality
            + (avg_product_value / 200.0) * 0.05  # Value tier bonus (normalize to $200)
        )

        # Apply size tier bonus (larger collections often perform better)
        size_bonuses = {"large": 0.15, "medium": 0.10, "small": 0.05, "minimal": 0.0}
        size_bonus = size_bonuses.get(size_tier, 0.0)

        # Apply curation boost (curated collections get strategic priority)
        curation_bonus = 0.10 if is_curated else 0.0

        # Final priority calculation
        final_priority_score = priority_score + size_bonus + curation_bonus
        final_priority_score = min(final_priority_score, 1.0)  # Cap at 1.0

        # Classify comprehensive priority for strategic collection recommendations
        if final_priority_score >= 0.9:
            return "hero_collection"  # Top-tier hero collections for homepage
        elif final_priority_score >= 0.75:
            return "featured"  # Featured collections for category pages
        elif final_priority_score >= 0.6:
            return "high_priority"  # High-priority recommendations
        elif final_priority_score >= 0.45:
            return "standard"  # Standard recommendations
        elif final_priority_score >= 0.3:
            return "secondary"  # Secondary recommendations
        elif final_priority_score >= 0.15:
            return "niche"  # Niche collections for specific users
        else:
            return "background"  # Background/maintenance collections

    def _get_enhanced_categories(
        self, collection_dict: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """Get enhanced categories for the collection using ALL optimized features"""
        categories = [f"shop_{shop_id}", "collections"]

        # Curation-based categorization
        is_curated = collection_dict.get("is_curated_collection", True)
        if is_curated:
            categories.append("curated")
        else:
            categories.append("automated")

        # Size-based categorization
        size_tier = collection_dict.get("collection_size_tier", "minimal")
        categories.append(f"size:{size_tier}")

        # Performance-based categorization
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        conversion_rate = float(
            collection_dict.get("collection_conversion_rate", 0) or 0
        )

        # Combined performance indicator
        performance_score = (engagement_score + conversion_rate) / 2.0
        if performance_score >= 0.6:
            categories.append("performance:high_performing")
        elif performance_score >= 0.3:
            categories.append("performance:moderate")
        else:
            categories.append("performance:developing")

        # Value tier categorization
        avg_product_value = collection_dict.get("avg_product_value", 0) or 0
        if avg_product_value >= 150:
            categories.append("value:premium")
        elif avg_product_value >= 75:
            categories.append("value:mid_market")
        else:
            categories.append("value:accessible")

        # Business impact categorization
        revenue_potential = float(
            collection_dict.get("collection_revenue_potential", 0) or 0
        )
        if revenue_potential >= 0.6:
            categories.append("business:high_impact")
        else:
            categories.append("business:standard")

        return categories[:7]  # Enhanced categories

    # ===== ADVANCED COLLECTION INTELLIGENCE =====

    def _calculate_collection_health_status(
        self, collection_dict: Dict[str, Any]
    ) -> str:
        """
        Calculate overall collection health using multiple optimized features
        """
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        popularity_score = float(
            collection_dict.get("collection_popularity_score", 0) or 0
        )
        conversion_rate = float(
            collection_dict.get("collection_conversion_rate", 0) or 0
        )
        recency_score = float(collection_dict.get("collection_recency_score", 0) or 0)
        diversity_score = float(collection_dict.get("product_diversity_score", 0) or 0)

        # Calculate comprehensive health score
        health_score = (
            engagement_score * 0.25
            + popularity_score * 0.20
            + conversion_rate * 0.25
            + recency_score * 0.20
            + diversity_score * 0.10
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

    def _calculate_strategic_value(self, collection_dict: Dict[str, Any]) -> str:
        """
        Determine strategic business value using engagement, revenue, and curation
        """
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        revenue_potential = float(
            collection_dict.get("collection_revenue_potential", 0) or 0
        )
        is_curated = collection_dict.get("is_curated_collection", True)
        size_tier = collection_dict.get("collection_size_tier", "minimal")

        # Strategic value calculation
        strategic_score = (engagement_score * 0.4) + (revenue_potential * 0.6)

        # Apply strategic bonuses
        if is_curated:
            strategic_score += 0.15  # Curated collections have strategic value

        if size_tier in ["large", "medium"]:
            strategic_score += 0.10  # Larger collections have more strategic impact

        # Classify strategic value
        if strategic_score >= 0.8:
            return "strategic_asset"
        elif strategic_score >= 0.6:
            return "valuable"
        elif strategic_score >= 0.4:
            return "useful"
        elif strategic_score >= 0.2:
            return "supportive"
        else:
            return "maintenance"

    def _calculate_growth_trajectory(self, collection_dict: Dict[str, Any]) -> str:
        """
        Calculate growth trajectory using recency and engagement trends
        """
        recency_score = float(collection_dict.get("collection_recency_score", 0) or 0)
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        popularity_score = float(
            collection_dict.get("collection_popularity_score", 0) or 0
        )

        # Growth indicators
        activity_indicator = recency_score * 0.4
        engagement_indicator = engagement_score * 0.3
        popularity_indicator = popularity_score * 0.3

        growth_score = activity_indicator + engagement_indicator + popularity_indicator

        if growth_score >= 0.8:
            return "accelerating"
        elif growth_score >= 0.6:
            return "growing"
        elif growth_score >= 0.4:
            return "steady"
        elif growth_score >= 0.2:
            return "declining"
        else:
            return "stagnant"

    def _calculate_user_appeal_factor(self, collection_dict: Dict[str, Any]) -> str:
        """
        Calculate user appeal using engagement and diversity metrics
        """
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        diversity_score = float(collection_dict.get("product_diversity_score", 0) or 0)
        popularity_score = float(
            collection_dict.get("collection_popularity_score", 0) or 0
        )

        # Appeal calculation - diverse collections with good engagement appeal to more users
        appeal_score = (
            engagement_score * 0.4 + diversity_score * 0.3 + popularity_score * 0.3
        )

        if appeal_score >= 0.8:
            return "mass_appeal"
        elif appeal_score >= 0.6:
            return "broad_appeal"
        elif appeal_score >= 0.4:
            return "targeted_appeal"
        elif appeal_score >= 0.2:
            return "niche_appeal"
        else:
            return "limited_appeal"

    # ===== PREDICTIVE LABELS =====

    def generate_predictive_labels(self, collection_dict: Dict[str, Any]) -> List[str]:
        """
        Generate predictive labels for advanced Gorse collection targeting

        These labels help Gorse make better collection recommendations
        """
        predictive_labels = []

        # Collection Health Status
        health = self._calculate_collection_health_status(collection_dict)
        predictive_labels.append(f"health:{health}")

        # Strategic Business Value
        strategic_value = self._calculate_strategic_value(collection_dict)
        predictive_labels.append(f"strategic:{strategic_value}")

        # Growth Trajectory
        growth = self._calculate_growth_trajectory(collection_dict)
        predictive_labels.append(f"growth:{growth}")

        # User Appeal Factor
        appeal = self._calculate_user_appeal_factor(collection_dict)
        predictive_labels.append(f"appeal:{appeal}")

        return predictive_labels

    # ===== BUSINESS INTELLIGENCE LABELS =====

    def generate_business_intelligence_labels(
        self, collection_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Generate business intelligence labels for strategic collection management
        """
        bi_labels = []

        # Revenue Impact Assessment
        revenue_potential = float(
            collection_dict.get("collection_revenue_potential", 0) or 0
        )
        conversion_rate = float(
            collection_dict.get("collection_conversion_rate", 0) or 0
        )

        revenue_impact_score = (revenue_potential + conversion_rate) / 2.0

        if revenue_impact_score >= 0.7:
            bi_labels.append("business_impact:revenue_driver")
        elif revenue_impact_score >= 0.4:
            bi_labels.append("business_impact:profitable")
        else:
            bi_labels.append("business_impact:cost_center")

        # Marketing Strategy
        engagement_score = float(
            collection_dict.get("collection_engagement_score", 0) or 0
        )
        popularity_score = float(
            collection_dict.get("collection_popularity_score", 0) or 0
        )

        marketing_potential = (engagement_score + popularity_score) / 2.0

        if marketing_potential >= 0.7:
            bi_labels.append("marketing:hero_candidate")
        elif marketing_potential >= 0.5:
            bi_labels.append("marketing:promotional_asset")
        elif marketing_potential >= 0.3:
            bi_labels.append("marketing:supporting_content")
        else:
            bi_labels.append("marketing:background_content")

        # Inventory Strategy
        size_tier = collection_dict.get("collection_size_tier", "minimal")
        diversity_score = float(collection_dict.get("product_diversity_score", 0) or 0)

        if size_tier in ["large", "medium"] and diversity_score >= 0.6:
            bi_labels.append("inventory:comprehensive_offering")
        elif size_tier == "small" and diversity_score <= 0.3:
            bi_labels.append("inventory:focused_offering")
        else:
            bi_labels.append("inventory:standard_offering")

        # Customer Acquisition Strategy
        conversion_rate = float(
            collection_dict.get("collection_conversion_rate", 0) or 0
        )
        avg_product_value = collection_dict.get("avg_product_value", 0) or 0

        if conversion_rate >= 0.15 and avg_product_value >= 100:
            bi_labels.append("acquisition:high_value_converter")
        elif conversion_rate >= 0.10:
            bi_labels.append("acquisition:good_converter")
        elif avg_product_value >= 150:
            bi_labels.append("acquisition:premium_showcase")
        else:
            bi_labels.append("acquisition:standard_entry")

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

        return cleaned_labels[:10]  # Maintain limit for collections

    # ===== COMPREHENSIVE TRANSFORMATION =====

    def transform_to_comprehensive_gorse_item(
        self, collection_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform to comprehensive Gorse collection item using ALL features and predictive labels
        """
        try:
            base_item = self.transform_to_gorse_item(collection_features, shop_id)
            if not base_item:
                return None

            if hasattr(collection_features, "__dict__"):
                collection_dict = collection_features.__dict__
            else:
                collection_dict = collection_features

            # Add predictive labels
            predictive_labels = self.generate_predictive_labels(collection_dict)
            bi_labels = self.generate_business_intelligence_labels(collection_dict)

            # Combine all labels
            all_labels = base_item["Labels"] + predictive_labels + bi_labels
            validated_labels = self.validate_label_quality(all_labels)

            base_item["Labels"] = validated_labels
            base_item["Comment"] = (
                f"Collection: {collection_dict.get('collection_id', '')} (comprehensive features + predictive + BI labels)"
            )

            return base_item

        except Exception as e:
            logger.error(
                f"Failed to create comprehensive Gorse collection item: {str(e)}"
            )
            return self.transform_to_gorse_item(
                collection_features, shop_id
            )  # Fallback

    def transform_batch_to_comprehensive_gorse_items(
        self, collection_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch to comprehensive Gorse collection items"""
        gorse_items = []

        for collection_features in collection_features_list:
            gorse_item = self.transform_to_comprehensive_gorse_item(
                collection_features, shop_id
            )
            if gorse_item:
                gorse_items.append(gorse_item)

        return gorse_items

    # ===== COLLECTION PERFORMANCE ANALYSIS =====

    def analyze_collection_portfolio(
        self, collection_features_list: List[Any]
    ) -> Dict[str, Any]:
        """
        Analyze entire collection portfolio for strategic insights
        """
        if not collection_features_list:
            return {"status": "empty_portfolio"}

        analysis = {
            "total_collections": len(collection_features_list),
            "performance_distribution": {
                "hero_collections": 0,
                "featured": 0,
                "high_priority": 0,
                "standard": 0,
                "secondary": 0,
                "niche": 0,
                "background": 0,
            },
            "health_distribution": {
                "excellent_health": 0,
                "good_health": 0,
                "fair_health": 0,
                "poor_health": 0,
                "critical_health": 0,
            },
            "strategic_recommendations": [],
        }

        # Analyze each collection
        for collection_features in collection_features_list:
            if hasattr(collection_features, "__dict__"):
                collection_dict = collection_features.__dict__
            else:
                collection_dict = collection_features

            # Priority analysis
            priority = self._calculate_comprehensive_recommendation_priority(
                collection_dict
            )
            analysis["performance_distribution"][priority] += 1

            # Health analysis
            health = self._calculate_collection_health_status(collection_dict)
            analysis["health_distribution"][health] += 1

        # Generate strategic recommendations
        total = analysis["total_collections"]

        hero_percentage = (
            analysis["performance_distribution"]["hero_collections"] / total
        )
        if hero_percentage < 0.05:  # Less than 5% hero collections
            analysis["strategic_recommendations"].append(
                "Consider promoting high-performing collections to hero status"
            )

        critical_health = analysis["health_distribution"]["critical_health"] / total
        if critical_health > 0.2:  # More than 20% critical health
            analysis["strategic_recommendations"].append(
                "Focus on improving or retiring underperforming collections"
            )

        return analysis
