"""
ML model data model for BetterBundle Python Worker
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class MLModel(BaseModel):
    """Represents a trained machine learning model"""
    
    id: str = Field(..., description="Unique model identifier")
    shop_id: str = Field(..., description="Shop identifier")
    model_type: str = Field(..., description="Type of model (recommendation, classification, regression, ensemble)")
    model_name: str = Field(..., description="Human-readable model name")
    version: str = Field(..., description="Model version")
    status: str = Field(..., description="Model status (training, trained, deployed, failed)")
    
    # Model metadata
    description: Optional[str] = Field(None, description="Model description")
    tags: List[str] = Field(default_factory=list, description="Model tags")
    
    # Configuration and parameters
    config: Dict[str, Any] = Field(default_factory=dict, description="Model configuration")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Model hyperparameters")
    
    # Performance metrics
    metrics: Optional[Dict[str, float]] = Field(None, description="Model performance metrics")
    validation_score: Optional[float] = Field(None, description="Validation score")
    test_score: Optional[float] = Field(None, description="Test score")
    
    # Training information
    training_data_size: Optional[int] = Field(None, description="Number of training samples")
    feature_count: Optional[int] = Field(None, description="Number of features used")
    
    # Deployment information
    deployed_at: Optional[datetime] = Field(None, description="When model was deployed")
    deployment_config: Optional[Dict[str, Any]] = Field(None, description="Deployment configuration")
    
    # File storage
    model_file_path: Optional[str] = Field(None, description="Path to saved model file")
    model_file_size: Optional[int] = Field(None, description="Size of model file in bytes")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When model was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When model was last updated")
    trained_at: Optional[datetime] = Field(None, description="When training completed")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional model metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def update_status(self, new_status: str):
        """Update model status"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if new_status == "trained":
            self.trained_at = datetime.utcnow()
        elif new_status == "deployed":
            self.deployed_at = datetime.utcnow()
    
    def add_metrics(self, metrics: Dict[str, float]):
        """Add or update performance metrics"""
        if self.metrics is None:
            self.metrics = {}
        self.metrics.update(metrics)
        self.updated_at = datetime.utcnow()
    
    def is_deployed(self) -> bool:
        """Check if model is currently deployed"""
        return self.status == "deployed"
    
    def is_trained(self) -> bool:
        """Check if model training is complete"""
        return self.status == "trained"
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information summary"""
        return {
            "id": self.id,
            "name": self.model_name,
            "type": self.model_type,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metrics": self.metrics,
            "deployed": self.is_deployed(),
        }
