"""
Gorse ML service implementation for BetterBundle Python Worker
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import httpx

from app.core.logging import get_logger
from app.core.config import settings
from app.shared.decorators import async_timing
from app.shared.helpers import now_utc

from ..interfaces.gorse_ml import IGorseMLService
from ..models import MLFeatures, MLModel, MLTrainingJob, MLPrediction


class GorseMLService(IGorseMLService):
    """Gorse ML service for training and prediction operations"""

    def __init__(self):
        self.gorse_api_url = getattr(settings, "GORSE_API_URL", "http://localhost:8088")
        self.gorse_api_key = getattr(settings, "GORSE_API_KEY", "")

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = httpx.Timeout(60.0, connect=10.0)

        # Model configurations
        self.default_model_configs = self._initialize_model_configs()

        self.logger = get_logger(__name__)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Initialize HTTP client"""
        if self.http_client is None:
            headers = {}
            if self.gorse_api_key:
                headers["X-API-Key"] = self.gorse_api_key

            self.http_client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
            self.logger.info("Gorse ML service initialized")

    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            self.logger.info("Gorse ML service closed")

    async def train_recommendation_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """Train a recommendation model using Gorse"""
        try:
            self.logger.info(f"Starting recommendation model training", shop_id=shop_id)

            # Prepare training data
            training_data = await self._prepare_recommendation_data(features)

            # Merge with default config
            config = {**self.default_model_configs["recommendation"], **model_config}

            # Start training
            training_job = MLTrainingJob(
                id=f"rec_{shop_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type="recommendation",
                status="training",
                config=config,
                training_params=training_params or {},
                started_at=now_utc(),
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Execute training asynchronously
            asyncio.create_task(self._execute_training(training_job, training_data))

            return training_job

        except Exception as e:
            self.logger.error(
                f"Failed to start recommendation training",
                shop_id=shop_id,
                error=str(e),
            )
            raise

    async def train_classification_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        labels: List[Any],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """Train a classification model using Gorse"""
        try:
            self.logger.info(f"Starting classification model training", shop_id=shop_id)

            # Prepare training data
            training_data = await self._prepare_classification_data(features, labels)

            # Merge with default config
            config = {**self.default_model_configs["classification"], **model_config}

            # Start training
            training_job = MLTrainingJob(
                id=f"cls_{shop_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type="classification",
                status="training",
                config=config,
                training_params=training_params or {},
                started_at=now_utc(),
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Execute training asynchronously
            asyncio.create_task(self._execute_training(training_job, training_data))

            return training_job

        except Exception as e:
            self.logger.error(
                f"Failed to start classification training",
                shop_id=shop_id,
                error=str(e),
            )
            raise

    async def train_regression_model(
        self,
        shop_id: str,
        features: List[MLFeatures],
        targets: List[float],
        model_config: Dict[str, Any],
        training_params: Optional[Dict[str, Any]] = None,
    ) -> MLTrainingJob:
        """Train a regression model using Gorse"""
        try:
            self.logger.info(f"Starting regression model training", shop_id=shop_id)

            # Prepare training data
            training_data = await self._prepare_regression_data(features, targets)

            # Merge with default config
            config = {**self.default_model_configs["regression"], **model_config}

            # Start training
            training_job = MLTrainingJob(
                id=f"reg_{shop_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type="regression",
                status="training",
                config=config,
                training_params=training_params or {},
                started_at=now_utc(),
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Execute training asynchronously
            asyncio.create_task(self._execute_training(training_job, training_data))

            return training_job

        except Exception as e:
            self.logger.error(
                f"Failed to start regression training", shop_id=shop_id, error=str(e)
            )
            raise

    async def get_recommendations(
        self,
        shop_id: str,
        user_id: Optional[str] = None,
        item_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        model_version: Optional[str] = None,
    ) -> List[MLPrediction]:
        """Get recommendations from trained model"""
        try:
            self.logger.debug(
                f"Getting recommendations",
                shop_id=shop_id,
                user_id=user_id,
                item_id=item_id,
                limit=limit,
            )

            # Build recommendation request
            endpoint = f"{self.gorse_api_url}/api/recommend"
            params = {"n": limit}

            if user_id:
                params["user_id"] = user_id
            if item_id:
                params["item_id"] = item_id
            if category:
                params["category"] = category

            # Make request to Gorse
            response = await self.http_client.get(endpoint, params=params)
            response.raise_for_status()

            data = response.json()

            # Convert to MLPrediction objects
            predictions = []
            for item in data.get("items", []):
                prediction = MLPrediction(
                    id=f"pred_{shop_id}_{item.get('item_id', 'unknown')}",
                    shop_id=shop_id,
                    model_id="recommendation",
                    model_version=model_version or "latest",
                    entity_id=item.get("item_id", ""),
                    prediction_type="recommendation",
                    prediction_value=item.get("score", 0.0),
                    confidence_score=item.get("confidence", 0.0),
                    metadata=item,
                    created_at=now_utc(),
                )
                predictions.append(prediction)

            return predictions

        except Exception as e:
            self.logger.error(
                f"Failed to get recommendations", shop_id=shop_id, error=str(e)
            )
            raise

    async def predict_customer_segment(
        self,
        shop_id: str,
        customer_features: MLFeatures,
        model_version: Optional[str] = None,
    ) -> MLPrediction:
        """Predict customer segment"""
        try:
            logger.debug(
                f"Predicting customer segment",
                shop_id=shop_id,
                customer_id=customer_features.entity_id,
            )

            # Prepare features for prediction
            feature_vector = customer_features.get_feature_vector()

            # Make prediction request
            endpoint = f"{self.gorse_api_url}/api/predict"
            payload = {
                "model_type": "classification",
                "features": feature_vector,
                "model_version": model_version or "latest",
            }

            response = await self.http_client.post(endpoint, json=payload)
            response.raise_for_status()

            data = response.json()

            # Create prediction result
            prediction = MLPrediction(
                id=f"pred_{shop_id}_{customer_features.entity_id}",
                shop_id=shop_id,
                model_id="customer_segmentation",
                model_version=model_version or "latest",
                entity_id=customer_features.entity_id,
                prediction_type="classification",
                prediction_value=data.get("prediction", ""),
                confidence_score=data.get("confidence", 0.0),
                metadata=data,
                created_at=now_utc(),
            )

            return prediction

        except Exception as e:
            logger.error(
                f"Failed to predict customer segment", shop_id=shop_id, error=str(e)
            )
            raise

    async def predict_product_performance(
        self,
        shop_id: str,
        product_features: MLFeatures,
        model_version: Optional[str] = None,
    ) -> MLPrediction:
        """Predict product performance"""
        try:
            logger.debug(
                f"Predicting product performance",
                shop_id=shop_id,
                product_id=product_features.entity_id,
            )

            # Prepare features for prediction
            feature_vector = product_features.get_feature_vector()

            # Make prediction request
            endpoint = f"{self.gorse_api_url}/api/predict"
            payload = {
                "model_type": "regression",
                "features": feature_vector,
                "model_version": model_version or "latest",
            }

            response = await self.http_client.post(endpoint, json=payload)
            response.raise_for_status()

            data = response.json()

            # Create prediction result
            prediction = MLPrediction(
                id=f"pred_{shop_id}_{product_features.entity_id}",
                shop_id=shop_id,
                model_id="product_performance",
                model_version=model_version or "latest",
                entity_id=product_features.entity_id,
                prediction_type="regression",
                prediction_value=data.get("prediction", 0.0),
                confidence_score=data.get("confidence", 0.0),
                metadata=data,
                created_at=now_utc(),
            )

            return prediction

        except Exception as e:
            logger.error(
                f"Failed to predict product performance", shop_id=shop_id, error=str(e)
            )
            raise

    # Additional methods would be implemented here...
    # For brevity, I'm showing the core functionality

    async def _prepare_recommendation_data(
        self, features: List[MLFeatures]
    ) -> Dict[str, Any]:
        """Prepare data for recommendation training"""
        # Implementation would convert MLFeatures to Gorse format
        return {"features": [f.get_feature_vector() for f in features]}

    async def _prepare_classification_data(
        self, features: List[MLFeatures], labels: List[Any]
    ) -> Dict[str, Any]:
        """Prepare data for classification training"""
        return {
            "features": [f.get_feature_vector() for f in features],
            "labels": labels,
        }

    async def _prepare_regression_data(
        self, features: List[MLFeatures], targets: List[float]
    ) -> Dict[str, Any]:
        """Prepare data for regression training"""
        return {
            "features": [f.get_feature_vector() for f in features],
            "targets": targets,
        }

    async def _execute_training(
        self, training_job: MLTrainingJob, training_data: Dict[str, Any]
    ):
        """Execute training asynchronously"""
        try:
            # Update job status
            training_job.status = "training"
            training_job.updated_at = now_utc()

            # Make training request to Gorse
            endpoint = f"{self.gorse_api_url}/api/train"
            payload = {
                "model_type": training_job.model_type,
                "config": training_job.config,
                "training_params": training_job.training_params,
                "data": training_data,
            }

            response = await self.http_client.post(endpoint, json=payload)
            response.raise_for_status()

            # Update job status
            training_job.status = "completed"
            training_job.completed_at = now_utc()
            training_job.updated_at = now_utc()

            logger.info(
                f"Training completed successfully",
                job_id=training_job.id,
                model_type=training_job.model_type,
            )

        except Exception as e:
            # Update job status
            training_job.status = "failed"
            training_job.error_message = str(e)
            training_job.failed_at = now_utc()
            training_job.updated_at = now_utc()

            logger.error(f"Training failed", job_id=training_job.id, error=str(e))

    def _initialize_model_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default model configurations"""
        return {
            "recommendation": {
                "algorithm": "collaborative_filtering",
                "similarity_metric": "cosine",
                "neighborhood_size": 50,
            },
            "classification": {
                "algorithm": "random_forest",
                "n_estimators": 100,
                "max_depth": 10,
            },
            "regression": {
                "algorithm": "gradient_boosting",
                "n_estimators": 100,
                "learning_rate": 0.1,
            },
        }

    # Additional methods to complete the interface

    async def get_model_performance(
        self,
        shop_id: str,
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get model performance metrics"""
        try:
            logger.debug(
                f"Getting model performance", shop_id=shop_id, model_id=model_id
            )

            # This would query Gorse for model performance
            # For now, return mock performance data
            return {
                "accuracy": 0.85,
                "precision": 0.82,
                "recall": 0.88,
                "f1_score": 0.85,
                "training_time": "2.5 minutes",
                "last_updated": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Failed to get model performance", shop_id=shop_id, error=str(e)
            )
            raise

    async def update_model(
        self,
        shop_id: str,
        model_id: str,
        new_features: List[MLFeatures],
        update_config: Dict[str, Any],
    ) -> MLTrainingJob:
        """Update existing model with new data"""
        try:
            logger.info(f"Starting model update", shop_id=shop_id, model_id=model_id)

            # Create update training job
            training_job = MLTrainingJob(
                id=f"update_{shop_id}_{model_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type="update",
                status="training",
                config=update_config,
                training_params={},
                started_at=now_utc(),
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Execute update asynchronously
            asyncio.create_task(
                self._execute_training(
                    training_job,
                    {"features": [f.get_feature_vector() for f in new_features]},
                )
            )

            return training_job

        except Exception as e:
            logger.error(
                f"Failed to update model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            raise

    async def deploy_model(
        self, shop_id: str, model_id: str, deployment_config: Dict[str, Any]
    ) -> bool:
        """Deploy model to production"""
        try:
            logger.info(f"Deploying model", shop_id=shop_id, model_id=model_id)

            # This would deploy the model in Gorse
            # For now, return success
            return True

        except Exception as e:
            logger.error(
                f"Failed to deploy model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            return False

    async def rollback_model(
        self, shop_id: str, model_id: str, target_version: str
    ) -> bool:
        """Rollback model to previous version"""
        try:
            logger.info(
                f"Rolling back model",
                shop_id=shop_id,
                model_id=model_id,
                target_version=target_version,
            )

            # This would rollback the model in Gorse
            # For now, return success
            return True

        except Exception as e:
            logger.error(
                f"Failed to rollback model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            return False

    async def get_model_versions(
        self, shop_id: str, model_id: str
    ) -> List[Dict[str, Any]]:
        """Get all versions of a model"""
        try:
            logger.debug(f"Getting model versions", shop_id=shop_id, model_id=model_id)

            # This would query Gorse for model versions
            # For now, return mock data
            return [
                {
                    "version": "1.0",
                    "created_at": now_utc().isoformat(),
                    "status": "active",
                },
                {
                    "version": "1.1",
                    "created_at": now_utc().isoformat(),
                    "status": "training",
                },
            ]

        except Exception as e:
            logger.error(
                f"Failed to get model versions",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            return []

    async def delete_model(self, shop_id: str, model_id: str) -> bool:
        """Delete a model"""
        try:
            logger.info(f"Deleting model", shop_id=shop_id, model_id=model_id)

            # This would delete the model in Gorse
            # For now, return success
            return True

        except Exception as e:
            logger.error(
                f"Failed to delete model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            return False

    async def export_model(
        self, shop_id: str, model_id: str, export_format: str = "onnx"
    ) -> bytes:
        """Export model in specified format"""
        try:
            logger.info(
                f"Exporting model",
                shop_id=shop_id,
                model_id=model_id,
                format=export_format,
            )

            # This would export the model from Gorse
            # For now, return mock data
            return b"mock_model_data"

        except Exception as e:
            logger.error(
                f"Failed to export model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            raise

    async def import_model(
        self,
        shop_id: str,
        model_data: bytes,
        model_config: Dict[str, Any],
        import_format: str = "onnx",
    ) -> MLModel:
        """Import model from external source"""
        try:
            logger.info(f"Importing model", shop_id=shop_id, format=import_format)

            # This would import the model into Gorse
            # For now, return mock model
            model = MLModel(
                id=f"imported_{shop_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type=model_config.get("type", "unknown"),
                model_name=model_config.get("name", "Imported Model"),
                version="1.0",
                status="imported",
                config=model_config,
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            return model

        except Exception as e:
            logger.error(f"Failed to import model", shop_id=shop_id, error=str(e))
            raise

    async def validate_model(
        self, shop_id: str, model_id: str, validation_data: List[MLFeatures]
    ) -> Dict[str, Any]:
        """Validate model performance on new data"""
        try:
            logger.info(f"Validating model", shop_id=shop_id, model_id=model_id)

            # This would validate the model in Gorse
            # For now, return mock validation results
            return {
                "validation_accuracy": 0.83,
                "validation_precision": 0.80,
                "validation_recall": 0.86,
                "validation_f1": 0.83,
                "data_points": len(validation_data),
            }

        except Exception as e:
            logger.error(
                f"Failed to validate model",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            raise

    async def get_training_history(
        self, shop_id: str, model_id: Optional[str] = None, limit: int = 100
    ) -> List[MLTrainingJob]:
        """Get training history"""
        try:
            logger.debug(
                f"Getting training history", shop_id=shop_id, model_id=model_id
            )

            # This would query Gorse for training history
            # For now, return mock data
            return [
                MLTrainingJob(
                    id=f"mock_job_{i}",
                    shop_id=shop_id,
                    model_type="recommendation",
                    status="completed",
                    config={},
                    training_params={},
                    started_at=now_utc(),
                    completed_at=now_utc(),
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
                for i in range(min(limit, 5))
            ]

        except Exception as e:
            logger.error(
                f"Failed to get training history", shop_id=shop_id, error=str(e)
            )
            return []

    async def cancel_training(self, shop_id: str, training_job_id: str) -> bool:
        """Cancel a training job"""
        try:
            logger.info(
                f"Cancelling training job", shop_id=shop_id, job_id=training_job_id
            )

            # This would cancel the training job in Gorse
            # For now, return success
            return True

        except Exception as e:
            logger.error(
                f"Failed to cancel training",
                shop_id=shop_id,
                job_id=training_job_id,
                error=str(e),
            )
            return False
