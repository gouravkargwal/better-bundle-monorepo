"""
ML pipeline service implementation for BetterBundle Python Worker
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid

from app.core.logging import get_logger
from app.shared.decorators import async_timing
from app.shared.helpers import now_utc

from ..interfaces.ml_pipeline import IMLPipelineService
from ..interfaces.feature_engineering import IFeatureEngineeringService
from ..interfaces.gorse_ml import IGorseMLService
from ..models import MLFeatures, MLModel, MLTrainingJob, MLPrediction


class MLPipelineService(IMLPipelineService):
    """ML pipeline service for orchestrating end-to-end ML workflows"""

    def __init__(
        self,
        feature_service: IFeatureEngineeringService,
        gorse_service: IGorseMLService,
    ):
        self.feature_service = feature_service
        self.gorse_service = gorse_service
        self.logger = get_logger(__name__)

        # Active pipelines
        self.active_pipelines: Dict[str, Dict[str, Any]] = {}

    async def run_feature_engineering_pipeline(
        self, shop_id: str, shop_data: Dict[str, Any], pipeline_config: Dict[str, Any]
    ) -> Dict[str, List[MLFeatures]]:
        """Run complete feature engineering pipeline"""
        try:
            self.logger.info(f"Starting feature engineering pipeline", shop_id=shop_id)

            # Extract data from shop_data
            products = shop_data.get("products", [])
            customers = shop_data.get("customers", [])
            orders = shop_data.get("orders", [])
            collections = shop_data.get("collections", [])
            events = shop_data.get("events", [])
            shop = shop_data.get("shop")

            if not shop:
                raise ValueError("Shop data is required")

            # Compute features for each entity type
            features = {}

            # Product features
            if products:
                product_features = []
                for product in products:
                    product_feat = await self.feature_service.compute_product_features(
                        product, shop, orders, collections
                    )
                    ml_features = await self.feature_service.create_ml_features(
                        shop_id, "product", product.id, product_feat, ["shopify_api"]
                    )
                    product_features.append(ml_features)
                features["products"] = product_features

            # Customer features
            if customers:
                customer_features = []
                for customer in customers:
                    customer_feat = (
                        await self.feature_service.compute_customer_features(
                            customer, shop, orders, events
                        )
                    )
                    ml_features = await self.feature_service.create_ml_features(
                        shop_id, "customer", customer.id, customer_feat, ["shopify_api"]
                    )
                    customer_features.append(ml_features)
                features["customers"] = customer_features

            # Order features
            if orders:
                order_features = []
                for order in orders:
                    order_feat = await self.feature_service.compute_order_features(
                        order, shop, products
                    )
                    ml_features = await self.feature_service.create_ml_features(
                        shop_id, "order", order.id, order_feat, ["shopify_api"]
                    )
                    order_features.append(ml_features)
                features["orders"] = order_features

            # Collection features
            if collections:
                collection_features = []
                for collection in collections:
                    collection_feat = (
                        await self.feature_service.compute_collection_features(
                            collection, shop, products
                        )
                    )
                    ml_features = await self.feature_service.create_ml_features(
                        shop_id,
                        "collection",
                        collection.id,
                        collection_feat,
                        ["shopify_api"],
                    )
                    collection_features.append(ml_features)
                features["collections"] = collection_features

            # Shop features
            shop_feat = await self.feature_service.compute_shop_features(
                shop, products, orders, customers, collections, events
            )
            shop_ml_features = await self.feature_service.create_ml_features(
                shop_id, "shop", shop.id, shop_feat, ["shopify_api"]
            )
            features["shop"] = [shop_ml_features]

            # Cross-entity features
            if all([products, orders, customers, collections, events]):
                cross_entity_feat = (
                    await self.feature_service.compute_cross_entity_features(
                        shop, products, orders, customers, collections, events
                    )
                )
                cross_entity_ml_features = (
                    await self.feature_service.create_ml_features(
                        shop_id,
                        "cross_entity",
                        "cross_entity",
                        cross_entity_feat,
                        ["shopify_api"],
                    )
                )
                features["cross_entity"] = [cross_entity_ml_features]

            self.logger.info(
                f"Feature engineering pipeline completed",
                shop_id=shop_id,
                feature_counts={k: len(v) for k, v in features.items()},
            )

            return features

        except Exception as e:
            self.logger.error(
                f"Feature engineering pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_ml_training_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        training_config: Dict[str, Any],
    ) -> Dict[str, MLTrainingJob]:
        """Run complete ML training pipeline"""
        try:
            self.logger.info(f"Starting ML training pipeline", shop_id=shop_id)

            training_jobs = {}

            # Train recommendation model
            if "products" in features and "customers" in features:
                rec_config = training_config.get("recommendation", {})
                rec_job = await self.gorse_service.train_recommendation_model(
                    shop_id, features["products"], rec_config
                )
                training_jobs["recommendation"] = rec_job

            # Train customer segmentation model
            if "customers" in features:
                seg_config = training_config.get("customer_segmentation", {})
                customer_labels = self._create_customer_labels(features["customers"])
                seg_job = await self.gorse_service.train_classification_model(
                    shop_id, features["customers"], customer_labels, seg_config
                )
                training_jobs["customer_segmentation"] = seg_job

            # Train product performance model
            if "products" in features and "orders" in features:
                perf_config = training_config.get("product_performance", {})
                product_targets = self._create_product_targets(features["products"])
                perf_job = await self.gorse_service.train_regression_model(
                    shop_id, features["products"], product_targets, perf_config
                )
                training_jobs["product_performance"] = perf_job

            self.logger.info(
                f"ML training pipeline completed",
                shop_id=shop_id,
                jobs_count=len(training_jobs),
            )

            return training_jobs

        except Exception as e:
            self.logger.error(
                f"ML training pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_end_to_end_pipeline(
        self, shop_id: str, shop_data: Dict[str, Any], pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run complete end-to-end ML pipeline"""
        try:
            pipeline_id = str(uuid.uuid4())
            self.logger.info(
                f"Starting end-to-end ML pipeline",
                shop_id=shop_id,
                pipeline_id=pipeline_id,
            )

            # Track pipeline status
            self.active_pipelines[pipeline_id] = {
                "shop_id": shop_id,
                "status": "running",
                "started_at": now_utc(),
                "stages": {},
            }

            results = {}

            # Stage 1: Feature Engineering
            try:
                self.active_pipelines[pipeline_id]["stages"][
                    "feature_engineering"
                ] = "running"
                features = await self.run_feature_engineering_pipeline(
                    shop_id, shop_data, pipeline_config
                )
                results["features"] = features
                self.active_pipelines[pipeline_id]["stages"][
                    "feature_engineering"
                ] = "completed"
            except Exception as e:
                self.active_pipelines[pipeline_id]["stages"][
                    "feature_engineering"
                ] = "failed"
                raise

            # Stage 2: ML Training (if enabled)
            if pipeline_config.get("include_training", True):
                try:
                    self.active_pipelines[pipeline_id]["stages"]["training"] = "running"
                    training_config = pipeline_config.get("training", {})
                    training_jobs = await self.run_ml_training_pipeline(
                        shop_id, features, training_config
                    )
                    results["training"] = training_jobs
                    self.active_pipelines[pipeline_id]["stages"][
                        "training"
                    ] = "completed"
                except Exception as e:
                    self.active_pipelines[pipeline_id]["stages"]["training"] = "failed"
                    raise

            # Stage 3: Predictions (if enabled)
            if pipeline_config.get("include_predictions", True):
                try:
                    self.active_pipelines[pipeline_id]["stages"][
                        "predictions"
                    ] = "running"
                    predictions = {}

                    # Sample predictions for each entity type
                    for entity_type, entity_features in features.items():
                        if entity_features:
                            sample_features = entity_features[
                                0
                            ]  # Use first entity as sample
                            pred_config = pipeline_config.get("prediction", {})
                            entity_predictions = await self.run_prediction_pipeline(
                                shop_id, sample_features, pred_config
                            )
                            predictions[entity_type] = entity_predictions

                    results["predictions"] = predictions
                    self.active_pipelines[pipeline_id]["stages"][
                        "predictions"
                    ] = "completed"
                except Exception as e:
                    self.active_pipelines[pipeline_id]["stages"][
                        "predictions"
                    ] = "failed"
                    raise

            # Update pipeline status
            self.active_pipelines[pipeline_id]["status"] = "completed"
            self.active_pipelines[pipeline_id]["completed_at"] = now_utc()

            self.logger.info(
                f"End-to-end ML pipeline completed",
                shop_id=shop_id,
                pipeline_id=pipeline_id,
            )

            return results

        except Exception as e:
            if pipeline_id in self.active_pipelines:
                self.active_pipelines[pipeline_id]["status"] = "failed"
                self.active_pipelines[pipeline_id]["error"] = str(e)
                self.active_pipelines[pipeline_id]["failed_at"] = now_utc()

            self.logger.error(
                f"End-to-end ML pipeline failed",
                shop_id=shop_id,
                pipeline_id=pipeline_id,
                error=str(e),
            )
            raise

    async def get_pipeline_status(
        self, shop_id: str, pipeline_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get pipeline execution status"""
        if pipeline_id:
            return self.active_pipelines.get(pipeline_id, {})

        shop_pipelines = {
            pid: pipeline
            for pid, pipeline in self.active_pipelines.items()
            if pipeline["shop_id"] == shop_id
        }
        return shop_pipelines

    async def run_prediction_pipeline(
        self, shop_id: str, features: MLFeatures, prediction_config: Dict[str, Any]
    ) -> Dict[str, MLPrediction]:
        """Run complete prediction pipeline"""
        try:
            self.logger.info(
                f"Starting prediction pipeline",
                shop_id=shop_id,
                entity_id=features.entity_id,
            )

            predictions = {}

            # Customer segmentation prediction
            if features.feature_type == "customer":
                seg_pred = await self.gorse_service.predict_customer_segment(
                    shop_id, features
                )
                predictions["customer_segment"] = seg_pred

            # Product performance prediction
            elif features.feature_type == "product":
                perf_pred = await self.gorse_service.predict_product_performance(
                    shop_id, features
                )
                predictions["product_performance"] = perf_pred

            # Get recommendations
            if features.feature_type in ["customer", "product"]:
                recs = await self.gorse_service.get_recommendations(
                    shop_id,
                    user_id=(
                        features.entity_id
                        if features.feature_type == "customer"
                        else None
                    ),
                    item_id=(
                        features.entity_id
                        if features.feature_type == "product"
                        else None
                    ),
                    limit=prediction_config.get("recommendation_limit", 10),
                )
                predictions["recommendations"] = recs

            return predictions

        except Exception as e:
            self.logger.error(
                f"Prediction pipeline failed",
                shop_id=shop_id,
                entity_id=features.entity_id,
                error=str(e),
            )
            raise

    async def run_incremental_update_pipeline(
        self,
        shop_id: str,
        new_data: Dict[str, Any],
        existing_features: Dict[str, List[MLFeatures]],
        update_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run incremental update pipeline"""
        try:
            self.logger.info(f"Starting incremental update pipeline", shop_id=shop_id)

            # Compute features for new data
            new_features = await self.run_feature_engineering_pipeline(
                shop_id, new_data, update_config
            )

            # Merge with existing features
            updated_features = {}
            for entity_type in new_features:
                if entity_type in existing_features:
                    updated_features[entity_type] = (
                        existing_features[entity_type] + new_features[entity_type]
                    )
                else:
                    updated_features[entity_type] = new_features[entity_type]

            # Update models if requested
            model_updates = {}
            if update_config.get("update_models", True):
                model_updates = await self.run_ml_training_pipeline(
                    shop_id, updated_features, update_config.get("training", {})
                )

            return {
                "updated_features": updated_features,
                "model_updates": model_updates,
            }

        except Exception as e:
            self.logger.error(
                f"Incremental update pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_model_evaluation_pipeline(
        self, shop_id: str, model_ids: List[str], evaluation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run model evaluation pipeline"""
        try:
            self.logger.info(
                f"Starting model evaluation pipeline",
                shop_id=shop_id,
                model_count=len(model_ids),
            )

            evaluation_results = {}

            for model_id in model_ids:
                try:
                    # Get model performance
                    performance = await self.gorse_service.get_model_performance(
                        shop_id, model_id
                    )

                    # Validate model on test data
                    validation_data = evaluation_config.get("validation_data", [])
                    if validation_data:
                        validation_results = await self.gorse_service.validate_model(
                            shop_id, model_id, validation_data
                        )
                        performance["validation"] = validation_results

                    evaluation_results[model_id] = performance

                except Exception as e:
                    evaluation_results[model_id] = {"error": str(e)}

            return evaluation_results

        except Exception as e:
            self.logger.error(
                f"Model evaluation pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_model_deployment_pipeline(
        self, shop_id: str, model_id: str, deployment_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run model deployment pipeline"""
        try:
            self.logger.info(
                f"Starting model deployment pipeline",
                shop_id=shop_id,
                model_id=model_id,
            )

            # Deploy model
            deployment_success = await self.gorse_service.deploy_model(
                shop_id, model_id, deployment_config
            )

            if deployment_success:
                deployment_results = {
                    "status": "deployed",
                    "deployed_at": now_utc(),
                    "deployment_config": deployment_config,
                }
            else:
                deployment_results = {"status": "failed", "error": "Deployment failed"}

            return deployment_results

        except Exception as e:
            self.logger.error(
                f"Model deployment pipeline failed",
                shop_id=shop_id,
                model_id=model_id,
                error=str(e),
            )
            raise

    async def run_ab_testing_pipeline(
        self,
        shop_id: str,
        model_a_id: str,
        model_b_id: str,
        ab_test_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run A/B testing pipeline"""
        try:
            self.logger.info(
                f"Starting A/B testing pipeline",
                shop_id=shop_id,
                model_a=model_a_id,
                model_b=model_b_id,
            )

            # Get performance metrics for both models
            model_a_performance = await self.gorse_service.get_model_performance(
                shop_id, model_a_id
            )
            model_b_performance = await self.gorse_service.get_model_performance(
                shop_id, model_b_id
            )

            # Compare performance
            comparison = self._compare_model_performance(
                model_a_performance, model_b_performance
            )

            # Determine winner
            winner = (
                "model_a"
                if comparison["model_a_score"] > comparison["model_b_score"]
                else "model_b"
            )

            ab_test_results = {
                "model_a": {
                    "id": model_a_id,
                    "performance": model_a_performance,
                    "score": comparison["model_a_score"],
                },
                "model_b": {
                    "id": model_b_id,
                    "performance": model_b_performance,
                    "score": comparison["model_b_score"],
                },
                "comparison": comparison,
                "winner": winner,
                "recommendation": f"Deploy {winner}",
            }

            return ab_test_results

        except Exception as e:
            self.logger.error(
                f"A/B testing pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_model_monitoring_pipeline(
        self, shop_id: str, model_ids: List[str], monitoring_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run model monitoring pipeline"""
        try:
            self.logger.info(
                f"Starting model monitoring pipeline",
                shop_id=shop_id,
                model_count=len(model_ids),
            )

            monitoring_results = {}
            alerts = []

            for model_id in model_ids:
                try:
                    # Get current performance
                    performance = await self.gorse_service.get_model_performance(
                        shop_id, model_id
                    )

                    # Check for performance degradation
                    degradation_threshold = monitoring_config.get(
                        "degradation_threshold", 0.1
                    )
                    if performance.get("accuracy", 1.0) < degradation_threshold:
                        alert = {
                            "type": "performance_degradation",
                            "model_id": model_id,
                            "severity": "high",
                            "message": f"Model {model_id} performance below threshold",
                            "current_accuracy": performance.get("accuracy", 0.0),
                            "threshold": degradation_threshold,
                        }
                        alerts.append(alert)

                    monitoring_results[model_id] = {
                        "performance": performance,
                        "status": "healthy" if not alerts else "degraded",
                    }

                except Exception as e:
                    alert = {
                        "type": "monitoring_error",
                        "model_id": model_id,
                        "severity": "medium",
                        "message": f"Failed to monitor model {model_id}",
                        "error": str(e),
                    }
                    alerts.append(alert)

            return {
                "monitoring_results": monitoring_results,
                "alerts": alerts,
                "alert_count": len(alerts),
            }

        except Exception as e:
            self.logger.error(
                f"Model monitoring pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_data_quality_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        quality_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run data quality assessment pipeline"""
        try:
            self.logger.info(f"Starting data quality pipeline", shop_id=shop_id)

            quality_results = {}
            recommendations = []

            for entity_type, entity_features in features.items():
                if not entity_features:
                    continue

                # Validate features
                validation_results = []
                for feature in entity_features:
                    validation = await self.feature_service.validate_features(
                        feature.get_features_dict(), entity_type
                    )
                    validation_results.append(validation)

                # Calculate quality metrics
                avg_quality = sum(r["quality_score"] for r in validation_results) / len(
                    validation_results
                )
                missing_features_count = sum(
                    len(r["missing_features"]) for r in validation_results
                )

                quality_results[entity_type] = {
                    "feature_count": len(entity_features),
                    "average_quality_score": avg_quality,
                    "missing_features_count": missing_features_count,
                    "validation_results": validation_results,
                }

                # Generate recommendations
                if avg_quality < quality_config.get("quality_threshold", 0.7):
                    recommendations.append(
                        {
                            "entity_type": entity_type,
                            "issue": "Low feature quality",
                            "recommendation": "Review data collection and feature engineering",
                        }
                    )

                if missing_features_count > 0:
                    recommendations.append(
                        {
                            "entity_type": entity_type,
                            "issue": "Missing features",
                            "recommendation": "Check data sources and feature computation",
                        }
                    )

            return {
                "quality_results": quality_results,
                "recommendations": recommendations,
                "overall_quality_score": sum(
                    r["average_quality_score"] for r in quality_results.values()
                )
                / len(quality_results),
            }

        except Exception as e:
            self.logger.error(
                f"Data quality pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_feature_selection_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        selection_config: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """Run feature selection pipeline"""
        try:
            self.logger.info(f"Starting feature selection pipeline", shop_id=shop_id)

            selected_features = {}

            for entity_type, entity_features in features.items():
                if not entity_features:
                    continue

                # Get feature importance scores
                feature_importance = {}
                for feature in entity_features:
                    importance = await self.feature_service.get_feature_importance(
                        feature.get_features_dict(), entity_type
                    )
                    feature_importance.update(importance)

                # Select top features
                importance_threshold = selection_config.get("importance_threshold", 0.5)
                top_features = [
                    feature_name
                    for feature_name, score in feature_importance.items()
                    if score >= importance_threshold
                ]

                selected_features[entity_type] = top_features

            return selected_features

        except Exception as e:
            self.logger.error(
                f"Feature selection pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def run_hyperparameter_optimization_pipeline(
        self,
        shop_id: str,
        features: Dict[str, List[MLFeatures]],
        optimization_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run hyperparameter optimization pipeline"""
        try:
            self.logger.info(
                f"Starting hyperparameter optimization pipeline", shop_id=shop_id
            )

            # This would integrate with Gorse's hyperparameter optimization
            # For now, return default optimized parameters
            optimized_params = {
                "recommendation": {
                    "algorithm": "collaborative_filtering",
                    "similarity_metric": "cosine",
                    "neighborhood_size": 75,
                },
                "classification": {
                    "algorithm": "random_forest",
                    "n_estimators": 150,
                    "max_depth": 15,
                },
                "regression": {
                    "algorithm": "gradient_boosting",
                    "n_estimators": 150,
                    "learning_rate": 0.05,
                },
            }

            return optimized_params

        except Exception as e:
            self.logger.error(
                f"Hyperparameter optimization pipeline failed",
                shop_id=shop_id,
                error=str(e),
            )
            raise

    async def run_model_ensemble_pipeline(
        self, shop_id: str, model_ids: List[str], ensemble_config: Dict[str, Any]
    ) -> MLModel:
        """Run model ensemble pipeline"""
        try:
            self.logger.info(
                f"Starting model ensemble pipeline",
                shop_id=shop_id,
                model_count=len(model_ids),
            )

            # This would create an ensemble model combining multiple models
            # For now, return a placeholder ensemble model
            ensemble_model = MLModel(
                id=f"ensemble_{shop_id}_{now_utc().timestamp()}",
                shop_id=shop_id,
                model_type="ensemble",
                model_name="Ensemble Model",
                version="1.0",
                status="trained",
                config=ensemble_config,
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            return ensemble_model

        except Exception as e:
            self.logger.error(
                f"Model ensemble pipeline failed", shop_id=shop_id, error=str(e)
            )
            raise

    async def cancel_pipeline(self, shop_id: str, pipeline_id: str) -> bool:
        """Cancel a running pipeline"""
        try:
            if pipeline_id in self.active_pipelines:
                pipeline = self.active_pipelines[pipeline_id]
                if pipeline["shop_id"] == shop_id and pipeline["status"] == "running":
                    pipeline["status"] = "cancelled"
                    pipeline["cancelled_at"] = now_utc()
                    return True
            return False
        except Exception as e:
            self.logger.error(
                f"Failed to cancel pipeline", pipeline_id=pipeline_id, error=str(e)
            )
            return False

    async def get_pipeline_history(
        self, shop_id: str, pipeline_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pipeline execution history"""
        shop_pipelines = [
            pipeline
            for pipeline in self.active_pipelines.values()
            if pipeline["shop_id"] == shop_id
        ]

        if pipeline_type:
            shop_pipelines = [
                p for p in shop_pipelines if pipeline_type in p.get("stages", {})
            ]

        # Sort by started_at and limit results
        sorted_pipelines = sorted(
            shop_pipelines, key=lambda x: x.get("started_at", now_utc()), reverse=True
        )

        return sorted_pipelines[:limit]

    async def validate_pipeline_config(
        self, pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate pipeline configuration"""
        validation_result = {"is_valid": True, "errors": [], "warnings": []}

        # Check required fields
        required_fields = ["include_training", "include_predictions"]
        for field in required_fields:
            if field not in pipeline_config:
                validation_result["errors"].append(f"Missing required field: {field}")
                validation_result["is_valid"] = False

        # Check field types
        if "include_training" in pipeline_config and not isinstance(
            pipeline_config["include_training"], bool
        ):
            validation_result["errors"].append("include_training must be boolean")
            validation_result["is_valid"] = False

        if "include_predictions" in pipeline_config and not isinstance(
            pipeline_config["include_predictions"], bool
        ):
            validation_result["errors"].append("include_predictions must be boolean")
            validation_result["is_valid"] = False

        return validation_result

    async def estimate_pipeline_runtime(
        self, shop_id: str, pipeline_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate pipeline runtime"""
        estimates = {
            "feature_engineering": "5-15 minutes",
            "training": "10-30 minutes",
            "predictions": "2-5 minutes",
            "total_estimated_time": "17-50 minutes",
        }

        if not pipeline_config.get("include_training", True):
            estimates["training"] = "skipped"
            estimates["total_estimated_time"] = "7-20 minutes"

        if not pipeline_config.get("include_predictions", True):
            estimates["predictions"] = "skipped"
            estimates["total_estimated_time"] = "15-45 minutes"

        return estimates

    # Helper methods
    def _create_customer_labels(self, customer_features: List[MLFeatures]) -> List[str]:
        """Create customer segmentation labels based on features"""
        labels = []
        for customer_feature in customer_features:
            total_spent = customer_feature.customer_features.get("total_spent", 0)
            if total_spent > 1000:
                labels.append("high_value")
            elif total_spent > 100:
                labels.append("medium_value")
            else:
                labels.append("low_value")
        return labels

    def _create_product_targets(
        self, product_features: List[MLFeatures]
    ) -> List[float]:
        """Create product performance targets based on features"""
        targets = []
        for product_feature in product_features:
            # Assuming product_feature.product_features contains relevant metrics
            # For example, if product_feature.product_features has 'revenue' and 'orders'
            # we can use 'revenue' as the target for regression.
            # This is a placeholder and needs actual data to be meaningful.
            # For now, we'll just return a dummy list.
            targets.append(product_feature.product_features.get("revenue", 0.0))
        return targets

    def _compare_model_performance(
        self, model_a_perf: Dict[str, Any], model_b_perf: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare performance of two models"""
        # Simple scoring based on accuracy and other metrics
        model_a_score = (
            model_a_perf.get("accuracy", 0.0) * 0.7
            + model_a_perf.get("precision", 0.0) * 0.3
        )
        model_b_score = (
            model_b_perf.get("accuracy", 0.0) * 0.7
            + model_b_perf.get("precision", 0.0) * 0.3
        )

        return {
            "model_a_score": model_a_score,
            "model_b_score": model_b_score,
            "difference": abs(model_a_score - model_b_score),
            "winner": "model_a" if model_a_score > model_b_score else "model_b",
        }
