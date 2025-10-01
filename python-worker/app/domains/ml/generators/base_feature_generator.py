"""
Base feature generator class for ML feature engineering
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import statistics
import math

from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class BaseFeatureGenerator(ABC):
    """Base class for all feature generators"""

    def __init__(self):
        # Configuration constants (extracted from hardcoded values)
        self.hashing_modulus = 1000  # For hash-based feature encoding
        self.price_tier_thresholds = {
            "low": 25,  # Price < 25
            "mid": 100,  # Price < 100
            "high": float("inf"),  # Price >= 100
        }
        self.normalization_divisors = {
            "variant_count": 10.0,
            "image_count": 10.0,
            "tag_diversity": 10.0,
        }

    def _get_price_tier(self, price: float) -> str:
        """Convert price to tier using configurable thresholds"""
        if price < self.price_tier_thresholds["low"]:
            return "low"
        elif price < self.price_tier_thresholds["mid"]:
            return "mid"
        else:
            return "high"

    def _encode_categorical_feature(self, value: str) -> int:
        """Encode categorical feature using hash-based encoding"""
        if not value:
            return 0
        return hash(value) % self.hashing_modulus

    def _compute_basic_statistics(self, values: List[float]) -> Dict[str, float]:
        """Compute basic statistics for a list of values"""
        if not values:
            return {"mean": 0, "std": 0, "median": 0, "min": 0, "max": 0}

        return {
            "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }

    def _compute_time_based_features(
        self, created_at, updated_at=None
    ) -> Dict[str, int]:
        """Compute time-based features"""
        from datetime import datetime

        now = now_utc()

        # Handle both datetime objects and string timestamps
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created_at = None

        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                updated_at = None

        if created_at is None:
            return {
                "days_since_creation": 0,
                "is_recent": 0,
                "is_old": 0,
                "days_since_update": 0,
                "is_recently_updated": 0,
            }

        days_since_creation = (now - created_at).days

        features = {
            "days_since_creation": days_since_creation,
            "is_recent": 1 if days_since_creation < 30 else 0,
            "is_old": 1 if days_since_creation > 365 else 0,
        }

        if updated_at:
            days_since_update = (now - updated_at).days
            features.update(
                {
                    "days_since_update": days_since_update,
                    "is_recently_updated": 1 if days_since_update < 7 else 0,
                }
            )
        else:
            features.update(
                {
                    "days_since_update": 0,
                    "is_recently_updated": 0,
                }
            )

        return features

    def _normalize_feature(self, value: float, divisor: float = 1.0) -> float:
        """Normalize a feature value"""
        if divisor == 0:
            return 0
        return value / divisor

    @abstractmethod
    async def generate_features(
        self, entity: Any, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for the given entity

        Args:
            entity: The entity to generate features for
            context: Additional context data (shop, related entities, etc.)

        Returns:
            Dictionary of generated features
        """
        pass

    def validate_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generated features"""
        validated_features = {}

        # JSON fields that should preserve None values
        json_fields = {
            "search_terms",
            "top_products",
            "top_vendors",
            "top_categories",
            "product_pairs",
            "interaction_patterns",
            "session_data",
        }

        # DateTime fields that should preserve None values (not convert to 0)
        datetime_fields = {
            "last_occurrence",
            "last_viewed_at",
            "last_purchased_at",
            "first_purchased_at",
            "last_co_occurrence",
            "last_activity_at",
            "started_at",
            "completed_at",
            "paid_at",
            "expires_at",
            "last_analysis_at",
            "first_view_date",
            "last_view_date",
            "first_purchase_date",
            "last_purchase_date",
            "shopify_created_at",
            "shopify_updated_at",
            "product_created_at",
            "product_updated_at",
            "last_order_date",
            "created_at_shopify",
            "processed_at",
            "cancelled_at",
        }

        # String fields that should preserve None values (not convert to 0)
        string_fields = {
            # Snake_case fields (database model fields)
            "device_type",
            "primary_referrer",
            "referrer_domain",
            "landing_page",
            "exit_page",
            "preferred_category",
            "preferred_vendor",
            "price_point_preference",
            "customer_state",
            "geographic_region",
            "currency_preference",
            "browser_type",
            "os_type",
            "screen_resolution",
            "country",
            "region",
            "city",
            "timezone",
            "language",
            "referrer_type",
            "traffic_source",
            "customer_last_order_id",
            "customer_currency_code",
            "customer_locale",
            "price_tier",
            "product_type",
        }

        for key, value in features.items():
            # Debug: Check for SQLAlchemy objects that shouldn't be in the data
            if hasattr(value, "__class__") and "sqlalchemy" in str(
                value.__class__.__module__
            ):
                logger.warning(
                    f"Found SQLAlchemy object in field {key}: {type(value)} - {value}"
                )
                # Convert SQLAlchemy objects to None for string fields, 0 for others
                if key in string_fields:
                    validated_features[key] = None
                else:
                    validated_features[key] = 0
                continue

            if value is None:
                # Convert None to appropriate defaults
                if key in json_fields:
                    validated_features[key] = []  # Empty array for JSON list fields
                elif key in datetime_fields:
                    validated_features[key] = None  # Preserve None for DateTime fields
                elif key in string_fields:
                    validated_features[key] = None  # Preserve None for String fields
                else:
                    validated_features[key] = 0
            elif isinstance(value, (int, float)):
                # Handle NaN and infinity
                if math.isnan(value) or math.isinf(value):
                    validated_features[key] = 0
                else:
                    validated_features[key] = value
            else:
                validated_features[key] = value

        return validated_features
