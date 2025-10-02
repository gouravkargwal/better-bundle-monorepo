"""
Customer Behavior Feature Generator - STATE-OF-THE-ART VERSION
Generates ALL optimized behavioral features needed for comprehensive Gorse integration

Key improvements:
- Generates ALL 12 optimized user features used in enhanced transformers
- Advanced behavioral pattern recognition
- Purchase lifecycle modeling
- Churn risk assessment
- Category and interaction diversity analysis
- Temporal behavior analysis
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from collections import Counter
import statistics
import math
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerBehaviorFeatureGenerator(BaseFeatureGenerator):
    """
    State-of-the-art feature generator that creates ALL 12 optimized user features
    for maximum Gorse recommendation performance
    """

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, customer: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate ALL 12 optimized behavioral features for comprehensive Gorse integration

        Args:
            customer: Customer data from CustomerData table
            context: Contains user_interactions, orders, user_sessions

        Returns:
            Comprehensive feature set with all 12 optimized features
        """
        try:
            customer_id = customer.get("customer_id", "")
            logger.debug(
                f"Computing ALL optimized behavior features for customer: {customer_id}"
            )

            shop = context.get("shop", {})
            user_interactions = context.get("user_interactions", [])
            orders = context.get("orders", [])
            user_sessions = context.get("user_sessions", [])

            # If no data, return minimal features
            if not user_interactions and not orders:
                return self._get_comprehensive_minimal_features(customer, shop)

            features = {
                "shop_id": shop.get("id", ""),
                "customer_id": customer_id,
            }

            # === GENERATE ALL 12 OPTIMIZED USER FEATURES ===

            # 1. User Lifecycle Stage (Most critical)
            features.update(
                self._compute_user_lifecycle_stage(user_interactions, orders)
            )

            # 2. Purchase Frequency Score (0-1 normalized)
            features.update(self._compute_purchase_frequency_score(orders))

            # 3. Interaction Diversity Score (0-1 normalized)
            features.update(
                self._compute_interaction_diversity_score(user_interactions)
            )

            # 4. Category Diversity (Integer count)
            features.update(self._compute_category_diversity(user_interactions, orders))

            # 5. Primary Category (Most engaged category)
            features.update(self._compute_primary_category(user_interactions, orders))

            # 6. Conversion Rate (0-1 normalized)
            features.update(self._compute_conversion_rate(user_interactions, orders))

            # 7. Avg Order Value (Dollar amount)
            features.update(self._compute_avg_order_value(orders))

            # 8. Lifetime Value (Dollar amount)
            features.update(self._compute_lifetime_value(orders))

            # 9. Recency Score (0-1 normalized with temporal decay)
            features.update(self._compute_recency_score(user_interactions, orders))

            # 10. Churn Risk Score (0-1 normalized - CRITICAL)
            features.update(self._compute_churn_risk_score(user_interactions, orders))

            # 11. Total Interactions (Volume signal)
            features.update(self._compute_total_interactions(user_interactions))

            # 12. Days Since Last Purchase (Temporal signal)
            features.update(self._compute_days_since_last_purchase(orders))

            # Timestamp
            features["last_computed_at"] = now_utc()

            logger.debug(
                f"Computed ALL 12 optimized features for customer {customer_id}: "
                f"lifecycle={features.get('user_lifecycle_stage')}, "
                f"frequency={features.get('purchase_frequency_score'):.2f}, "
                f"diversity={features.get('interaction_diversity_score'):.2f}"
            )

            return features

        except Exception as e:
            logger.error(f"Failed to compute comprehensive behavior features: {str(e)}")
            return self._get_comprehensive_minimal_features(
                customer, context.get("shop", {})
            )

    # ===== ALL 12 OPTIMIZED FEATURE COMPUTATIONS =====

    def _compute_user_lifecycle_stage(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        1. USER LIFECYCLE STAGE - Most critical feature for Gorse

        Stages: new, repeat_active, repeat_dormant, one_time_buyer
        """
        total_purchases = len(orders)
        thirty_days_ago = now_utc() - timedelta(days=30)

        # Check recent activity
        recent_interactions = 0
        recent_purchases = 0

        for interaction in user_interactions:
            interaction_time = self._parse_datetime(interaction.get("created_at"))
            if interaction_time and interaction_time >= thirty_days_ago:
                recent_interactions += 1

        for order in orders:
            order_date = self._parse_datetime(order.get("order_date"))
            if order_date and order_date >= thirty_days_ago:
                recent_purchases += 1

        # Determine lifecycle stage
        if total_purchases == 0:
            if recent_interactions >= 5:
                lifecycle_stage = "new"  # Engaged but hasn't purchased
            else:
                lifecycle_stage = "new"  # Fresh user
        elif total_purchases == 1:
            if recent_purchases > 0 or recent_interactions >= 10:
                lifecycle_stage = "new_customer"  # Recently made first purchase
            else:
                lifecycle_stage = (
                    "one_time_buyer"  # Single purchase, no recent activity
                )
        elif total_purchases >= 2:
            if recent_purchases > 0 or recent_interactions >= 15:
                lifecycle_stage = "repeat_active"  # Active repeat customer
            else:
                lifecycle_stage = "repeat_dormant"  # Repeat customer but dormant
        else:
            lifecycle_stage = "unknown"

        return {"user_lifecycle_stage": lifecycle_stage}

    def _compute_purchase_frequency_score(
        self, orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        2. PURCHASE FREQUENCY SCORE (0-1) - Key loyalty indicator
        """
        if not orders:
            return {"purchase_frequency_score": 0.0}

        # Calculate time span of purchase activity
        order_dates = []
        for order in orders:
            order_date = self._parse_datetime(order.get("order_date"))
            if order_date:
                order_dates.append(order_date)

        if len(order_dates) < 2:
            # Single purchase gets minimal frequency score
            return {"purchase_frequency_score": 0.1 if len(order_dates) == 1 else 0.0}

        # Calculate purchase frequency (purchases per month)
        order_dates.sort()
        time_span = (order_dates[-1] - order_dates[0]).days

        if time_span <= 0:
            return {"purchase_frequency_score": 0.5}  # Multiple purchases same day

        # Purchases per month
        frequency_per_month = len(orders) / max(time_span / 30.0, 1.0)

        # Normalize: 2+ purchases per month = max score
        frequency_score = min(frequency_per_month / 2.0, 1.0)

        return {"purchase_frequency_score": round(frequency_score, 3)}

    def _compute_interaction_diversity_score(
        self, user_interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        3. INTERACTION DIVERSITY SCORE (0-1) - Engagement quality indicator
        """
        if not user_interactions:
            return {"interaction_diversity_score": 0.0}

        # Count different interaction types
        interaction_types = set()
        for interaction in user_interactions:
            interaction_type = interaction.get("interactionType", "")
            if interaction_type:
                interaction_types.add(interaction_type)

        # Expected interaction types for full engagement
        expected_types = {
            "product_viewed",
            "product_added_to_cart",
            "checkout_started",
            "search_performed",
            "category_browsed",
        }

        # Diversity score: ratio of actual to expected types
        diversity_score = len(interaction_types) / len(expected_types)
        diversity_score = min(diversity_score, 1.0)

        return {"interaction_diversity_score": round(diversity_score, 3)}

    def _compute_category_diversity(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        4. CATEGORY DIVERSITY - Number of distinct categories engaged with
        """
        categories_engaged = set()

        # From interactions
        for interaction in user_interactions:
            metadata = interaction.get("metadata", {})
            category = metadata.get("product_category") or metadata.get("category")
            if category:
                categories_engaged.add(str(category).lower())

        # From orders (if available)
        for order in orders:
            line_items = order.get("line_items", [])
            for item in line_items:
                category = item.get("product_category") or item.get("category")
                if category:
                    categories_engaged.add(str(category).lower())

        return {"category_diversity": len(categories_engaged)}

    def _compute_primary_category(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        5. PRIMARY CATEGORY - Most engaged product category
        """
        category_engagement = Counter()

        # Weight different engagement types
        for interaction in user_interactions:
            metadata = interaction.get("metadata", {})
            category = metadata.get("product_category") or metadata.get("category")
            interaction_type = interaction.get("interactionType", "")

            if category:
                category = str(category).lower()
                # Weight by engagement intensity
                if "purchase" in interaction_type:
                    category_engagement[category] += 5
                elif "cart" in interaction_type:
                    category_engagement[category] += 3
                elif "view" in interaction_type:
                    category_engagement[category] += 1

        # Add purchase weight from orders
        for order in orders:
            line_items = order.get("line_items", [])
            for item in line_items:
                category = item.get("product_category") or item.get("category")
                if category:
                    category_engagement[
                        str(category).lower()
                    ] += 10  # Purchases get highest weight

        if not category_engagement:
            return {"primary_category": None}

        primary_category = category_engagement.most_common(1)[0][0]
        return {"primary_category": primary_category}

    def _compute_conversion_rate(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        6. CONVERSION RATE (0-1) - Critical for purchase propensity
        """
        if not user_interactions:
            return {"conversion_rate": 0.0}

        # Count conversion-indicating interactions
        view_sessions = 0
        purchase_sessions = len(orders)  # Each order represents a conversion

        # Count unique product views (approximate sessions)
        unique_products_viewed = set()
        for interaction in user_interactions:
            if interaction.get("interactionType") == "product_viewed":
                metadata = interaction.get("metadata", {})
                product_id = metadata.get("product_id")
                if product_id:
                    unique_products_viewed.add(product_id)

        view_sessions = len(unique_products_viewed)

        if view_sessions == 0:
            return {"conversion_rate": 1.0 if purchase_sessions > 0 else 0.0}

        conversion_rate = purchase_sessions / view_sessions
        return {"conversion_rate": round(min(conversion_rate, 1.0), 3)}

    def _compute_avg_order_value(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        7. AVG ORDER VALUE - Important for value-based segmentation
        """
        if not orders:
            return {"avg_order_value": 0.0}

        order_values = []
        for order in orders:
            total_amount = float(order.get("total_amount", 0.0))
            if total_amount > 0:
                order_values.append(total_amount)

        if not order_values:
            return {"avg_order_value": 0.0}

        avg_value = statistics.mean(order_values)
        return {"avg_order_value": round(avg_value, 2)}

    def _compute_lifetime_value(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        8. LIFETIME VALUE - Total customer value
        """
        total_value = 0.0

        for order in orders:
            # Subtract refunds for net value
            total_amount = float(order.get("total_amount", 0.0))
            refunded_amount = float(order.get("total_refunded_amount", 0.0))
            net_amount = total_amount - refunded_amount
            total_value += net_amount

        return {"lifetime_value": round(max(total_value, 0.0), 2)}

    def _compute_recency_score(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        9. RECENCY SCORE (0-1) - Temporal engagement indicator with exponential decay
        """
        all_activity_dates = []

        # Collect all activity timestamps
        for interaction in user_interactions:
            created_at = self._parse_datetime(interaction.get("created_at"))
            if created_at:
                all_activity_dates.append(created_at)

        for order in orders:
            order_date = self._parse_datetime(order.get("order_date"))
            if order_date:
                all_activity_dates.append(order_date)

        if not all_activity_dates:
            return {"recency_score": 0.0}

        # Find most recent activity
        latest_activity = max(all_activity_dates)
        days_since_activity = (now_utc() - latest_activity).days

        # Exponential decay: 1.0 for today, 0.5 for 30 days, 0.1 for 90 days
        recency_score = math.exp(-days_since_activity / 45.0)  # 45-day half-life

        return {"recency_score": round(recency_score, 3)}

    def _compute_churn_risk_score(
        self, user_interactions: List[Dict[str, Any]], orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        10. CHURN RISK SCORE (0-1) - CRITICAL missing feature from your current system

        Predicts likelihood of customer churn based on behavioral patterns
        """
        if not orders and not user_interactions:
            return {"churn_risk_score": 1.0}  # New users have high churn risk

        thirty_days_ago = now_utc() - timedelta(days=30)
        sixty_days_ago = now_utc() - timedelta(days=60)

        # Recent activity analysis
        recent_interactions = 0
        older_interactions = 0
        recent_purchases = 0
        older_purchases = 0

        for interaction in user_interactions:
            interaction_time = self._parse_datetime(interaction.get("created_at"))
            if interaction_time:
                if interaction_time >= thirty_days_ago:
                    recent_interactions += 1
                elif interaction_time >= sixty_days_ago:
                    older_interactions += 1

        for order in orders:
            order_date = self._parse_datetime(order.get("order_date"))
            if order_date:
                if order_date >= thirty_days_ago:
                    recent_purchases += 1
                elif order_date >= sixty_days_ago:
                    older_purchases += 1

        # Calculate activity decline
        total_recent = recent_interactions + (
            recent_purchases * 5
        )  # Weight purchases more
        total_older = older_interactions + (older_purchases * 5)

        if total_older == 0:
            # New customer - moderate churn risk
            churn_risk = 0.6
        else:
            # Calculate activity ratio (recent vs older)
            activity_ratio = total_recent / total_older

            # Higher recent activity = lower churn risk
            if activity_ratio >= 1.0:
                churn_risk = 0.1  # Low risk - maintaining or increasing activity
            elif activity_ratio >= 0.5:
                churn_risk = 0.3  # Medium risk - some decline
            elif activity_ratio >= 0.2:
                churn_risk = 0.6  # High risk - significant decline
            else:
                churn_risk = 0.9  # Very high risk - major decline

        # Additional churn indicators
        if recent_purchases == 0 and len(orders) > 0:
            churn_risk = min(churn_risk + 0.2, 1.0)  # No recent purchases

        if recent_interactions == 0 and len(user_interactions) > 10:
            churn_risk = min(churn_risk + 0.3, 1.0)  # No recent interactions

        return {"churn_risk_score": round(min(churn_risk, 1.0), 3)}

    def _compute_total_interactions(
        self, user_interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        11. TOTAL INTERACTIONS - Volume signal for engagement level
        """
        return {"total_interactions": len(user_interactions)}

    def _compute_days_since_last_purchase(
        self, orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        12. DAYS SINCE LAST PURCHASE - Temporal purchase signal
        """
        if not orders:
            return {"days_since_last_purchase": None}

        # Find most recent purchase
        latest_purchase = None
        for order in orders:
            order_date = self._parse_datetime(order.get("order_date"))
            if order_date:
                if latest_purchase is None or order_date > latest_purchase:
                    latest_purchase = order_date

        if not latest_purchase:
            return {"days_since_last_purchase": None}

        days_since = (now_utc() - latest_purchase).days
        return {"days_since_last_purchase": days_since}

    # ===== HELPER COMPUTATION METHODS =====

    def _compute_engagement_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Legacy method - now calls interaction_diversity_score"""
        diversity_result = self._compute_interaction_diversity_score(interactions)

        return {
            "engagement_score": diversity_result["interaction_diversity_score"],
            "total_interaction_count": len(interactions),
            "interaction_type_count": len(
                set(i.get("interactionType", "") for i in interactions)
            ),
        }

    def _compute_recency_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Legacy method - now calls recency_score"""
        recency_result = self._compute_recency_score(interactions, [])

        # Calculate days since last interaction
        latest_time = None
        for interaction in interactions:
            created_at = self._parse_datetime(interaction.get("created_at"))
            if created_at:
                if latest_time is None or created_at > latest_time:
                    latest_time = created_at

        days_since_last = None
        if latest_time:
            days_since_last = (now_utc() - latest_time).days

        return {
            "recency_score": recency_result["recency_score"],
            # Ensure an integer (not None / SQL expression)
            "days_since_last_interaction": (
                int(days_since_last) if days_since_last is not None else 0
            ),
        }

    def _compute_conversion_metrics(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Legacy method - simplified version for backward compatibility"""
        views = sum(
            1 for i in interactions if "view" in i.get("interactionType", "").lower()
        )
        cart_adds = sum(
            1
            for i in interactions
            if "cart" in i.get("interactionType", "").lower()
            and "add" in i.get("interactionType", "").lower()
        )

        browse_to_cart_rate = (cart_adds / views) if views > 0 else 0.0

        return {
            "browse_to_cart_rate": round(browse_to_cart_rate, 3),
            "cart_to_purchase_rate": 0.0,  # Will be calculated from orders separately
            "conversion_propensity_score": browse_to_cart_rate,
        }

    def _compute_browsing_style(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enhanced browsing style computation"""
        views = sum(
            1 for i in interactions if "view" in i.get("interactionType", "").lower()
        )

        # Calculate products per session (approximate)
        unique_products = set()
        for interaction in interactions:
            metadata = interaction.get("metadata", {})
            product_id = metadata.get("product_id")
            if product_id:
                unique_products.add(product_id)

        exploration_ratio = len(unique_products) / max(views, 1) if views > 0 else 0

        if exploration_ratio >= 0.8:
            browsing_style = "explorer"
        elif exploration_ratio >= 0.5:
            browsing_style = "selective"
        elif exploration_ratio >= 0.2:
            browsing_style = "focused"
        else:
            browsing_style = "decisive"

        return {
            "browsing_style": browsing_style,
            "exploration_ratio": round(exploration_ratio, 3),
            "unique_products_viewed": len(unique_products),
        }

    def _compute_device_preference(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enhanced device preference with consistency scoring"""
        device_counts = Counter()

        for interaction in interactions:
            metadata = interaction.get("metadata", {})
            device_type = metadata.get("deviceType") or metadata.get("device_type")
            if device_type:
                device_counts[str(device_type).lower()] += 1

        if not device_counts:
            return {
                "primary_device": None,
                "device_consistency_score": 0.0,
            }

        primary_device = device_counts.most_common(1)[0][0]
        consistency = device_counts[primary_device] / sum(device_counts.values())

        return {
            "primary_device": primary_device,
            "device_consistency_score": round(consistency, 3),
        }

    # ===== COMPREHENSIVE MINIMAL FEATURES =====

    def _get_comprehensive_minimal_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return comprehensive minimal features when no interaction data exists"""
        return {
            "shop_id": shop.get("id", ""),
            "customer_id": customer.get("customer_id", ""),
            # ALL 12 optimized features with default values
            "user_lifecycle_stage": "new",
            "purchase_frequency_score": 0.0,
            "interaction_diversity_score": 0.0,
            "category_diversity": 0,
            "primary_category": None,
            "conversion_rate": 0.0,
            "avg_order_value": 0.0,
            "lifetime_value": 0.0,
            "recency_score": 0.0,
            "churn_risk_score": 0.8,  # New customers have high churn risk
            "total_interactions": 0,
            "days_since_last_purchase": None,
            # Legacy compatibility
            "engagement_score": 0.0,
            "total_interaction_count": 0,
            "interaction_type_count": 0,
            # Guarantee integer default for DB insert
            "days_since_last_interaction": 0,
            "browse_to_cart_rate": 0.0,
            "cart_to_purchase_rate": 0.0,
            "conversion_propensity_score": 0.0,
            "browsing_style": None,
            "exploration_ratio": 0.0,
            "unique_products_viewed": 0,
            "primary_device": None,
            "device_consistency_score": 0.0,
            "last_computed_at": now_utc(),
        }

    def _get_minimal_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Legacy method - calls comprehensive version"""
        return self._get_comprehensive_minimal_features(customer, shop)

    def _parse_datetime(self, datetime_str: Any) -> Optional[datetime]:
        """Enhanced datetime parsing with better error handling"""
        if not datetime_str:
            return None

        try:
            if isinstance(datetime_str, str):
                # Handle various ISO formats
                if datetime_str.endswith("Z"):
                    return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                elif "+" in datetime_str or datetime_str.endswith("UTC"):
                    return datetime.fromisoformat(datetime_str.replace("UTC", "+00:00"))
                else:
                    # Assume UTC if no timezone
                    dt = datetime.fromisoformat(datetime_str)
                    return dt.replace(tzinfo=timezone.utc)
            elif isinstance(datetime_str, datetime):
                # Ensure timezone aware
                if datetime_str.tzinfo is None:
                    return datetime_str.replace(tzinfo=timezone.utc)
                return datetime_str
            return None
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}': {str(e)}")
            return None

    # ===== VALIDATION METHODS =====

    def validate_feature_completeness(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that all 12 optimized features are present and valid"""
        required_features = [
            "user_lifecycle_stage",
            "purchase_frequency_score",
            "interaction_diversity_score",
            "category_diversity",
            "primary_category",
            "conversion_rate",
            "avg_order_value",
            "lifetime_value",
            "recency_score",
            "churn_risk_score",
            "total_interactions",
            "days_since_last_purchase",
        ]

        validation_results = {
            "all_features_present": True,
            "missing_features": [],
            "invalid_features": [],
            "feature_quality_score": 0.0,
        }

        present_features = 0
        for feature_name in required_features:
            if feature_name not in features:
                validation_results["missing_features"].append(feature_name)
                validation_results["all_features_present"] = False
            else:
                present_features += 1
                # Validate feature value
                value = features[feature_name]
                if value is None or (
                    isinstance(value, (int, float)) and math.isnan(value)
                ):
                    validation_results["invalid_features"].append(feature_name)

        validation_results["feature_quality_score"] = present_features / len(
            required_features
        )

        return validation_results

    async def generate_and_validate_features(
        self, customer: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate features with validation - recommended method"""
        features = await self.generate_features(customer, context)
        validation = self.validate_feature_completeness(features)

        features["_validation"] = validation

        if not validation["all_features_present"]:
            logger.warning(
                f"Customer {customer.get('customer_id', 'unknown')} missing features: "
                f"{validation['missing_features']}"
            )

        return features
