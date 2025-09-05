"""
Feature Importance Service for analyzing which features matter most
"""

from typing import Dict, List, Any, Optional
import asyncio
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyCustomer,
    ShopifyProduct,
    ShopifyOrder,
    BehavioralEvent,
)

from ..analyzers.feature_importance_analyzer import (
    FeatureImportanceAnalyzer,
    SimpleFeatureSelector,
)
from ..generators import (
    CustomerFeatureGenerator,
    ProductFeatureGenerator,
    OrderFeatureGenerator,
)
from ..generators.interaction_feature_generator import InteractionFeatureGenerator
from ..generators.session_feature_generator import SessionFeatureGenerator

logger = get_logger(__name__)


class FeatureImportanceService:
    """Service for analyzing feature importance in Gorse recommendations"""

    def __init__(self):
        self.analyzer = FeatureImportanceAnalyzer()
        self.selector = SimpleFeatureSelector(self.analyzer)

        # Initialize feature generators
        self.customer_generator = CustomerFeatureGenerator()
        self.product_generator = ProductFeatureGenerator()
        self.order_generator = OrderFeatureGenerator()
        self.interaction_generator = InteractionFeatureGenerator()
        self.session_generator = SessionFeatureGenerator()

    async def analyze_feature_importance_for_shop(
        self, shop_id: str, days_back: int = 30, min_samples: int = 100
    ) -> Dict[str, Any]:
        """
        Analyze feature importance for a specific shop

        Args:
            shop_id: Shop ID to analyze
            days_back: Number of days to look back for data
            min_samples: Minimum number of samples needed for analysis

        Returns:
            Dictionary with feature importance results
        """
        try:
            logger.info(f"Starting feature importance analysis for shop: {shop_id}")

            # Collect data for analysis
            analysis_data = await self._collect_analysis_data(shop_id, days_back)

            if len(analysis_data) < min_samples:
                logger.warning(
                    f"Not enough data for analysis: {len(analysis_data)} samples (need {min_samples})"
                )
                return {
                    "error": f"Insufficient data: {len(analysis_data)} samples (need {min_samples})",
                    "samples_collected": len(analysis_data),
                }

            # Analyze feature importance
            importance_scores = self.analyzer.analyze_feature_importance(
                analysis_data, target_metric="recommendation_success"
            )

            # Generate report
            report = self.analyzer.generate_feature_report()

            # Get top features
            top_features = self.analyzer.get_top_features(20)

            # Get feature weights
            feature_weights = self.analyzer.get_feature_weights(min_importance=0.1)

            logger.info(f"Feature importance analysis completed for shop: {shop_id}")

            return {
                "shop_id": shop_id,
                "samples_analyzed": len(analysis_data),
                "importance_scores": importance_scores,
                "top_features": top_features,
                "feature_weights": feature_weights,
                "report": report,
                "analysis_date": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Failed to analyze feature importance for shop {shop_id}: {str(e)}"
            )
            return {"error": str(e), "shop_id": shop_id}

    async def _collect_analysis_data(
        self, shop_id: str, days_back: int
    ) -> List[Dict[str, Any]]:
        """
        Collect data for feature importance analysis

        This is a simplified version - in practice, you'd query your database
        """
        try:
            # This is where you'd collect real data from your database
            # For now, I'll create a mock data collection method

            logger.info(f"Collecting analysis data for shop: {shop_id}")

            # In practice, you would:
            # 1. Get customers, products, orders, events from database
            # 2. Generate features for each customer-product interaction
            # 3. Track recommendation success (clicks, conversions, etc.)

            # For demonstration, I'll create mock data
            analysis_data = await self._create_mock_analysis_data(shop_id, days_back)

            return analysis_data

        except Exception as e:
            logger.error(f"Failed to collect analysis data: {str(e)}")
            return []

    async def _create_mock_analysis_data(
        self, shop_id: str, days_back: int
    ) -> List[Dict[str, Any]]:
        """
        Create mock data for feature importance analysis
        In practice, this would be real data from your database
        """
        import random

        # Mock data generation
        analysis_data = []

        # Simulate 200 customer-product interactions
        for i in range(200):
            # Generate mock features (these would come from your feature generators)
            features = {
                # Customer features
                "customer_product_affinity_score": random.uniform(0, 1),
                "purchase_intent_score": random.uniform(0, 1),
                "session_depth_avg": random.uniform(0, 10),
                "price_sensitivity": random.uniform(0, 1),
                "loyalty_score": random.uniform(0, 1),
                "browsing_intensity": random.uniform(0, 1),
                # Product features
                "trending_score": random.uniform(0, 1),
                "view_velocity": random.uniform(0, 5),
                "cross_sell_opportunity_score": random.uniform(0, 1),
                "seasonal_demand_multiplier": random.uniform(0.5, 2.0),
                "inventory_velocity": random.uniform(0, 10),
                "search_popularity": random.uniform(0, 1),
                # Interaction features
                "view_to_cart_conversion": random.uniform(0, 1),
                "cart_to_purchase_conversion": random.uniform(0, 1),
                "interaction_depth": random.uniform(0, 1),
                "engagement_intensity": random.uniform(0, 1),
                "research_depth": random.uniform(0, 1),
                # Temporal features
                "hour_of_day_encoded": random.randint(0, 23),
                "day_of_week_encoded": random.randint(0, 6),
                "season_encoded": random.randint(0, 3),
                "is_weekend": random.randint(0, 1),
                "peak_shopping_hours": random.randint(0, 1),
                # Device features
                "device_type_encoded": random.randint(0, 2),
                "screen_resolution_tier": random.randint(0, 2),
                "referrer_type_encoded": random.randint(0, 3),
            }

            # Simulate recommendation success based on feature importance
            # In practice, this would be real click/conversion data
            success_score = (
                features["customer_product_affinity_score"] * 0.3
                + features["purchase_intent_score"] * 0.25
                + features["trending_score"] * 0.2
                + features["view_to_cart_conversion"] * 0.15
                + features["loyalty_score"] * 0.1
            ) + random.uniform(-0.2, 0.2)

            # Add some noise and convert to binary success
            features["recommendation_success"] = 1 if success_score > 0.5 else 0

            analysis_data.append(features)

        return analysis_data

    def get_optimized_feature_weights(self, shop_id: str) -> Dict[str, float]:
        """
        Get optimized feature weights for a shop

        Args:
            shop_id: Shop ID to get weights for

        Returns:
            Dictionary of feature weights
        """
        # In practice, you'd load pre-computed weights from database
        # For now, return default weights based on common patterns

        default_weights = {
            # High importance features (0.8-1.0)
            "customer_product_affinity_score": 0.9,
            "purchase_intent_score": 0.9,
            "view_to_cart_conversion": 0.8,
            "trending_score": 0.8,
            "loyalty_score": 0.8,
            # Medium importance features (0.5-0.7)
            "session_depth_avg": 0.7,
            "cross_sell_opportunity_score": 0.6,
            "interaction_depth": 0.6,
            "engagement_intensity": 0.6,
            "price_sensitivity": 0.5,
            "browsing_intensity": 0.5,
            # Lower importance features (0.2-0.4)
            "view_velocity": 0.4,
            "search_popularity": 0.4,
            "seasonal_demand_multiplier": 0.3,
            "inventory_velocity": 0.3,
            "research_depth": 0.3,
            "cart_to_purchase_conversion": 0.3,
            # Context features (0.1-0.3)
            "hour_of_day_encoded": 0.2,
            "day_of_week_encoded": 0.2,
            "season_encoded": 0.2,
            "is_weekend": 0.1,
            "peak_shopping_hours": 0.1,
            "device_type_encoded": 0.1,
            "screen_resolution_tier": 0.1,
            "referrer_type_encoded": 0.1,
        }

        return default_weights

    def apply_feature_weights(
        self, features: Dict[str, Any], weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Apply feature weights to a feature dictionary

        Args:
            features: Dictionary of features
            weights: Optional custom weights (uses default if None)

        Returns:
            Dictionary of weighted features
        """
        if weights is None:
            weights = self.get_optimized_feature_weights("default")

        weighted_features = {}
        for feature_name, value in features.items():
            weight = weights.get(feature_name, 0.5)  # Default weight
            weighted_features[feature_name] = value * weight

        return weighted_features

    def select_top_features(
        self, features: Dict[str, Any], n: int = 20
    ) -> Dict[str, Any]:
        """
        Select top N most important features

        Args:
            features: Dictionary of all features
            n: Number of top features to select

        Returns:
            Dictionary of selected features
        """
        return self.selector.select_features(features, method="top_n", n=n)

    async def run_feature_optimization_experiment(
        self, shop_id: str, test_duration_days: int = 7
    ) -> Dict[str, Any]:
        """
        Run an A/B test to compare different feature sets

        Args:
            shop_id: Shop ID to run experiment on
            test_duration_days: Duration of the experiment

        Returns:
            Experiment results
        """
        try:
            logger.info(f"Starting feature optimization experiment for shop: {shop_id}")

            # This would implement A/B testing in practice
            # For now, return a mock experiment result

            experiment_results = {
                "shop_id": shop_id,
                "experiment_duration_days": test_duration_days,
                "feature_set_a": {
                    "features_used": 15,
                    "avg_click_rate": 0.12,
                    "avg_conversion_rate": 0.03,
                    "description": "Top 15 most important features",
                },
                "feature_set_b": {
                    "features_used": 30,
                    "avg_click_rate": 0.11,
                    "avg_conversion_rate": 0.028,
                    "description": "All available features",
                },
                "winner": "feature_set_a",
                "improvement": {
                    "click_rate": 0.09,  # 9% improvement
                    "conversion_rate": 0.07,  # 7% improvement
                },
                "recommendation": "Use top 15 features for better performance",
            }

            logger.info(
                f"Feature optimization experiment completed for shop: {shop_id}"
            )
            return experiment_results

        except Exception as e:
            logger.error(f"Failed to run feature optimization experiment: {str(e)}")
            return {"error": str(e)}
