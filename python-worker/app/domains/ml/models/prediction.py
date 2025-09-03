"""
ML prediction data model for BetterBundle Python Worker
"""

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field


class MLPrediction(BaseModel):
    """Represents a machine learning prediction"""
    
    id: str = Field(..., description="Unique prediction identifier")
    shop_id: str = Field(..., description="Shop identifier")
    model_id: str = Field(..., description="ID of the model used for prediction")
    entity_id: str = Field(..., description="ID of the entity being predicted")
    entity_type: str = Field(..., description="Type of entity (product, customer, order, collection)")
    
    # Prediction details
    prediction_type: str = Field(..., description="Type of prediction (classification, regression, recommendation)")
    prediction_value: Union[str, float, int, List[Any]] = Field(..., description="Predicted value")
    confidence_score: Optional[float] = Field(None, description="Confidence score for the prediction")
    
    # Classification predictions
    predicted_class: Optional[str] = Field(None, description="Predicted class for classification")
    class_probabilities: Optional[Dict[str, float]] = Field(None, description="Class probabilities")
    
    # Regression predictions
    predicted_value: Optional[float] = Field(None, description="Predicted numerical value")
    prediction_interval: Optional[Dict[str, float]] = Field(None, description="Prediction confidence interval")
    
    # Recommendation predictions
    recommended_items: Optional[List[Dict[str, Any]]] = Field(None, description="Recommended items")
    recommendation_scores: Optional[List[float]] = Field(None, description="Recommendation scores")
    
    # Input features
    input_features: Optional[Dict[str, Any]] = Field(None, description="Input features used for prediction")
    feature_importance: Optional[Dict[str, float]] = Field(None, description="Feature importance scores")
    
    # Model information
    model_version: Optional[str] = Field(None, description="Model version used")
    model_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional model metadata")
    
    # Performance metrics
    prediction_time_ms: Optional[float] = Field(None, description="Time taken for prediction in milliseconds")
    model_latency: Optional[float] = Field(None, description="Model inference latency")
    
    # Ground truth (if available)
    ground_truth: Optional[Union[str, float, int]] = Field(None, description="Actual/true value")
    prediction_error: Optional[float] = Field(None, description="Prediction error (if ground truth available)")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Prediction tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional prediction metadata")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When prediction was made")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When prediction was last updated")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def get_prediction_summary(self) -> Dict[str, Any]:
        """Get prediction summary"""
        summary = {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "prediction_type": self.prediction_type,
            "confidence_score": self.confidence_score,
            "created_at": self.created_at,
        }
        
        if self.prediction_type == "classification":
            summary["predicted_class"] = self.predicted_class
            summary["class_probabilities"] = self.class_probabilities
        elif self.prediction_type == "regression":
            summary["predicted_value"] = self.predicted_value
            summary["prediction_interval"] = self.prediction_interval
        elif self.prediction_type == "recommendation":
            summary["recommended_items"] = self.recommended_items
            summary["recommendation_scores"] = self.recommendation_scores
        
        return summary
    
    def add_ground_truth(self, ground_truth: Union[str, float, int]):
        """Add ground truth and calculate error"""
        self.ground_truth = ground_truth
        
        if self.prediction_type == "regression" and isinstance(ground_truth, (int, float)):
            if self.predicted_value is not None:
                self.prediction_error = abs(self.predicted_value - ground_truth)
        elif self.prediction_type == "classification" and isinstance(ground_truth, str):
            if self.predicted_class is not None:
                self.prediction_error = 0.0 if self.predicted_class == ground_truth else 1.0
        
        self.updated_at = datetime.utcnow()
    
    def update_confidence(self, confidence_score: float):
        """Update confidence score"""
        self.confidence_score = confidence_score
        self.updated_at = datetime.utcnow()
    
    def add_feature_importance(self, feature_importance: Dict[str, float]):
        """Add feature importance scores"""
        self.feature_importance = feature_importance
        self.updated_at = datetime.utcnow()
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if prediction has high confidence"""
        return self.confidence_score is not None and self.confidence_score >= threshold
    
    def get_top_features(self, top_k: int = 5) -> List[tuple]:
        """Get top k most important features"""
        if not self.feature_importance:
            return []
        
        sorted_features = sorted(
            self.feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return sorted_features[:top_k]
    
    def get_recommendation_summary(self) -> List[Dict[str, Any]]:
        """Get recommendation summary for recommendation predictions"""
        if self.prediction_type != "recommendation" or not self.recommended_items:
            return []
        
        summary = []
        for i, item in enumerate(self.recommended_items):
            summary_item = {
                "item": item,
                "score": self.recommendation_scores[i] if self.recommendation_scores else None,
                "rank": i + 1,
            }
            summary.append(summary_item)
        
        return summary
