"""
Feature Importance Analyzer for Gorse ML system
Automatically discovers which features are most important
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from sklearn.feature_selection import mutual_info_regression, f_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import statistics

from app.core.logging import get_logger

logger = get_logger(__name__)


class FeatureImportanceAnalyzer:
    """Analyzes feature importance using multiple ML techniques"""

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_importance_scores = {}

    def analyze_feature_importance(
        self,
        features_data: List[Dict[str, Any]],
        target_metric: str = "recommendation_success",
    ) -> Dict[str, float]:
        """
        Analyze feature importance using multiple techniques

        Args:
            features_data: List of feature dictionaries with target metrics
            target_metric: The metric to predict (e.g., 'click_rate', 'conversion_rate')

        Returns:
            Dictionary of feature names to importance scores
        """
        try:
            logger.info(
                f"Analyzing feature importance for {len(features_data)} samples"
            )

            # Convert to DataFrame
            df = pd.DataFrame(features_data)

            if target_metric not in df.columns:
                logger.error(f"Target metric '{target_metric}' not found in data")
                return {}

            # Separate features and target
            feature_columns = [col for col in df.columns if col != target_metric]
            X = df[feature_columns]
            y = df[target_metric]

            # Remove any non-numeric columns
            numeric_columns = X.select_dtypes(include=[np.number]).columns
            X_numeric = X[numeric_columns]

            if len(numeric_columns) == 0:
                logger.error("No numeric features found for analysis")
                return {}

            # Fill missing values
            X_numeric = X_numeric.fillna(0)
            y = y.fillna(0)

            logger.info(f"Analyzing {len(numeric_columns)} numeric features")

            # Run multiple importance analyses
            results = {}

            # 1. Correlation Analysis
            correlation_scores = self._correlation_analysis(X_numeric, y)
            results["correlation"] = correlation_scores

            # 2. Mutual Information
            mi_scores = self._mutual_information_analysis(X_numeric, y)
            results["mutual_information"] = mi_scores

            # 3. Random Forest Importance
            rf_scores = self._random_forest_analysis(X_numeric, y)
            results["random_forest"] = rf_scores

            # 4. F-Score Analysis
            f_scores = self._f_score_analysis(X_numeric, y)
            results["f_score"] = f_scores

            # Combine all methods
            combined_scores = self._combine_importance_scores(results)

            # Store for later use
            self.feature_importance_scores = combined_scores

            logger.info(f"Feature importance analysis completed. Top 5 features:")
            top_features = sorted(
                combined_scores.items(), key=lambda x: x[1], reverse=True
            )[:5]
            for feature, score in top_features:
                logger.info(f"  {feature}: {score:.3f}")

            return combined_scores

        except Exception as e:
            logger.error(f"Failed to analyze feature importance: {str(e)}")
            return {}

    def _correlation_analysis(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Calculate correlation between features and target"""
        correlations = {}
        for column in X.columns:
            try:
                correlation = abs(X[column].corr(y))
                correlations[column] = correlation if not np.isnan(correlation) else 0.0
            except:
                correlations[column] = 0.0
        return correlations

    def _mutual_information_analysis(
        self, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        """Calculate mutual information between features and target"""
        try:
            # Standardize features
            X_scaled = self.scaler.fit_transform(X)

            # Calculate mutual information
            mi_scores = mutual_info_regression(X_scaled, y, random_state=42)

            # Create dictionary
            mi_dict = {}
            for i, column in enumerate(X.columns):
                mi_dict[column] = mi_scores[i] if not np.isnan(mi_scores[i]) else 0.0

            return mi_dict
        except Exception as e:
            logger.warning(f"Mutual information analysis failed: {str(e)}")
            return {col: 0.0 for col in X.columns}

    def _random_forest_analysis(
        self, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        """Calculate feature importance using Random Forest"""
        try:
            # Train Random Forest
            rf = RandomForestRegressor(n_estimators=100, random_state=42)
            rf.fit(X, y)

            # Get feature importance
            importance_dict = {}
            for i, column in enumerate(X.columns):
                importance_dict[column] = rf.feature_importances_[i]

            return importance_dict
        except Exception as e:
            logger.warning(f"Random Forest analysis failed: {str(e)}")
            return {col: 0.0 for col in X.columns}

    def _f_score_analysis(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Calculate F-scores for feature importance"""
        try:
            # Calculate F-scores
            f_scores, _ = f_regression(X, y)

            # Normalize F-scores
            f_scores = f_scores / np.sum(f_scores) if np.sum(f_scores) > 0 else f_scores

            # Create dictionary
            f_dict = {}
            for i, column in enumerate(X.columns):
                f_dict[column] = f_scores[i] if not np.isnan(f_scores[i]) else 0.0

            return f_dict
        except Exception as e:
            logger.warning(f"F-score analysis failed: {str(e)}")
            return {col: 0.0 for col in X.columns}

    def _combine_importance_scores(
        self, results: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Combine multiple importance scores into a single score"""
        all_features = set()
        for method_scores in results.values():
            all_features.update(method_scores.keys())

        combined_scores = {}
        for feature in all_features:
            scores = []
            for method, method_scores in results.items():
                if feature in method_scores:
                    scores.append(method_scores[feature])

            if scores:
                # Use median to be robust to outliers
                combined_scores[feature] = statistics.median(scores)
            else:
                combined_scores[feature] = 0.0

        # Normalize scores to 0-1 range
        if combined_scores:
            max_score = max(combined_scores.values())
            if max_score > 0:
                combined_scores = {k: v / max_score for k, v in combined_scores.items()}

        return combined_scores

    def get_feature_weights(self, min_importance: float = 0.1) -> Dict[str, float]:
        """
        Get feature weights based on importance analysis

        Args:
            min_importance: Minimum importance score to include feature

        Returns:
            Dictionary of feature weights
        """
        if not self.feature_importance_scores:
            logger.warning(
                "No feature importance scores available. Run analyze_feature_importance first."
            )
            return {}

        # Filter features by minimum importance
        filtered_features = {
            feature: score
            for feature, score in self.feature_importance_scores.items()
            if score >= min_importance
        }

        logger.info(
            f"Selected {len(filtered_features)} features with importance >= {min_importance}"
        )

        return filtered_features

    def get_top_features(self, n: int = 20) -> List[str]:
        """
        Get top N most important features

        Args:
            n: Number of top features to return

        Returns:
            List of feature names ordered by importance
        """
        if not self.feature_importance_scores:
            logger.warning(
                "No feature importance scores available. Run analyze_feature_importance first."
            )
            return []

        sorted_features = sorted(
            self.feature_importance_scores.items(), key=lambda x: x[1], reverse=True
        )

        return [feature for feature, score in sorted_features[:n]]

    def generate_feature_report(self) -> str:
        """Generate a human-readable feature importance report"""
        if not self.feature_importance_scores:
            return "No feature importance analysis available."

        report = "=== FEATURE IMPORTANCE REPORT ===\n\n"

        # Top 10 features
        top_features = sorted(
            self.feature_importance_scores.items(), key=lambda x: x[1], reverse=True
        )[:10]

        report += "TOP 10 MOST IMPORTANT FEATURES:\n"
        for i, (feature, score) in enumerate(top_features, 1):
            report += f"{i:2d}. {feature:<40} {score:.3f}\n"

        # Feature categories
        report += "\nFEATURE CATEGORIES:\n"
        categories = {
            "Customer Features": [
                f
                for f in self.feature_importance_scores.keys()
                if f.startswith("customer_") or f.startswith("session_")
            ],
            "Product Features": [
                f
                for f in self.feature_importance_scores.keys()
                if f.startswith("product_") or f.startswith("trending_")
            ],
            "Interaction Features": [
                f
                for f in self.feature_importance_scores.keys()
                if f.startswith("interaction_") or f.startswith("affinity_")
            ],
            "Temporal Features": [
                f
                for f in self.feature_importance_scores.keys()
                if "time" in f or "season" in f or "hour" in f
            ],
        }

        for category, features in categories.items():
            if features:
                avg_importance = np.mean(
                    [self.feature_importance_scores[f] for f in features]
                )
                report += f"{category:<20} {len(features):2d} features, avg importance: {avg_importance:.3f}\n"

        return report


class SimpleFeatureSelector:
    """Simple feature selection based on importance scores"""

    def __init__(self, importance_analyzer: FeatureImportanceAnalyzer):
        self.analyzer = importance_analyzer

    def select_features(
        self, features: Dict[str, Any], method: str = "top_n", **kwargs
    ) -> Dict[str, Any]:
        """
        Select features based on importance

        Args:
            features: Dictionary of all features
            method: Selection method ("top_n", "threshold", "percentile")
            **kwargs: Method-specific parameters

        Returns:
            Dictionary of selected features
        """
        if method == "top_n":
            n = kwargs.get("n", 20)
            top_features = self.analyzer.get_top_features(n)
            return {k: v for k, v in features.items() if k in top_features}

        elif method == "threshold":
            threshold = kwargs.get("threshold", 0.1)
            weights = self.analyzer.get_feature_weights(threshold)
            return {k: v for k, v in features.items() if k in weights}

        elif method == "percentile":
            percentile = kwargs.get("percentile", 80)  # Top 20%
            importance_scores = self.analyzer.feature_importance_scores
            if not importance_scores:
                return features

            threshold = np.percentile(list(importance_scores.values()), percentile)
            return {
                k: v
                for k, v in features.items()
                if importance_scores.get(k, 0) >= threshold
            }

        else:
            logger.warning(f"Unknown selection method: {method}")
            return features
