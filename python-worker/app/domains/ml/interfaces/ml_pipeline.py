"""
ML pipeline service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    BehavioralEvent,
)
from app.domains.ml.models import MLFeatures, MLModel, MLTrainingJob, MLPrediction


class IMLPipelineService(ABC):
    """Interface for ML pipeline operations"""

    @abstractmethod
    async def run_feature_engineering_pipeline(
        self, shop_id: str, shop_data: Dict[str, Any], pipeline_config: Dict[str, Any]
    ) -> Dict[str, List[MLFeatures]]:
        """
        Run complete feature engineering pipeline

        Args:
            shop_id: Shop ID
            shop_data: Raw shop data from collection
            pipeline_config: Pipeline configuration

        Returns:
            Dictionary mapping entity types to ML features
        """
        pass

    @abstractmethod
    async def run_ml_training_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        training_config: Dict[str, Any],
    ) -> Dict[str, MLTrainingJob]:
        """
        Run complete ML training pipeline

        Args:
            shop_id: Shop ID
            features: ML features for training
            training_config: Training configuration

        Returns:
            Dictionary mapping model types to training jobs
        """
        pass

    @abstractmethod
    async def run_prediction_pipeline(
        self, shop_id: str, features: MLFeatures, prediction_config: Dict[str, Any]
    ) -> Dict[str, MLPrediction]:
        """
        Run complete prediction pipeline

        Args:
            shop_id: Shop ID
            features: ML features for prediction
            prediction_config: Prediction configuration

        Returns:
            Dictionary mapping prediction types to results
        """
        pass

    @abstractmethod
    async def run_end_to_end_pipeline(
        self, shop_id: str, shop_data: Dict[str, Any], pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run complete end-to-end ML pipeline

        Args:
            shop_id: Shop ID
            shop_data: Raw shop data from collection
            pipeline_config: Complete pipeline configuration

        Returns:
            Complete pipeline results including features, training, and predictions
        """
        pass

    @abstractmethod
    async def run_incremental_update_pipeline(
        self,
        shop_id: str,
        new_data: Dict[str, Any],
        existing_features: Dict[str, List[MLFeatures]],
        update_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run incremental update pipeline

        Args:
            shop_id: Shop ID
            new_data: New data since last run
            existing_features: Previously computed features
            update_config: Update configuration

        Returns:
            Updated features and models
        """
        pass

    @abstractmethod
    async def run_model_evaluation_pipeline(
        self, shop_id: str, model_ids: List[str], evaluation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run model evaluation pipeline

        Args:
            shop_id: Shop ID
            model_ids: Models to evaluate
            evaluation_config: Evaluation configuration

        Returns:
            Evaluation results for all models
        """
        pass

    @abstractmethod
    async def run_model_deployment_pipeline(
        self, shop_id: str, model_id: str, deployment_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run model deployment pipeline

        Args:
            shop_id: Shop ID
            model_id: Model to deploy
            deployment_config: Deployment configuration

        Returns:
            Deployment results
        """
        pass

    @abstractmethod
    async def run_ab_testing_pipeline(
        self,
        shop_id: str,
        model_a_id: str,
        model_b_id: str,
        ab_test_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run A/B testing pipeline

        Args:
            shop_id: Shop ID
            model_a_id: First model for testing
            model_b_id: Second model for testing
            ab_test_config: A/B testing configuration

        Returns:
            A/B testing results
        """
        pass

    @abstractmethod
    async def run_model_monitoring_pipeline(
        self, shop_id: str, model_ids: List[str], monitoring_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run model monitoring pipeline

        Args:
            shop_id: Shop ID
            model_ids: Models to monitor
            monitoring_config: Monitoring configuration

        Returns:
            Monitoring results and alerts
        """
        pass

    @abstractmethod
    async def run_data_quality_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        quality_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run data quality assessment pipeline

        Args:
            shop_id: Shop ID
            features: Features to assess
            quality_config: Quality assessment configuration

        Returns:
            Data quality metrics and recommendations
        """
        pass

    @abstractmethod
    async def run_feature_selection_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        selection_config: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """
        Run feature selection pipeline

        Args:
            shop_id: Shop ID
            features: Features to analyze
            selection_config: Feature selection configuration

        Returns:
            Selected feature names for each entity type
        """
        pass

    @abstractmethod
    async def run_hyperparameter_optimization_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        optimization_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run hyperparameter optimization pipeline

        Args:
            shop_id: Shop ID
            features: Features for optimization
            optimization_config: Optimization configuration

        Returns:
            Optimized hyperparameters for each model type
        """
        pass

    @abstractmethod
    async def run_model_ensemble_pipeline(
        self, shop_id: str, model_ids: List[str], ensemble_config: Dict[str, Any]
    ) -> MLModel:
        """
        Run model ensemble pipeline

        Args:
            shop_id: Shop ID
            model_ids: Models to ensemble
            ensemble_config: Ensemble configuration

        Returns:
            Ensemble model
        """
        pass

    @abstractmethod
    async def get_pipeline_status(
        self, shop_id: str, pipeline_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get pipeline execution status

        Args:
            shop_id: Shop ID
            pipeline_id: Specific pipeline ID

        Returns:
            Pipeline status information
        """
        pass

    @abstractmethod
    async def cancel_pipeline(self, shop_id: str, pipeline_id: str) -> bool:
        """
        Cancel a running pipeline

        Args:
            shop_id: Shop ID
            pipeline_id: Pipeline to cancel

        Returns:
            True if cancellation successful
        """
        pass

    @abstractmethod
    async def get_pipeline_history(
        self, shop_id: str, pipeline_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get pipeline execution history

        Args:
            shop_id: Shop ID
            pipeline_type: Type of pipeline
            limit: Maximum number of executions

        Returns:
            List of pipeline executions
        """
        pass

    @abstractmethod
    async def validate_pipeline_config(
        self, pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate pipeline configuration

        Args:
            pipeline_config: Configuration to validate

        Returns:
            Validation results
        """
        pass

    @abstractmethod
    async def estimate_pipeline_runtime(
        self, shop_id: str, pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Estimate pipeline runtime

        Args:
            shop_id: Shop ID
            pipeline_config: Pipeline configuration

        Returns:
            Runtime estimates for each pipeline stage
        """
        pass
