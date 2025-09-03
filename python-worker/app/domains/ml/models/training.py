"""
ML training job data model for BetterBundle Python Worker
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class MLTrainingJob(BaseModel):
    """Represents a machine learning training job"""
    
    id: str = Field(..., description="Unique training job identifier")
    shop_id: str = Field(..., description="Shop identifier")
    model_type: str = Field(..., description="Type of model to train")
    status: str = Field(..., description="Training status (pending, training, completed, failed, cancelled)")
    
    # Training configuration
    config: Dict[str, Any] = Field(default_factory=dict, description="Training configuration")
    training_params: Dict[str, Any] = Field(default_factory=dict, description="Training parameters")
    
    # Data information
    training_data_size: Optional[int] = Field(None, description="Number of training samples")
    validation_data_size: Optional[int] = Field(None, description="Number of validation samples")
    feature_count: Optional[int] = Field(None, description="Number of features")
    
    # Training progress
    current_epoch: Optional[int] = Field(None, description="Current training epoch")
    total_epochs: Optional[int] = Field(None, description="Total training epochs")
    progress_percentage: Optional[float] = Field(None, description="Training progress percentage")
    
    # Performance metrics
    training_loss: Optional[float] = Field(None, description="Current training loss")
    validation_loss: Optional[float] = Field(None, description="Current validation loss")
    training_accuracy: Optional[float] = Field(None, description="Current training accuracy")
    validation_accuracy: Optional[float] = Field(None, description="Current validation accuracy")
    
    # Training history
    loss_history: Optional[List[float]] = Field(None, description="Training loss history")
    accuracy_history: Optional[List[float]] = Field(None, description="Training accuracy history")
    validation_loss_history: Optional[List[float]] = Field(None, description="Validation loss history")
    validation_accuracy_history: Optional[List[float]] = Field(None, description="Validation accuracy history")
    
    # Results
    trained_model_id: Optional[str] = Field(None, description="ID of the trained model")
    final_metrics: Optional[Dict[str, float]] = Field(None, description="Final training metrics")
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error message if training failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")
    
    # Resource usage
    gpu_usage: Optional[float] = Field(None, description="GPU usage percentage")
    memory_usage: Optional[float] = Field(None, description="Memory usage in MB")
    cpu_usage: Optional[float] = Field(None, description="CPU usage percentage")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When job was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When job was last updated")
    started_at: Optional[datetime] = Field(None, description="When training started")
    completed_at: Optional[datetime] = Field(None, description="When training completed")
    cancelled_at: Optional[datetime] = Field(None, description="When training was cancelled")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional job metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def start_training(self):
        """Mark training as started"""
        self.status = "training"
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def complete_training(self, model_id: str, final_metrics: Dict[str, float]):
        """Mark training as completed"""
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.trained_model_id = model_id
        self.final_metrics = final_metrics
    
    def fail_training(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark training as failed"""
        self.status = "failed"
        self.updated_at = datetime.utcnow()
        self.error_message = error_message
        self.error_details = error_details or {}
    
    def cancel_training(self):
        """Cancel training"""
        self.status = "cancelled"
        self.cancelled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def update_progress(self, epoch: int, loss: float, accuracy: float, 
                       validation_loss: Optional[float] = None, 
                       validation_accuracy: Optional[float] = None):
        """Update training progress"""
        self.current_epoch = epoch
        self.training_loss = loss
        self.training_accuracy = accuracy
        
        if validation_loss is not None:
            self.validation_loss = validation_loss
        if validation_accuracy is not None:
            self.validation_accuracy = validation_accuracy
        
        if self.total_epochs:
            self.progress_percentage = (epoch / self.total_epochs) * 100
        
        self.updated_at = datetime.utcnow()
    
    def add_history_point(self, loss: float, accuracy: float, 
                         validation_loss: Optional[float] = None, 
                         validation_accuracy: Optional[float] = None):
        """Add a point to training history"""
        if self.loss_history is None:
            self.loss_history = []
        if self.accuracy_history is None:
            self.accuracy_history = []
        if self.validation_loss_history is None:
            self.validation_loss_history = []
        if self.validation_accuracy_history is None:
            self.validation_accuracy_history = []
        
        self.loss_history.append(loss)
        self.accuracy_history.append(accuracy)
        
        if validation_loss is not None:
            self.validation_loss_history.append(validation_loss)
        if validation_accuracy is not None:
            self.validation_accuracy_history.append(validation_accuracy)
    
    def is_running(self) -> bool:
        """Check if training is currently running"""
        return self.status == "training"
    
    def is_completed(self) -> bool:
        """Check if training is completed"""
        return self.status == "completed"
    
    def is_failed(self) -> bool:
        """Check if training failed"""
        return self.status == "failed"
    
    def is_cancelled(self) -> bool:
        """Check if training was cancelled"""
        return self.status == "cancelled"
    
    def get_job_summary(self) -> Dict[str, Any]:
        """Get training job summary"""
        return {
            "id": self.id,
            "model_type": self.model_type,
            "status": self.status,
            "progress": self.progress_percentage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "final_metrics": self.final_metrics,
            "error_message": self.error_message,
        }
