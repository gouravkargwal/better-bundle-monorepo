"""
Gorse ML service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.domains.ml.models import MLFeatures, MLModel, MLTrainingJob, MLPrediction


class IGorseMLService(ABC):
    """Interface for Gorse ML operations"""

    @abstractmethod
    async def train_recommendation_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """
        Train a recommendation model using Gorse

        Args:
            shop_id: Shop ID
            features: ML features for training
            model_config: Model configuration
            training_params: Training parameters

        Returns:
            Training job instance
        """
        pass

    @abstractmethod
    async def train_classification_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        labels: List[Any],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """
        Train a classification model using Gorse

        Args:
            shop_id: Shop ID
            features: ML features for training
            labels: Target labels
            model_config: Model configuration
            training_params: Training parameters

        Returns:
            Training job instance
        """
        pass

    @abstractmethod
    async def train_regression_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        targets: List[float],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """
        Train a regression model using Gorse

        Args:
            shop_id: Shop ID
            features: ML features for training
            targets: Target values
            model_config: Model configuration
            training_params: Training parameters

        Returns:
            Training job instance
        """
        pass

    @abstractmethod
    async def get_recommendations(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        item_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        model_version: Optional[str] = None,
    ) -> List[MLPrediction]:
        """
        Get recommendations from trained model

        Args:
            shop_id: Shop ID
            user_id: User ID for personalized recommendations
            item_id: Item ID for item-based recommendations
            category: Category for category-based recommendations
            limit: Maximum number of recommendations
            model_version: Specific model version to use

        Returns:
            List of predictions
        """
        pass

    @abstractmethod
    async def predict_customer_segment(
        self,
        shop_id: str,
        customer_features: MLFeatures,
        model_version: Optional[str] = None,
    ) -> MLPrediction:
        """
        Predict customer segment

        Args:
            shop_id: Shop ID
            customer_features: Customer ML features
            model_version: Specific model version to use

        Returns:
            Prediction result
        """
        pass

    @abstractmethod
    async def predict_product_performance(
        self,
        shop_id: str,
        product_features: MLFeatures,
        model_version: Optional[str] = None,
    ) -> MLPrediction:
        """
        Predict product performance

        Args:
            shop_id: Shop ID
            product_features: Product ML features
            model_version: Specific model version to use

        Returns:
            Prediction result
        """
        pass

    @abstractmethod
    async def get_model_performance(
        self,
        shop_id: str,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get model performance metrics

        Args:
            shop_id: Shop ID
            model_id: Specific model ID
            model_version: Specific model version

        Returns:
            Performance metrics
        """
        pass

    @abstractmethod
    async def update_model(
        self,
        shop_id: str,
        model_id: str,
        new_features: List[MLFeatures],
        update_config: Dict[str, Any],
    ) -> MLTrainingJob:
        """
        Update existing model with new data

        Args:
            shop_id: Shop ID
            model_id: Model to update
            new_features: New features for update
            update_config: Update configuration

        Returns:
            Update training job
        """
        pass

    @abstractmethod
    async def deploy_model(
        self, shop_id: str, model_id: str, deployment_config: Dict[str, Any]
    ) -> bool:
        """
        Deploy model to production

        Args:
            shop_id: Shop ID
            model_id: Model to deploy
            deployment_config: Deployment configuration

        Returns:
            True if deployment successful
        """
        pass

    @abstractmethod
    async def rollback_model(
        self, shop_id: str, model_id: str, target_version: str
    ) -> bool:
        """
        Rollback model to previous version

        Args:
            shop_id: Shop ID
            model_id: Model to rollback
            target_version: Version to rollback to

        Returns:
            True if rollback successful
        """
        pass

    @abstractmethod
    async def get_model_versions(
        self, shop_id: str, model_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all versions of a model

        Args:
            shop_id: Shop ID
            model_id: Model ID

        Returns:
            List of model versions
        """
        pass

    @abstractmethod
    async def delete_model(self, shop_id: str, model_id: str) -> bool:
        """
        Delete a model

        Args:
            shop_id: Shop ID
            model_id: Model to delete

        Returns:
            True if deletion successful
        """
        pass

    @abstractmethod
    async def export_model(
        self, shop_id: str, model_id: str, export_format: str = "onnx"
    ) -> bytes:
        """
        Export model in specified format

        Args:
            shop_id: Shop ID
            model_id: Model to export
            export_format: Export format

        Returns:
            Model data as bytes
        """
        pass

    @abstractmethod
    async def import_model(
        self,
        shop_id: str,
        model_data: bytes,
        model_config: Dict[str, Any],
        import_format: str = "onnx",
    ) -> MLModel:
        """
        Import model from external source

        Args:
            shop_id: Shop ID
            model_data: Model data
            model_config: Model configuration
            import_format: Import format

        Returns:
            Imported model instance
        """
        pass

    @abstractmethod
    async def validate_model(
        self, shop_id: str, model_id: str, validation_data: List[MLFeatures]
    ) -> Dict[str, Any]:
        """
        Validate model performance on new data

        Args:
            shop_id: Shop ID
            model_id: Model to validate
            validation_data: Data for validation

        Returns:
            Validation results
        """
        pass

    @abstractmethod
    async def get_training_history(
        self, shop_id: str, model_id: Optional[str] = None, limit: int = 100
    ) -> List[MLTrainingJob]:
        """
        Get training history

        Args:
            shop_id: Shop ID
            model_id: Specific model ID
            limit: Maximum number of jobs

        Returns:
            List of training jobs
        """
        pass

    @abstractmethod
    async def cancel_training(self, shop_id: str, training_job_id: str) -> bool:
        """
        Cancel a training job

        Args:
            shop_id: Shop ID
            training_job_id: Job to cancel

        Returns:
            True if cancellation successful
        """
        pass
