"""
ML Features model for BetterBundle Python Worker
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class MLFeatures(BaseModel):
    """Machine learning features model"""

    # Core identification
    id: str = Field(..., description="Unique feature set ID")
    shop_id: str = Field(..., description="Shop ID these features belong to")
    feature_type: str = Field(
        ..., description="Type of features (product, customer, order, etc.)"
    )
    entity_id: str = Field(..., description="ID of the entity these features describe")

    # Feature computation metadata
    computed_at: datetime = Field(
        default_factory=now_utc, description="When features were computed"
    )
    feature_version: str = Field(
        "1.0", description="Version of feature computation algorithm"
    )
    data_sources: List[str] = Field(
        default_factory=list, description="Data sources used for computation"
    )

    # Product-specific features
    product_features: Optional[Dict[str, Any]] = Field(
        None, description="Product-specific features"
    )
    variant_features: Optional[Dict[str, Any]] = Field(
        None, description="Variant-specific features"
    )
    collection_features: Optional[Dict[str, Any]] = Field(
        None, description="Collection-specific features"
    )

    # Customer-specific features
    customer_features: Optional[Dict[str, Any]] = Field(
        None, description="Customer-specific features"
    )
    behavior_features: Optional[Dict[str, Any]] = Field(
        None, description="Customer behavior features"
    )

    # Order-specific features
    order_features: Optional[Dict[str, Any]] = Field(
        None, description="Order-specific features"
    )

    # Advanced ML features
    advanced_features: Optional[Dict[str, Any]] = Field(
        None, description="Advanced ML features"
    )

    # Feature quality and validation
    feature_count: int = Field(0, description="Total number of features")
    missing_features: List[str] = Field(
        default_factory=list, description="Missing feature names"
    )
    feature_quality_score: Optional[float] = Field(
        None, description="Overall feature quality score (0-1)"
    )

    # ML pipeline integration
    used_in_training: bool = Field(
        False, description="Whether features were used in ML training"
    )
    training_job_ids: List[str] = Field(
        default_factory=list, description="Training jobs that used these features"
    )
    last_used_in_training: Optional[datetime] = Field(
        None, description="Last time used in training"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=now_utc, description="Feature set creation date"
    )
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @property
    def is_complete(self) -> bool:
        """Check if all expected features are present"""
        return len(self.missing_features) == 0

    @property
    def feature_completeness(self) -> float:
        """Get feature completeness percentage"""
        if self.feature_count == 0:
            return 0.0
        return (
            (self.feature_count - len(self.missing_features)) / self.feature_count
        ) * 100

    @property
    def age_days(self) -> int:
        """Get age of features in days"""
        return (now_utc() - self.computed_at).days

    @property
    def is_fresh(self) -> bool:
        """Check if features are fresh (less than 7 days old)"""
        return self.age_days < 7

    def get_feature_vector(self) -> Dict[str, Any]:
        """Get all features as a flat dictionary for ML training"""
        features = {}

        # Add product features
        if self.product_features:
            features.update(self.product_features)

        # Add variant features
        if self.variant_features:
            features.update(self.variant_features)

        # Add collection features
        if self.collection_features:
            features.update(self.collection_features)

        # Add customer features
        if self.customer_features:
            features.update(self.customer_features)

        # Add behavior features
        if self.behavior_features:
            features.update(self.behavior_features)

        # Add order features
        if self.order_features:
            features.update(self.order_features)

        # Add advanced features
        if self.advanced_features:
            features.update(self.advanced_features)

        # Add metadata features
        features.update(
            {
                "feature_count": self.feature_count,
                "feature_completeness": self.feature_completeness,
                "feature_quality_score": self.feature_quality_score or 0,
                "age_days": self.age_days,
                "is_fresh": self.is_fresh,
            }
        )

        return features

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names"""
        feature_vector = self.get_feature_vector()
        return list(feature_vector.keys())

    def get_numeric_features(self) -> Dict[str, float]:
        """Get only numeric features for ML training"""
        feature_vector = self.get_feature_vector()
        numeric_features = {}

        for name, value in feature_vector.items():
            if isinstance(value, (int, float)) and value is not None:
                numeric_features[name] = float(value)

        return numeric_features

    def get_categorical_features(self) -> Dict[str, str]:
        """Get only categorical features for ML training"""
        feature_vector = self.get_feature_vector()
        categorical_features = {}

        for name, value in feature_vector.items():
            if isinstance(value, str) and value is not None:
                categorical_features[name] = value

        return categorical_features

    def validate_features(self) -> Dict[str, Any]:
        """Validate feature quality and completeness"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "feature_count": self.feature_count,
            "missing_count": len(self.missing_features),
            "completeness_percentage": self.feature_completeness,
            "quality_score": self.feature_quality_score,
        }

        # Check for missing features
        if self.missing_features:
            validation_result["warnings"].append(
                f"Missing {len(self.missing_features)} features"
            )

        # Check feature quality
        if self.feature_quality_score is not None and self.feature_quality_score < 0.5:
            validation_result["warnings"].append("Low feature quality score")

        # Check feature freshness
        if not self.is_fresh:
            validation_result["warnings"].append(
                "Features are stale (older than 7 days)"
            )

        # Check feature count
        if self.feature_count == 0:
            validation_result["errors"].append("No features present")
            validation_result["is_valid"] = False

        return validation_result

    def mark_used_in_training(self, training_job_id: str) -> None:
        """Mark features as used in training"""
        self.used_in_training = True
        if training_job_id not in self.training_job_ids:
            self.training_job_ids.append(training_job_id)
        self.last_used_in_training = now_utc()
        self.updated_at = now_utc()

    def update_quality_score(self, score: float) -> None:
        """Update feature quality score"""
        if 0 <= score <= 1:
            self.feature_quality_score = score
            self.updated_at = now_utc()
        else:
            raise ValueError("Quality score must be between 0 and 1")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()

    def to_ml_format(self) -> Dict[str, Any]:
        """Convert to ML training format"""
        return {
            "features": self.get_feature_vector(),
            "metadata": {
                "id": self.id,
                "shop_id": self.shop_id,
                "entity_id": self.entity_id,
                "feature_type": self.feature_type,
                "computed_at": self.computed_at.isoformat(),
                "feature_version": self.feature_version,
            },
        }
