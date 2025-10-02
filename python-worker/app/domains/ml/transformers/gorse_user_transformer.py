"""
Gorse User Transformer - STATE-OF-THE-ART VERSION
Transforms optimized user features from CustomerBehaviorFeatureGenerator to Gorse user objects

Key improvements:
- Uses ALL 12 optimized user features from CustomerBehaviorFeatureGenerator
- Enhanced behavioral lifecycle stages with predictive signals
- Churn risk integration for proactive customer retention
- Intent-based segmentation for immediate actionability
- Advanced business value optimization
- Comprehensive label validation and quality control
"""

from typing import Dict, Any, List, Optional
import math
from app.core.logging import get_logger

logger = get_logger(__name__)


class GorseUserTransformer:
    """Transform optimized user features from CustomerBehaviorFeatureGenerator to Gorse user format"""

    def __init__(self):
        """Initialize user transformer"""
        pass

    def transform_to_gorse_user(
        self, user_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform optimized user features from CustomerBehaviorFeatureGenerator to Gorse user object

        Args:
            user_features: Optimized UserFeatures model or dict from CustomerBehaviorFeatureGenerator
            shop_id: Shop ID

        Returns:
            Gorse user object: {"UserId": "...", "Labels": [...]}
        """
        try:
            if hasattr(user_features, "__dict__"):
                user_dict = user_features.__dict__
            else:
                user_dict = user_features

            customer_id = user_dict.get("customer_id", "")
            if not customer_id:
                logger.warning("No customer_id found in user features")
                return None

            # Convert ALL optimized features from CustomerBehaviorFeatureGenerator to labels
            labels = self._convert_to_comprehensive_labels(user_dict)

            user_object = {
                "UserId": f"shop_{shop_id}_{customer_id}",
                "Labels": labels,
                "Comment": f"Customer: {customer_id} (using CustomerBehaviorFeatureGenerator features)",
            }

            logger.debug(
                f"Transformed user {customer_id} with {len(labels)} comprehensive labels from CustomerBehaviorFeatureGenerator"
            )

            return user_object

        except Exception as e:
            logger.error(
                f"Failed to transform user features from CustomerBehaviorFeatureGenerator: {str(e)}"
            )
            return None

    def transform_batch_to_gorse_users(
        self, user_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform multiple user features to Gorse user objects"""
        gorse_users = []

        for user_features in user_features_list:
            gorse_user = self.transform_to_gorse_user(user_features, shop_id)
            if gorse_user:
                gorse_users.append(gorse_user)

        logger.info(
            f"Transformed {len(gorse_users)} users with CustomerBehaviorFeatureGenerator features for shop {shop_id}"
        )
        return gorse_users

    def _convert_to_comprehensive_labels(self, user_dict: Dict[str, Any]) -> List[str]:
        """
        Convert ALL 12 optimized user features from CustomerBehaviorFeatureGenerator
        to comprehensive categorical labels for maximum Gorse performance

        Args:
            user_dict: ALL optimized user features from CustomerBehaviorFeatureGenerator

        Returns:
            List of comprehensive categorical labels using all features (max 12)
        """
        labels = []

        try:
            # ===== DIRECT MAPPING TO CustomerBehaviorFeatureGenerator FEATURES =====

            # 1. USER LIFECYCLE STAGE (from user_lifecycle_stage) - MOST CRITICAL
            lifecycle_stage = user_dict.get("user_lifecycle_stage", "new")
            labels.append(f"lifecycle:{lifecycle_stage}")

            # 2. PURCHASE FREQUENCY SCORE (from purchase_frequency_score)
            frequency_score = float(user_dict.get("purchase_frequency_score", 0) or 0)
            if frequency_score >= 0.8:
                labels.append("frequency:very_high")
            elif frequency_score >= 0.6:
                labels.append("frequency:high")
            elif frequency_score >= 0.4:
                labels.append("frequency:medium")
            elif frequency_score >= 0.2:
                labels.append("frequency:low")
            else:
                labels.append("frequency:minimal")

            # 3. INTERACTION DIVERSITY SCORE (from interaction_diversity_score)
            diversity_score = float(
                user_dict.get("interaction_diversity_score", 0) or 0
            )
            if diversity_score >= 0.7:
                labels.append("diversity:explorer")
            elif diversity_score >= 0.4:
                labels.append("diversity:selective")
            else:
                labels.append("diversity:focused")

            # 4. CATEGORY DIVERSITY (from category_diversity)
            category_diversity = int(user_dict.get("category_diversity", 0) or 0)
            if category_diversity >= 8:
                labels.append("categories:very_diverse")
            elif category_diversity >= 5:
                labels.append("categories:diverse")
            elif category_diversity >= 3:
                labels.append("categories:moderate")
            else:
                labels.append("categories:focused")

            # 5. PRIMARY CATEGORY (from primary_category)
            primary_category = user_dict.get("primary_category")
            if primary_category and str(primary_category).lower() not in [
                "none",
                "unknown",
                "",
            ]:
                clean_category = str(primary_category).lower().replace(" ", "_")[:20]
                labels.append(f"category:{clean_category}")

            # 6. CONVERSION RATE (from conversion_rate)
            conversion_rate = float(user_dict.get("conversion_rate", 0) or 0)
            if conversion_rate >= 0.2:
                labels.append("conversion:high_converter")
            elif conversion_rate >= 0.1:
                labels.append("conversion:moderate_converter")
            elif conversion_rate >= 0.05:
                labels.append("conversion:low_converter")
            else:
                labels.append("conversion:browser")

            # 7. AVG ORDER VALUE TIER (from avg_order_value)
            avg_order_value = float(user_dict.get("avg_order_value", 0) or 0)
            if avg_order_value >= 300:
                labels.append("aov:luxury")
            elif avg_order_value >= 150:
                labels.append("aov:premium")
            elif avg_order_value >= 75:
                labels.append("aov:mid_tier")
            elif avg_order_value >= 25:
                labels.append("aov:value")
            else:
                labels.append("aov:budget")

            # 8. LIFETIME VALUE TIER (from lifetime_value)
            lifetime_value = float(user_dict.get("lifetime_value", 0) or 0)
            if lifetime_value >= 2000:
                labels.append("ltv:vip")
            elif lifetime_value >= 1000:
                labels.append("ltv:high_value")
            elif lifetime_value >= 500:
                labels.append("ltv:valuable")
            elif lifetime_value >= 100:
                labels.append("ltv:growing")
            else:
                labels.append("ltv:new")

            # 9. RECENCY SCORE (from recency_score)
            recency_score = float(user_dict.get("recency_score", 0) or 0)
            if recency_score >= 0.8:
                labels.append("recency:very_active")
            elif recency_score >= 0.6:
                labels.append("recency:active")
            elif recency_score >= 0.3:
                labels.append("recency:warm")
            else:
                labels.append("recency:cold")

            # 10. CHURN RISK SCORE (from churn_risk_score - CRITICAL NEW FEATURE)
            churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)
            if churn_risk >= 0.7:
                labels.append("risk:high_churn")
            elif churn_risk >= 0.4:
                labels.append("risk:medium_churn")
            else:
                labels.append("risk:stable")

            # 11. TOTAL INTERACTIONS (from total_interactions - VOLUME SIGNAL)
            total_interactions = int(user_dict.get("total_interactions", 0) or 0)
            if total_interactions >= 100:
                labels.append("volume:high_engagement")
            elif total_interactions >= 50:
                labels.append("volume:moderate_engagement")
            elif total_interactions >= 20:
                labels.append("volume:low_engagement")
            else:
                labels.append("volume:minimal_engagement")

            # 12. DAYS SINCE LAST PURCHASE (from days_since_last_purchase - TEMPORAL)
            days_since_last = user_dict.get("days_since_last_purchase")
            if days_since_last is not None:
                if days_since_last <= 7:
                    labels.append("last_purchase:this_week")
                elif days_since_last <= 30:
                    labels.append("last_purchase:this_month")
                elif days_since_last <= 90:
                    labels.append("last_purchase:this_quarter")
                else:
                    labels.append("last_purchase:dormant")

        except Exception as e:
            logger.error(
                f"Error converting CustomerBehaviorFeatureGenerator features to labels: {str(e)}"
            )

        return labels[:12]  # ALL 12 optimized features as labels

    # ===== ADVANCED BEHAVIORAL PATTERN ANALYSIS =====

    def _calculate_advanced_purchase_intent_enhanced(
        self, user_dict: Dict[str, Any]
    ) -> str:
        """
        Advanced purchase intent using CustomerBehaviorFeatureGenerator features

        Combines lifecycle, recency, conversion efficiency, and churn risk from enhanced generator
        """
        lifecycle_stage = user_dict.get("user_lifecycle_stage", "new")
        recency_score = float(user_dict.get("recency_score", 0) or 0)
        conversion_rate = float(user_dict.get("conversion_rate", 0) or 0)
        churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)

        # Calculate composite intent score using enhanced features
        if lifecycle_stage in ["repeat_active", "new_customer"]:
            lifecycle_boost = 0.3
        elif lifecycle_stage == "repeat_dormant":
            lifecycle_boost = -0.2  # Negative boost for dormant
        else:
            lifecycle_boost = 0.0

        # Churn risk penalty (high churn risk = low purchase intent)
        churn_penalty = churn_risk * -0.3

        intent_score = (
            (recency_score * 0.4)
            + (conversion_rate * 0.4)
            + lifecycle_boost
            + churn_penalty
        )

        if intent_score >= 0.8:
            return "immediate"
        elif intent_score >= 0.6:
            return "very_high"
        elif intent_score >= 0.4:
            return "high"
        elif intent_score >= 0.2:
            return "medium"
        else:
            return "low"

    def _calculate_comprehensive_shopping_pattern_enhanced(
        self, user_dict: Dict[str, Any]
    ) -> str:
        """
        Comprehensive shopping pattern using CustomerBehaviorFeatureGenerator features
        """
        interaction_diversity = float(
            user_dict.get("interaction_diversity_score", 0) or 0
        )
        purchase_frequency = float(user_dict.get("purchase_frequency_score", 0) or 0)
        conversion_rate = float(user_dict.get("conversion_rate", 0) or 0)
        category_diversity = int(user_dict.get("category_diversity", 0) or 0)
        total_interactions = int(user_dict.get("total_interactions", 0) or 0)
        churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)

        # Enhanced pattern classification using CustomerBehaviorFeatureGenerator features
        if purchase_frequency >= 0.7 and conversion_rate >= 0.2:
            return "power_buyer"  # High frequency + high conversion
        elif interaction_diversity >= 0.7 and category_diversity >= 5:
            return "curious_explorer"  # High diversity across categories
        elif conversion_rate >= 0.15 and total_interactions <= 30:
            return "efficient_buyer"  # High conversion with low browsing
        elif total_interactions >= 100 and conversion_rate <= 0.05:
            return "research_browser"  # High browsing, low conversion
        elif purchase_frequency >= 0.4:
            return "regular_customer"  # Steady purchase pattern
        elif interaction_diversity >= 0.4:
            return "selective_shopper"  # Moderate diversity
        elif churn_risk >= 0.7:
            return "at_risk_customer"  # High churn risk pattern
        else:
            return "casual_visitor"  # Basic engagement

    def _calculate_business_value_tier_enhanced(self, user_dict: Dict[str, Any]) -> str:
        """
        Enhanced business value tier using CustomerBehaviorFeatureGenerator features
        """
        lifetime_value = float(user_dict.get("lifetime_value", 0) or 0)
        avg_order_value = float(user_dict.get("avg_order_value", 0) or 0)
        purchase_frequency = float(user_dict.get("purchase_frequency_score", 0) or 0)
        churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)

        # Composite business value score with churn risk adjustment
        ltv_score = min(lifetime_value / 2000.0, 1.0)  # Normalize to $2000
        aov_score = min(avg_order_value / 300.0, 1.0)  # Normalize to $300
        frequency_score = purchase_frequency  # Already 0-1
        churn_penalty = churn_risk * -0.2  # High churn risk reduces business value

        business_score = (
            (ltv_score * 0.4)
            + (aov_score * 0.3)
            + (frequency_score * 0.2)
            + churn_penalty
            + 0.1
        )

        if business_score >= 0.8:
            return "vip_tier"
        elif business_score >= 0.6:
            return "high_value_tier"
        elif business_score >= 0.4:
            return "valuable_tier"
        elif business_score >= 0.2:
            return "growing_tier"
        else:
            return "entry_tier"

    # ===== RECOMMENDATION READINESS ASSESSMENT =====

    def _calculate_recommendation_readiness_enhanced(
        self, user_dict: Dict[str, Any]
    ) -> str:
        """
        Calculate recommendation readiness using CustomerBehaviorFeatureGenerator features

        Critical for Gorse's recommendation engine optimization
        """
        total_interactions = int(user_dict.get("total_interactions", 0) or 0)
        category_diversity = int(user_dict.get("category_diversity", 0) or 0)
        interaction_diversity = float(
            user_dict.get("interaction_diversity_score", 0) or 0
        )
        purchase_frequency = float(user_dict.get("purchase_frequency_score", 0) or 0)
        recency_score = float(user_dict.get("recency_score", 0) or 0)
        lifecycle_stage = user_dict.get("user_lifecycle_stage", "new")
        churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)

        # Calculate comprehensive readiness score
        interaction_signal = min(
            total_interactions / 20.0, 1.0
        )  # 20+ interactions = good
        diversity_signal = min(category_diversity / 4.0, 1.0)  # 4+ categories = good
        quality_signal = interaction_diversity  # Already 0-1
        activity_signal = (purchase_frequency + recency_score) / 2.0

        # Lifecycle stage bonus
        lifecycle_bonus = (
            0.2 if lifecycle_stage in ["repeat_active", "new_customer"] else 0.0
        )

        # Churn risk penalty
        churn_penalty = churn_risk * -0.15

        readiness_score = (
            interaction_signal * 0.25
            + diversity_signal * 0.20
            + quality_signal * 0.20
            + activity_signal * 0.25
            + lifecycle_bonus
            + churn_penalty
        )

        if readiness_score >= 0.8:
            return "highly_ready"
        elif readiness_score >= 0.6:
            return "ready"
        elif readiness_score >= 0.4:
            return "partially_ready"
        elif readiness_score >= 0.2:
            return "warming_up"
        else:
            return "cold_start"

    # ===== PREDICTIVE LABELS =====

    def generate_predictive_labels_enhanced(
        self, user_dict: Dict[str, Any]
    ) -> List[str]:
        """
        Generate predictive labels using CustomerBehaviorFeatureGenerator features

        These labels help Gorse make better future predictions using enhanced behavioral data
        """
        predictive_labels = []

        # Purchase Intent Prediction (using enhanced method)
        intent = self._calculate_advanced_purchase_intent_enhanced(user_dict)
        predictive_labels.append(f"intent:{intent}")

        # Shopping Pattern Prediction (using enhanced method)
        pattern = self._calculate_comprehensive_shopping_pattern_enhanced(user_dict)
        predictive_labels.append(f"pattern:{pattern}")

        # Business Value Prediction (using enhanced method)
        value_tier = self._calculate_business_value_tier_enhanced(user_dict)
        predictive_labels.append(f"value_tier:{value_tier}")

        # Recommendation Readiness (using enhanced method)
        readiness = self._calculate_recommendation_readiness_enhanced(user_dict)
        predictive_labels.append(f"readiness:{readiness}")

        return predictive_labels

    # ===== CHURN RISK ANALYSIS =====

    def _analyze_churn_indicators(self, user_dict: Dict[str, Any]) -> List[str]:
        """
        Analyze churn indicators using CustomerBehaviorFeatureGenerator churn_risk_score

        Provides actionable churn prevention labels
        """
        churn_labels = []

        churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)
        recency_score = float(user_dict.get("recency_score", 0) or 0)
        lifecycle_stage = user_dict.get("user_lifecycle_stage", "new")
        days_since_last_purchase = user_dict.get("days_since_last_purchase")

        # Churn risk classification
        if churn_risk >= 0.8:
            churn_labels.append("churn_urgency:critical")
        elif churn_risk >= 0.6:
            churn_labels.append("churn_urgency:high")
        elif churn_risk >= 0.4:
            churn_labels.append("churn_urgency:moderate")
        else:
            churn_labels.append("churn_urgency:low")

        # Churn prevention strategy
        if churn_risk >= 0.7 and lifecycle_stage in ["repeat_active", "repeat_dormant"]:
            churn_labels.append("prevention_strategy:retention_campaign")
        elif churn_risk >= 0.6 and recency_score <= 0.3:
            churn_labels.append("prevention_strategy:reactivation_needed")
        elif churn_risk >= 0.4:
            churn_labels.append("prevention_strategy:engagement_boost")

        # Win-back opportunity
        if (
            days_since_last_purchase
            and days_since_last_purchase >= 90
            and churn_risk >= 0.6
        ):
            churn_labels.append("winback:opportunity")

        return churn_labels

    # ===== COMPREHENSIVE TRANSFORMATION =====

    def transform_to_comprehensive_gorse_user(
        self, user_features, shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform to comprehensive Gorse user using ALL CustomerBehaviorFeatureGenerator features
        """
        try:
            base_user = self.transform_to_gorse_user(user_features, shop_id)
            if not base_user:
                return None

            if hasattr(user_features, "__dict__"):
                user_dict = user_features.__dict__
            else:
                user_dict = user_features

            # Add enhanced predictive labels using CustomerBehaviorFeatureGenerator
            predictive_labels = self.generate_predictive_labels_enhanced(user_dict)
            churn_labels = self._analyze_churn_indicators(user_dict)

            # Combine all labels
            all_labels = base_user["Labels"] + predictive_labels + churn_labels
            validated_labels = self.validate_label_quality(all_labels)

            base_user["Labels"] = validated_labels
            base_user["Comment"] = (
                f"Customer: {user_dict.get('customer_id', '')} (comprehensive CustomerBehaviorFeatureGenerator features)"
            )

            return base_user

        except Exception as e:
            logger.error(f"Failed to create comprehensive Gorse user: {str(e)}")
            return self.transform_to_gorse_user(user_features, shop_id)  # Fallback

    def transform_batch_to_comprehensive_gorse_users(
        self, user_features_list: List[Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Transform batch to comprehensive Gorse users using CustomerBehaviorFeatureGenerator"""
        gorse_users = []

        for user_features in user_features_list:
            gorse_user = self.transform_to_comprehensive_gorse_user(
                user_features, shop_id
            )
            if gorse_user:
                gorse_users.append(gorse_user)

        logger.info(
            f"Transformed {len(gorse_users)} users with comprehensive CustomerBehaviorFeatureGenerator features for shop {shop_id}"
        )
        return gorse_users

    # ===== BUSINESS INTELLIGENCE INTEGRATION =====

    def analyze_user_portfolio(self, user_features_list: List[Any]) -> Dict[str, Any]:
        """
        Analyze entire user portfolio using CustomerBehaviorFeatureGenerator features
        """
        if not user_features_list:
            return {"status": "empty_portfolio"}

        analysis = {
            "total_users": len(user_features_list),
            "lifecycle_distribution": {},
            "churn_risk_distribution": {},
            "business_value_distribution": {},
            "strategic_insights": [],
        }

        # Analyze each user
        for user_features in user_features_list:
            if hasattr(user_features, "__dict__"):
                user_dict = user_features.__dict__
            else:
                user_dict = user_features

            # Lifecycle analysis
            lifecycle = user_dict.get("user_lifecycle_stage", "unknown")
            analysis["lifecycle_distribution"][lifecycle] = (
                analysis["lifecycle_distribution"].get(lifecycle, 0) + 1
            )

            # Churn risk analysis
            churn_risk = float(user_dict.get("churn_risk_score", 0) or 0)
            if churn_risk >= 0.7:
                risk_category = "high_risk"
            elif churn_risk >= 0.4:
                risk_category = "medium_risk"
            else:
                risk_category = "stable"
            analysis["churn_risk_distribution"][risk_category] = (
                analysis["churn_risk_distribution"].get(risk_category, 0) + 1
            )

            # Business value analysis
            value_tier = self._calculate_business_value_tier_enhanced(user_dict)
            analysis["business_value_distribution"][value_tier] = (
                analysis["business_value_distribution"].get(value_tier, 0) + 1
            )

        # Generate strategic insights
        total = analysis["total_users"]

        # Churn risk insights
        high_risk_percentage = (
            analysis["churn_risk_distribution"].get("high_risk", 0) / total
        )
        if high_risk_percentage > 0.15:  # More than 15% high churn risk
            analysis["strategic_insights"].append(
                "URGENT: High churn risk detected - implement retention campaigns"
            )

        # Lifecycle insights
        new_user_percentage = analysis["lifecycle_distribution"].get("new", 0) / total
        if new_user_percentage > 0.4:  # More than 40% new users
            analysis["strategic_insights"].append(
                "Opportunity: High new user acquisition - focus on onboarding optimization"
            )

        # Business value insights
        vip_percentage = (
            analysis["business_value_distribution"].get("vip_tier", 0) / total
        )
        if vip_percentage < 0.05:  # Less than 5% VIP users
            analysis["strategic_insights"].append(
                "Growth: Low VIP segment - implement value tier upgrade strategies"
            )

        return analysis

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

        return cleaned_labels[:16]  # Allow up to 16 labels for comprehensive features

    def validate_feature_compatibility(
        self, user_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate compatibility with CustomerBehaviorFeatureGenerator features
        """
        required_features = [
            "user_lifecycle_stage",
            "purchase_frequency_score",
            "interaction_diversity_score",
            "category_diversity",
            "conversion_rate",
            "avg_order_value",
            "lifetime_value",
            "recency_score",
            "churn_risk_score",  # Critical new feature
            "total_interactions",
        ]

        compatibility = {
            "compatible": True,
            "missing_features": [],
            "feature_coverage": 0.0,
        }

        present_features = 0
        for feature in required_features:
            if feature in user_dict:
                present_features += 1
            else:
                compatibility["missing_features"].append(feature)

        compatibility["feature_coverage"] = present_features / len(required_features)
        compatibility["compatible"] = (
            compatibility["feature_coverage"] >= 0.8
        )  # 80% coverage required

        return compatibility

    # ===== BACKWARD COMPATIBILITY =====

    def generate_predictive_labels(self, user_dict: Dict[str, Any]) -> List[str]:
        """Legacy method - calls enhanced version"""
        return self.generate_predictive_labels_enhanced(user_dict)

    def _calculate_advanced_purchase_intent(self, user_dict: Dict[str, Any]) -> str:
        """Legacy method - calls enhanced version"""
        return self._calculate_advanced_purchase_intent_enhanced(user_dict)

    def _calculate_comprehensive_shopping_pattern(
        self, user_dict: Dict[str, Any]
    ) -> str:
        """Legacy method - calls enhanced version"""
        return self._calculate_comprehensive_shopping_pattern_enhanced(user_dict)

    def _calculate_business_value_tier(self, user_dict: Dict[str, Any]) -> str:
        """Legacy method - calls enhanced version"""
        return self._calculate_business_value_tier_enhanced(user_dict)

    def _calculate_recommendation_readiness(self, user_dict: Dict[str, Any]) -> str:
        """Legacy method - calls enhanced version"""
        return self._calculate_recommendation_readiness_enhanced(user_dict)
