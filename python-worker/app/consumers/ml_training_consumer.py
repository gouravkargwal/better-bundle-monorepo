"""
ML training consumer for processing machine learning training jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import ML_TRAINING_STREAM, ML_TRAINING_GROUP
from app.domains.ml.services import MLPipelineService
from app.core.logging import get_logger


class MLTrainingConsumer(BaseConsumer):
    """Consumer for processing ML training jobs"""
    
    def __init__(self, ml_pipeline_service: MLPipelineService):
        super().__init__(
            stream_name=ML_TRAINING_STREAM,
            consumer_group=ML_TRAINING_GROUP,
            consumer_name="ml-training-consumer",
            batch_size=3,  # Process fewer ML jobs at once (they're resource-intensive)
            poll_timeout=3000,  # 3 second timeout
            max_retries=2,
            retry_delay=5.0,  # Longer delay for ML jobs
            circuit_breaker_failures=2,  # More sensitive for ML training
            circuit_breaker_timeout=300,  # 5 minute recovery
        )
        
        self.ml_pipeline_service = ml_pipeline_service
        self.logger = get_logger(__name__)
        
        # Training job tracking
        self.active_training_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 3600  # 1 hour for ML training
    
    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single ML training job message"""
        try:
            # Extract message data - Redis streams return data directly
            message_data = message  # No need to get "data" field
            job_id = message_data.get("job_id")
            shop_id = message_data.get("shop_id")
            shop_domain = message_data.get("shop_domain")
            training_type = message_data.get("training_type", "end_to_end")
            model_config = message_data.get("model_config", {})
            
            if not all([job_id, shop_id, shop_domain]):
                raise ValueError("Missing required job fields: job_id, shop_id, shop_domain")
            
            self.logger.info(
                f"Processing ML training job",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                training_type=training_type
            )
            
            # Track active training job
            self.active_training_jobs[job_id] = {
                "started_at": datetime.utcnow(),
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "training_type": training_type,
                "status": "processing",
                "model_config": model_config
            }
            
            # Process based on training type
            if training_type == "end_to_end":
                await self._process_end_to_end_training(
                    job_id, shop_id, shop_domain, model_config
                )
            elif training_type == "feature_engineering":
                await self._process_feature_engineering_training(
                    job_id, shop_id, shop_domain, model_config
                )
            elif training_type == "model_training":
                await self._process_model_training(
                    job_id, shop_id, shop_domain, model_config
                )
            elif training_type == "prediction":
                await self._process_prediction_training(
                    job_id, shop_id, shop_domain, model_config
                )
            else:
                self.logger.warning(f"Unknown training type: {training_type}")
                await self._mark_training_failed(job_id, f"Unknown training type: {training_type}")
            
            # Mark job as completed
            await self._mark_training_completed(job_id)
            
        except Exception as e:
            self.logger.error(
                f"Failed to process ML training job",
                job_id=message.get("job_id"),  # Redis streams return data directly
                error=str(e)
            )
            raise
    
    async def _process_end_to_end_training(
        self, 
        job_id: str, 
        shop_id: str, 
        shop_domain: str, 
        model_config: Dict[str, Any]
    ):
        """Process end-to-end ML pipeline training"""
        try:
            self.logger.info(f"Starting end-to-end ML training", job_id=job_id)
            
            # Run the complete ML pipeline
            result = await self.ml_pipeline_service.run_end_to_end_pipeline(
                shop_id=shop_id,
                shop_domain=shop_domain,
                pipeline_config=model_config
            )
            
            self.logger.info(
                f"End-to-end ML training completed",
                job_id=job_id,
                shop_id=shop_id,
                result=result
            )
            
            # Update job tracking
            if job_id in self.active_training_jobs:
                self.active_training_jobs[job_id]["status"] = "completed"
                self.active_training_jobs[job_id]["result"] = result
                self.active_training_jobs[job_id]["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(
                f"End-to-end ML training failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e)
            )
            await self._mark_training_failed(job_id, str(e))
            raise
    
    async def _process_feature_engineering_training(
        self, 
        job_id: str, 
        shop_id: str, 
        shop_domain: str, 
        model_config: Dict[str, Any]
    ):
        """Process feature engineering pipeline"""
        try:
            self.logger.info(f"Starting feature engineering pipeline", job_id=job_id)
            
            # Run feature engineering pipeline
            result = await self.ml_pipeline_service.run_feature_engineering_pipeline(
                shop_id=shop_id,
                shop_data=model_config.get("shop_data", {}),
                pipeline_config=model_config
            )
            
            self.logger.info(
                f"Feature engineering pipeline completed",
                job_id=job_id,
                shop_id=shop_id,
                features_count=len(result)
            )
            
            # Update job tracking
            if job_id in self.active_training_jobs:
                self.active_training_jobs[job_id]["status"] = "completed"
                self.active_training_jobs[job_id]["result"] = result
                self.active_training_jobs[job_id]["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(
                f"Feature engineering pipeline failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e)
            )
            await self._mark_training_failed(job_id, str(e))
            raise
    
    async def _process_model_training(
        self, 
        job_id: str, 
        shop_id: str, 
        shop_domain: str, 
        model_config: Dict[str, Any]
    ):
        """Process model training pipeline"""
        try:
            self.logger.info(f"Starting model training pipeline", job_id=job_id)
            
            # Run model training pipeline
            result = await self.ml_pipeline_service.run_ml_training_pipeline(
                shop_id=shop_id,
                shop_domain=shop_domain,
                pipeline_config=model_config
            )
            
            self.logger.info(
                f"Model training pipeline completed",
                job_id=job_id,
                shop_id=shop_id,
                result=result
            )
            
            # Update job tracking
            if job_id in self.active_training_jobs:
                self.active_training_jobs[job_id]["status"] = "completed"
                self.active_training_jobs[job_id]["result"] = result
                self.active_training_jobs[job_id]["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(
                f"Model training pipeline failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e)
            )
            await self._mark_training_failed(job_id, str(e))
            raise
    
    async def _process_prediction_training(
        self, 
        job_id: str, 
        shop_id: str, 
        shop_domain: str, 
        model_config: Dict[str, Any]
    ):
        """Process prediction pipeline"""
        try:
            self.logger.info(f"Starting prediction pipeline", job_id=job_id)
            
            # Note: This would need to be implemented in the MLPipelineService
            # For now, we'll log that it's not implemented
            self.logger.warning(f"Prediction pipeline not implemented yet", job_id=job_id)
            
            # For now, mark as completed with warning
            if job_id in self.active_training_jobs:
                self.active_training_jobs[job_id]["status"] = "completed"
                self.active_training_jobs[job_id]["result"] = {"message": "Not implemented yet"}
                self.active_training_jobs[job_id]["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(
                f"Prediction pipeline failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e)
            )
            await self._mark_training_failed(job_id, str(e))
            raise
    
    async def _mark_training_completed(self, job_id: str):
        """Mark training job as completed"""
        if job_id in self.active_training_jobs:
            self.active_training_jobs[job_id]["status"] = "completed"
            self.active_training_jobs[job_id]["completed_at"] = datetime.utcnow()
        
        self.logger.info(f"ML training job completed successfully", job_id=job_id)
    
    async def _mark_training_failed(self, job_id: str, error_message: str):
        """Mark training job as failed"""
        if job_id in self.active_training_jobs:
            self.active_training_jobs[job_id]["status"] = "failed"
            self.active_training_jobs[job_id]["error"] = error_message
            self.active_training_jobs[job_id]["failed_at"] = datetime.utcnow()
        
        self.logger.error(f"ML training job failed", job_id=job_id, error=error_message)
    
    async def cleanup_old_jobs(self):
        """Clean up old completed/failed training jobs"""
        now = datetime.utcnow()
        jobs_to_remove = []
        
        for job_id, job_data in self.active_training_jobs.items():
            if job_data["status"] in ["completed", "failed"]:
                # Check if job is old enough to remove
                if "completed_at" in job_data:
                    age = (now - job_data["completed_at"]).total_seconds()
                elif "failed_at" in job_data:
                    age = (now - job_data["failed_at"]).total_seconds()
                else:
                    continue
                
                if age > self.job_timeout:
                    jobs_to_remove.append(job_id)
        
        # Remove old jobs
        for job_id in jobs_to_remove:
            del self.active_training_jobs[job_id]
        
        if jobs_to_remove:
            self.logger.info(f"Cleaned up {len(jobs_to_remove)} old ML training jobs")
    
    def get_training_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific training job"""
        return self.active_training_jobs.get(job_id)
    
    def get_all_training_jobs_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all active training jobs"""
        return self.active_training_jobs.copy()
    
    async def _health_check(self):
        """Extended health check for ML training consumer"""
        await super()._health_check()
        
        # Clean up old jobs periodically
        await self.cleanup_old_jobs()
        
        # Log training job statistics
        active_count = len([j for j in self.active_training_jobs.values() if j["status"] == "processing"])
        completed_count = len([j for j in self.active_training_jobs.values() if j["status"] == "completed"])
        failed_count = len([j for j in self.active_training_jobs.values() if j["status"] == "failed"])
        
        self.logger.info(
            f"ML training consumer job status",
            active_jobs=active_count,
            completed_jobs=completed_count,
            failed_jobs=failed_count,
            total_jobs=len(self.active_training_jobs)
        )
