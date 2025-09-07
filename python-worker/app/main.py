"""
Main application for BetterBundle Python Worker
"""

import asyncio
import time
import uvicorn
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from app.core.config.settings import settings
from app.core.logging import setup_logging, get_logger
from app.shared.helpers import now_utc

# Domain imports
from app.domains.shopify.services import (
    ShopifyDataCollectionService,
    ShopifyAPIClient,
    ShopifyPermissionService,
)
from app.domains.ml.services import (
    FeatureEngineeringService,
)
from app.domains.analytics.services import (
    BusinessMetricsService,
    PerformanceAnalyticsService,
    CustomerAnalyticsService,
    ProductAnalyticsService,
    RevenueAnalyticsService,
    HeuristicService,
)

# Consumer imports
from app.consumers.consumer_manager import consumer_manager
from app.consumers.data_collection_consumer import DataCollectionConsumer
from app.consumers.main_table_processing_consumer import MainTableProcessingConsumer
from app.consumers.analytics_consumer import AnalyticsConsumer
from app.consumers.feature_computation_consumer import FeatureComputationConsumer

# Webhook imports
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository
from app.consumers.behavioral_events_consumer import BehavioralEventsConsumer
from app.consumers.gorse_sync_consumer import GorseSyncConsumer
from app.consumers.gorse_training_consumer import GorseTrainingConsumer

# API imports
from app.api.v1.training import router as training_router

# Initialize logging (already configured in main.py)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting BetterBundle Python Worker...")

    # Initialize services
    await initialize_services()

    logger.info("BetterBundle Python Worker started successfully")

    yield

    # Shutdown
    logger.info("Shutting down BetterBundle Python Worker...")
    await cleanup_services()
    logger.info("BetterBundle Python Worker shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="BetterBundle Python Worker",
    description="AI-powered Shopify analytics and ML platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(training_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
services = {}


async def initialize_services():
    """Initialize only essential services at startup"""
    try:
        logger.info("Initializing essential services...")

        # Initialize only core Shopify services (lazy load others)
        services["shopify_api"] = ShopifyAPIClient()
        services["shopify_permissions"] = ShopifyPermissionService(
            api_client=services["shopify_api"]
        )
        services["shopify"] = ShopifyDataCollectionService(
            api_client=services["shopify_api"],
            permission_service=services["shopify_permissions"],
        )

        # Initialize only data collection consumer (most critical)
        services["data_collection_consumer"] = DataCollectionConsumer(
            shopify_service=services["shopify"]
        )

        # Initialize main table processing consumer
        services["main_table_processing_consumer"] = MainTableProcessingConsumer()

        # Initialize feature computation consumer
        services["feature_computation_consumer"] = FeatureComputationConsumer()

        # Initialize behavioral events consumer
        services["behavioral_events_consumer"] = BehavioralEventsConsumer()

        # Initialize gorse sync consumer
        services["gorse_sync_consumer"] = GorseSyncConsumer()

        # Initialize gorse training consumer
        services["gorse_training_consumer"] = GorseTrainingConsumer()

        # Initialize webhook services
        services["webhook_repository"] = WebhookRepository()
        services["webhook_handler"] = WebhookHandler(services["webhook_repository"])

        # Register and start consumers
        consumer_manager.register_consumers(
            data_collection_consumer=services["data_collection_consumer"],
            main_table_processing_consumer=services["main_table_processing_consumer"],
            feature_computation_consumer=services["feature_computation_consumer"],
            behavioral_events_consumer=services["behavioral_events_consumer"],
            gorse_sync_consumer=services["gorse_sync_consumer"],
            gorse_training_consumer=services["gorse_training_consumer"],
        )

        # Start consumer manager
        await consumer_manager.start()

        logger.info("Essential services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


async def get_service(service_name: str):
    """Lazy load services on demand"""
    if service_name not in services:
        logger.info(f"Lazy loading service: {service_name}")

        if service_name == "feature_engineering":
            logger.info("Using FeatureEngineeringService (refactored architecture)")
            services["feature_engineering"] = FeatureEngineeringService()
        elif service_name == "ml_pipeline":
            if "feature_engineering" not in services:
                await get_service("feature_engineering")
            if "gorse_ml" not in services:
                await get_service("gorse_ml")
        elif service_name == "business_metrics":
            services["business_metrics"] = BusinessMetricsService()
        elif service_name == "performance_analytics":
            services["performance_analytics"] = PerformanceAnalyticsService()
        elif service_name == "customer_analytics":
            services["customer_analytics"] = CustomerAnalyticsService()
        elif service_name == "product_analytics":
            services["product_analytics"] = ProductAnalyticsService()
        elif service_name == "revenue_analytics":
            services["revenue_analytics"] = RevenueAnalyticsService()
        elif service_name == "heuristic":
            services["heuristic"] = HeuristicService()
        elif service_name == "analytics_consumer":
            # Load all analytics services
            for analytics_service in [
                "business_metrics",
                "performance_analytics",
                "customer_analytics",
                "product_analytics",
                "revenue_analytics",
            ]:
                if analytics_service not in services:
                    await get_service(analytics_service)

            services["analytics_consumer"] = AnalyticsConsumer(
                business_metrics_service=services["business_metrics"],
                performance_analytics_service=services["performance_analytics"],
                customer_analytics_service=services["customer_analytics"],
                product_analytics_service=services["product_analytics"],
                revenue_analytics_service=services["revenue_analytics"],
            )
        elif service_name == "feature_computation_consumer":
            services["feature_computation_consumer"] = FeatureComputationConsumer()

    return services[service_name]


async def cleanup_services():
    """Cleanup all services"""
    try:

        # Stop consumer manager
        await consumer_manager.stop()

        # Stop Gorse training monitor
        if "gorse_training_monitor" in services:
            await services["gorse_training_monitor"].stop_monitoring()

        # Close Gorse ML service
        if "gorse_ml" in services:
            await services["gorse_ml"].close()

        # Shutdown database connection
        from app.core.database.simple_db_client import close_database

        await close_database()

        # Clear services dictionary
        services.clear()

    except Exception as e:
        logger.error(f"Failed to cleanup services: {e}")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": now_utc().isoformat(),
        "version": "1.0.0",
        "services": list(services.keys()),
    }


# Shopify data endpoints
@app.post("/api/shopify/collect-data")
async def collect_shopify_data(
    shop_id: str,
    background_tasks: BackgroundTasks,
    collection_config: Optional[Dict[str, Any]] = None,
):
    """Collect Shopify data for a shop"""
    try:
        if "shopify" not in services:
            raise HTTPException(status_code=500, detail="Shopify service not available")

        # Start data collection in background
        background_tasks.add_task(
            services["shopify"].collect_all_data_by_shop_id,
            shop_id,
            collection_config or {},
        )

        return {
            "message": "Data collection started",
            "shop_id": shop_id,
            "status": "processing",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to start data collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shopify/data-status/{shop_id}")
async def get_data_status(shop_id: str):
    """Get data collection status for a shop"""
    try:
        if "shopify" not in services:
            raise HTTPException(status_code=500, detail="Shopify service not available")

        status = await services["shopify"].get_collection_status(shop_id)
        return status

    except Exception as e:
        logger.error(f"Failed to get data status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Main table processing endpoints
@app.post("/api/main-table/process")
async def trigger_main_table_processing(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Trigger main table processing for a shop"""
    try:
        from app.core.redis_client import streams_manager
        from app.shared.helpers import now_utc

        # Extract parameters from request body (JSON) or form data
        try:
            body = await request.json()
        except:
            # Fallback to form data
            form_data = await request.form()
            body = dict(form_data)

        shop_id = body.get("shop_id")
        shop_domain = body.get("shop_domain", "")

        # Validate required parameters
        if not shop_id:
            raise HTTPException(status_code=400, detail="shop_id is required")

        # Generate a unique job ID for main table processing
        job_id = f"main_table_processing_{shop_id}_{int(now_utc().timestamp())}"

        # Publish the main table processing event to Redis stream
        event_id = await streams_manager.publish_data_job_event(
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
            access_token="",  # Not needed for main table processing
            job_type="main_table_processing",
        )

        logger.info(
            f"Triggered main table processing",
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
            event_id=event_id,
        )

        return {
            "message": "Main table processing triggered",
            "job_id": job_id,
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "event_id": event_id,
            "status": "processing",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger main table processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/main-table/status/{shop_id}")
async def get_main_table_processing_status(shop_id: str):
    """Get main table processing status for a shop"""
    try:
        if "main_table_processing_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Main table processing consumer not available"
            )

        # Get health status from the consumer
        health_status = await services[
            "main_table_processing_consumer"
        ].get_health_status()

        # Get active jobs for this shop
        active_jobs = {}
        for job_id, job_data in services[
            "main_table_processing_consumer"
        ].active_jobs.items():
            if job_data.get("shop_id") == shop_id:
                active_jobs[job_id] = job_data

        return {
            "shop_id": shop_id,
            "consumer_status": health_status,
            "active_jobs": active_jobs,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get main table processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Feature computation endpoints
@app.post("/api/features/compute")
async def compute_features(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Trigger feature computation consumer via Redis stream"""
    try:
        from app.core.redis_client import streams_manager
        from app.shared.helpers import now_utc

        # Extract parameters from request body (JSON) or form data
        try:
            body = await request.json()
        except:
            # Fallback to form data
            form_data = await request.form()
            body = dict(form_data)

        shop_id = body.get("shop_id")
        batch_size = int(body.get("batch_size", 100))
        features_ready = body.get("features_ready", False)
        incremental = body.get("incremental", True)  # Default to incremental processing

        # Validate required parameters
        if not shop_id:
            raise HTTPException(status_code=400, detail="shop_id is required")

        # Generate a unique job ID
        job_id = f"feature_compute_{shop_id}_{int(now_utc().timestamp())}"

        # Prepare event metadata
        metadata = {
            "batch_size": batch_size,
            "incremental": incremental,
            "trigger_source": "api_endpoint",
            "timestamp": now_utc().isoformat(),
            "processed_count": 0,  # Will be updated by the consumer
        }

        # Publish the feature computation event to Redis stream
        event_id = await streams_manager.publish_features_computed_event(
            job_id=job_id,
            shop_id=shop_id,
            features_ready=features_ready,
            metadata=metadata,
        )

        logger.info(
            f"Triggered feature computation consumer",
            job_id=job_id,
            shop_id=shop_id,
            batch_size=batch_size,
            event_id=event_id,
        )

        return {
            "message": "Feature computation consumer triggered",
            "job_id": job_id,
            "shop_id": shop_id,
            "batch_size": batch_size,
            "event_id": event_id,
            "status": "queued",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger feature computation consumer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/features/status/{shop_id}")
async def get_feature_computation_status(shop_id: str):
    """Get feature computation status for a shop"""
    try:
        # Get the feature computation consumer from services
        if "feature_computation_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Feature computation consumer not available"
            )

        consumer = services["feature_computation_consumer"]

        # Get active jobs for this shop
        active_jobs = {
            job_id: job_info
            for job_id, job_info in consumer.active_feature_jobs.items()
            if job_info.get("shop_id") == shop_id
        }

        return {
            "shop_id": shop_id,
            "consumer_status": consumer.status.value,
            "active_jobs": len(active_jobs),
            "jobs": active_jobs,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get feature computation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/features/architecture/status")
async def get_feature_architecture_status():
    """Get current feature engineering architecture status"""
    try:
        return {
            "architecture": "refactored",
            "use_refactored": True,
            "components": {
                "generators": [
                    "ProductFeatureGenerator",
                    "CustomerFeatureGenerator",
                    "OrderFeatureGenerator",
                    "CollectionFeatureGenerator",
                    "ShopFeatureGenerator",
                ],
                "repository": "FeatureRepository",
                "pipeline": "FeatureEngineeringService",
            },
            "benefits": [
                "Single Responsibility Principle",
                "Separation of Concerns",
                "Improved Testability",
                "Better Maintainability",
                "SQL Injection Security Fixes",
                "Configurable Parameters",
                "Modular Architecture",
                "Independent Component Testing",
            ],
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get architecture status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ML pipeline endpoints
@app.post("/api/ml/pipeline/run")
async def run_ml_pipeline(
    shop_id: str,
    pipeline_config: Dict[str, Any],
    background_tasks: BackgroundTasks,
):
    """Run ML pipeline for a shop"""
    try:
        # Lazy load ML pipeline service
        ml_pipeline_service = await get_service("ml_pipeline")

        # Start ML pipeline in background
        background_tasks.add_task(
            ml_pipeline_service.run_end_to_end_pipeline,
            shop_id,
            {},  # Empty shop_data for now
            pipeline_config,
        )

        return {
            "message": "ML pipeline started",
            "shop_id": shop_id,
            "status": "processing",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to start ML pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/pipeline/status/{shop_id}")
async def get_pipeline_status(shop_id: str, pipeline_id: Optional[str] = None):
    """Get ML pipeline status"""
    try:
        # Lazy load ML pipeline service
        ml_pipeline_service = await get_service("ml_pipeline")

        status = await ml_pipeline_service.get_pipeline_status(shop_id, pipeline_id)
        return status

    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoints
@app.get("/api/analytics/business-metrics/{shop_id}")
async def get_business_metrics(
    shop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get business metrics for a shop"""
    try:
        # Lazy load business metrics service
        business_metrics_service = await get_service("business_metrics")

        # Parse dates
        from datetime import datetime

        start = datetime.fromisoformat(start_date) if start_date else datetime.now()
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()

        metrics = await business_metrics_service.compute_overall_metrics(
            shop_id, start, end
        )
        return metrics

    except Exception as e:
        logger.error(f"Failed to get business metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/kpi-dashboard/{shop_id}")
async def get_kpi_dashboard(shop_id: str):
    """Get KPI dashboard data for a shop"""
    try:
        if "business_metrics" not in services:
            raise HTTPException(
                status_code=500, detail="Business metrics service not available"
            )

        dashboard = await services["business_metrics"].get_kpi_dashboard(shop_id)
        return dashboard

    except Exception as e:
        logger.error(f"Failed to get KPI dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/customer-insights/{shop_id}")
async def get_customer_insights(shop_id: str):
    """Get customer insights for a shop"""
    try:
        if "customer_analytics" not in services:
            raise HTTPException(
                status_code=500, detail="Customer analytics service not available"
            )

        insights = await services["customer_analytics"].get_customer_insights(shop_id)
        return insights

    except Exception as e:
        logger.error(f"Failed to get customer insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/product-insights/{shop_id}")
async def get_product_insights(
    shop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get product insights for a shop"""
    try:
        if "product_analytics" not in services:
            raise HTTPException(
                status_code=500, detail="Product analytics service not available"
            )

        # Parse dates
        from datetime import datetime

        start = datetime.fromisoformat(start_date) if start_date else datetime.now()
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()

        insights = await services["product_analytics"].analyze_product_performance(
            shop_id, start, end
        )
        return insights

    except Exception as e:
        logger.error(f"Failed to get product insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/revenue-insights/{shop_id}")
async def get_revenue_insights(shop_id: str):
    """Get revenue insights for a shop"""
    try:
        if "revenue_analytics" not in services:
            raise HTTPException(
                status_code=500, detail="Revenue analytics service not available"
            )

        insights = await services["revenue_analytics"].get_revenue_insights(shop_id)
        return insights

    except Exception as e:
        logger.error(f"Failed to get revenue insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance analytics endpoints
@app.get("/api/analytics/performance/{shop_id}")
async def get_performance_analytics(
    shop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get performance analytics for a shop"""
    try:
        if "performance_analytics" not in services:
            raise HTTPException(
                status_code=500, detail="Performance analytics service not available"
            )

        # Parse dates
        from datetime import datetime

        start = datetime.fromisoformat(start_date) if start_date else datetime.now()
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()

        performance = await services["performance_analytics"].analyze_shop_performance(
            shop_id, start, end
        )
        return performance

    except Exception as e:
        logger.error(f"Failed to get performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/performance/recommendations/{shop_id}")
async def get_performance_recommendations(shop_id: str):
    """Get performance optimization recommendations"""
    try:
        if "performance_analytics" not in services:
            raise HTTPException(
                status_code=500, detail="Performance analytics service not available"
            )

        recommendations = await services[
            "performance_analytics"
        ].generate_optimization_recommendations(shop_id)
        return {"recommendations": recommendations}

    except Exception as e:
        logger.error(f"Failed to get performance recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Data collection consumer endpoints
@app.post("/api/data-collection/trigger")
async def trigger_data_collection_consumer(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Trigger data collection consumer via Redis stream"""
    try:
        from app.core.redis_client import streams_manager
        from app.shared.helpers import now_utc

        # Extract parameters from request body (JSON) or form data
        try:
            body = await request.json()
        except:
            # Fallback to form data
            form_data = await request.form()
            body = dict(form_data)

        shop_id = body.get("shop_id")
        shop_domain = body.get("shop_domain")
        access_token = body.get("access_token")
        job_type = body.get("job_type", "data_collection")

        # Validate required parameters
        if not shop_id:
            raise HTTPException(status_code=400, detail="shop_id is required")
        if not shop_domain:
            raise HTTPException(status_code=400, detail="shop_domain is required")
        if not access_token:
            raise HTTPException(status_code=400, detail="access_token is required")

        # Generate a unique job ID
        job_id = f"data_collection_{shop_id}_{int(now_utc().timestamp())}"

        # Publish the data collection job to Redis stream
        event_id = await streams_manager.publish_data_job_event(
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
            access_token=access_token,
            job_type=job_type,
        )

        logger.info(
            f"Triggered data collection consumer",
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
            event_id=event_id,
        )

        return {
            "message": "Data collection consumer triggered",
            "job_id": job_id,
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "event_id": event_id,
            "status": "queued",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger data collection consumer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-collection/status/{shop_id}")
async def get_data_collection_status(shop_id: str):
    """Get data collection status for a shop"""
    try:
        # Get the data collection consumer from services
        if "data_collection_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Data collection consumer not available"
            )

        consumer = services["data_collection_consumer"]

        # Get active jobs for this shop
        active_jobs = {
            job_id: job_info
            for job_id, job_info in consumer.active_jobs.items()
            if job_info.get("shop_id") == shop_id
        }

        return {
            "shop_id": shop_id,
            "consumer_status": consumer.status.value,
            "active_jobs": len(active_jobs),
            "jobs": active_jobs,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get data collection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Consumer monitoring endpoints
@app.get("/api/consumers/status")
async def get_consumers_status():
    """Get status of all Redis consumers"""
    try:
        return consumer_manager.get_all_consumers_status()
    except Exception as e:
        logger.error(f"Failed to get consumers status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consumers/{consumer_name}/status")
async def get_consumer_status(consumer_name: str):
    """Get status of a specific consumer"""
    try:
        status = consumer_manager.get_consumer_status(consumer_name)
        if not status:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )
        return status
    except Exception as e:
        logger.error(f"Failed to get consumer status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/consumers/{consumer_name}/circuit-breaker")
async def get_circuit_breaker_status(consumer_name: str):
    """Get circuit breaker status for a specific consumer"""
    try:
        consumer = consumer_manager.get_consumer(consumer_name)
        if not consumer:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )
        return consumer.get_circuit_breaker_status()
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/consumers/{consumer_name}/reset-circuit-breaker")
async def reset_circuit_breaker(consumer_name: str):
    """Reset circuit breaker for a specific consumer"""
    try:
        consumer = consumer_manager.get_consumer(consumer_name)
        if not consumer:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )

        consumer.reset_circuit_breaker()
        return {
            "message": f"Circuit breaker reset for consumer {consumer_name}",
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/consumers/{consumer_name}/restart")
async def restart_consumer(consumer_name: str):
    """Restart a specific consumer"""
    try:
        consumer = consumer_manager.get_consumer(consumer_name)
        if not consumer:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )

        # Stop and restart the consumer
        await consumer.stop()
        await asyncio.sleep(2)  # Wait a bit
        await consumer.start()

        return {
            "message": f"Consumer {consumer_name} restarted",
            "status": consumer.status.value,
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to restart consumer {consumer_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/redis-health")
async def check_redis_health():
    """Check Redis connection health"""
    try:
        from app.core.redis_client import check_redis_health

        is_healthy = await check_redis_health()
        return {"redis_healthy": is_healthy, "timestamp": now_utc().isoformat()}
    except Exception as e:
        logger.error(f"Failed to check Redis health: {e}")
        return {
            "redis_healthy": False,
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/database-health")
async def check_database_health():
    """Check database connection health"""
    try:
        from app.core.database.simple_db_client import check_database_health

        is_healthy = await check_database_health()
        return {
            "database_healthy": is_healthy,
            "timestamp": now_utc().isoformat(),
            "timeout_settings": {
                "connect_timeout": settings.DATABASE_CONNECT_TIMEOUT,
                "query_timeout": settings.DATABASE_QUERY_TIMEOUT,
                "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            },
        }
    except Exception as e:
        logger.error(f"Failed to check database health: {e}")
        return {
            "database_healthy": False,
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/consumer-database-test/{consumer_name}")
async def test_consumer_database_connection(consumer_name: str):
    """Test database connection from a specific consumer's perspective"""
    try:
        consumer = consumer_manager.get_consumer(consumer_name)
        if not consumer:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )

        # Try to get the database and run a simple query
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Test a simple query that consumers might run
        start_time = now_utc()
        result = await db.query_raw('SELECT COUNT(*) as shop_count FROM "Shop"')
        query_time = (now_utc() - start_time).total_seconds()

        return {
            "consumer_name": consumer_name,
            "database_test": "success",
            "query_time_seconds": query_time,
            "shop_count": result[0]["shop_count"] if result else 0,
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Consumer database test failed for {consumer_name}: {e}")
        return {
            "consumer_name": consumer_name,
            "database_test": "failed",
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/raw-payload-structure/{shop_id}")
async def debug_raw_payload_structure(
    shop_id: str, data_type: str = "products", limit: int = 3
):
    """Debug the structure of raw payloads to understand field extraction failures"""
    try:
        from app.core.database.simple_db_client import get_database
        import json

        db = await get_database()

        # Map data types to table names
        table_map = {
            "products": "RawProduct",
            "orders": "RawOrder",
            "customers": "RawCustomer",
            "collections": "RawCollection",
        }

        table_name = table_map.get(data_type, "RawProduct")

        # Get sample raw payloads
        raw_samples = await db.query_raw(
            f'SELECT "shopifyId", "payload", "extractedAt" FROM "{table_name}" WHERE "shopId" = $1 LIMIT $2',
            shop_id,
            limit,
        )

        parsed_samples = []
        for sample in raw_samples:
            payload = sample["payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except:
                    pass

            # Analyze payload structure
            structure_analysis = {
                "shopifyId": sample["shopifyId"],
                "extractedAt": sample["extractedAt"],
                "payload_type": type(payload).__name__,
                "top_level_keys": (
                    list(payload.keys()) if isinstance(payload, dict) else "Not a dict"
                ),
                "has_raw_data": (
                    "raw_data" in payload if isinstance(payload, dict) else False
                ),
                "has_data_key": (
                    "data" in payload if isinstance(payload, dict) else False
                ),
                "has_direct_type": (
                    data_type in payload if isinstance(payload, dict) else False
                ),
            }

            # Check nested structure
            if isinstance(payload, dict):
                if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                    structure_analysis["raw_data_keys"] = list(
                        payload["raw_data"].keys()
                    )
                    structure_analysis["has_nested_type"] = (
                        data_type in payload["raw_data"]
                    )

                if "data" in payload and isinstance(payload["data"], dict):
                    structure_analysis["data_keys"] = list(payload["data"].keys())
                    structure_analysis["has_data_type"] = data_type in payload["data"]

            # Sample of actual payload (first 500 chars)
            payload_str = (
                str(payload)[:500] + "..." if len(str(payload)) > 500 else str(payload)
            )
            structure_analysis["payload_sample"] = payload_str

            parsed_samples.append(structure_analysis)

        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "table_name": table_name,
            "sample_count": len(parsed_samples),
            "samples": parsed_samples,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Debug raw payload structure failed: {e}")
        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/field-extraction-test/{shop_id}")
async def test_field_extraction(
    shop_id: str, data_type: str = "products", limit: int = 2
):
    """Test field extraction on actual raw data to identify extraction issues"""
    try:
        from app.core.database.simple_db_client import get_database
        from app.domains.shopify.services.field_extractor import FieldExtractorService
        from app.domains.shopify.services.data_cleaning_service import (
            DataCleaningService,
        )
        import json

        db = await get_database()
        field_extractor = FieldExtractorService()
        data_cleaner = DataCleaningService()

        # Map data types to table names
        table_map = {
            "products": "RawProduct",
            "orders": "RawOrder",
            "customers": "RawCustomer",
            "collections": "RawCollection",
        }

        table_name = table_map.get(data_type, "RawProduct")

        # Get sample raw payloads
        raw_samples = await db.query_raw(
            f'SELECT "shopifyId", "payload" FROM "{table_name}" WHERE "shopId" = $1 LIMIT $2',
            shop_id,
            limit,
        )

        test_results = []
        for sample in raw_samples:
            shopify_id = sample["shopifyId"]
            payload = sample["payload"]

            # Parse payload if string
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception as parse_error:
                    test_results.append(
                        {
                            "shopifyId": shopify_id,
                            "step": "payload_parsing",
                            "success": False,
                            "error": str(parse_error),
                        }
                    )
                    continue

            # Test field extraction
            try:
                extracted_data = field_extractor.extract_fields_generic(
                    data_type, payload, shop_id
                )
                extraction_success = extracted_data is not None
                extraction_keys = list(extracted_data.keys()) if extracted_data else []
            except Exception as extract_error:
                test_results.append(
                    {
                        "shopifyId": shopify_id,
                        "step": "field_extraction",
                        "success": False,
                        "error": str(extract_error),
                    }
                )
                continue

            # Test data cleaning if extraction succeeded
            cleaning_success = False
            cleaning_keys = []
            cleaning_error = None

            if extraction_success:
                try:
                    cleaned_data = data_cleaner.clean_data_generic(
                        extracted_data, data_type
                    )
                    cleaning_success = cleaned_data is not None
                    cleaning_keys = list(cleaned_data.keys()) if cleaned_data else []
                except Exception as clean_error:
                    cleaning_error = str(clean_error)

            # Check for required ID field
            id_field_config = {
                "products": "productId",
                "orders": "orderId",
                "customers": "customerId",
                "collections": "collectionId",
            }

            required_id_field = id_field_config.get(data_type, "id")
            has_required_id = False

            if cleaning_success:
                has_required_id = bool(cleaned_data.get(required_id_field))

            test_results.append(
                {
                    "shopifyId": shopify_id,
                    "extraction_success": extraction_success,
                    "extraction_keys_count": len(extraction_keys),
                    "cleaning_success": cleaning_success,
                    "cleaning_keys_count": len(cleaning_keys),
                    "has_required_id_field": has_required_id,
                    "required_id_field": required_id_field,
                    "cleaning_error": cleaning_error,
                    "final_status": (
                        "SUCCESS"
                        if extraction_success and cleaning_success and has_required_id
                        else "FAILED"
                    ),
                }
            )

        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "table_name": table_name,
            "sample_count": len(test_results),
            "success_count": len(
                [r for r in test_results if r.get("final_status") == "SUCCESS"]
            ),
            "test_results": test_results,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Field extraction test failed: {e}")
        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.post("/api/debug/test-main-table-processing/{shop_id}")
async def test_main_table_processing(
    shop_id: str, data_type: str = "products", limit: int = 5
):
    """Test main table processing with actual data to verify upsert fixes"""
    try:
        from app.domains.shopify.services.main_table_storage import (
            MainTableStorageService,
        )

        storage_service = MainTableStorageService()

        # Test the main table processing for the specified data type
        result = await storage_service._store_data_generic(
            data_type, shop_id, incremental=True
        )

        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "test_result": {
                "success": result.success,
                "processed_count": result.processed_count,
                "error_count": result.error_count,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
            },
            "message": (
                "SUCCESS"
                if result.success and result.processed_count > 0
                else "FAILED - Check errors"
            ),
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        import traceback

        logger.error(f"Main table processing test failed: {e}")
        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "test_result": "FAILED",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/table-counts/{shop_id}")
async def check_table_counts(shop_id: str):
    """Check raw vs main table counts for debugging"""
    try:
        from app.core.database.simple_db_client import get_database

        db = await get_database()

        # Check all data types
        results = {}
        for data_type in ["products", "orders", "customers", "collections"]:
            # Map to table names
            raw_tables = {
                "products": "RawProduct",
                "orders": "RawOrder",
                "customers": "RawCustomer",
                "collections": "RawCollection",
            }
            main_tables = {
                "products": "ProductData",
                "orders": "OrderData",
                "customers": "CustomerData",
                "collections": "CollectionData",
            }

            raw_table = raw_tables[data_type]
            main_table = main_tables[data_type]

            # Get counts
            raw_count = await db.query_raw(
                f'SELECT COUNT(*) as count FROM "{raw_table}" WHERE "shopId" = $1',
                shop_id,
            )
            main_count = await db.query_raw(
                f'SELECT COUNT(*) as count FROM "{main_table}" WHERE "shopId" = $1',
                shop_id,
            )

            results[data_type] = {
                "raw_count": raw_count[0]["count"] if raw_count else 0,
                "main_count": main_count[0]["count"] if main_count else 0,
                "gap": (raw_count[0]["count"] if raw_count else 0)
                - (main_count[0]["count"] if main_count else 0),
            }

        return {
            "shop_id": shop_id,
            "table_comparison": results,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Table counts check failed: {e}")
        return {
            "shop_id": shop_id,
            "error": str(e),
            "timestamp": now_utc().isoformat(),
        }


@app.get("/api/debug/id-comparison/{shop_id}")
async def debug_id_comparison(shop_id: str, data_type: str = "products"):
    """Debug the exact ID comparison logic to see why records aren't being processed"""
    try:
        from app.domains.shopify.services.main_table_storage import (
            MainTableStorageService,
        )
        from app.core.database.simple_db_client import get_database

        storage_service = MainTableStorageService()
        db = await get_database()

        # Import the module-level config
        from app.domains.shopify.services.main_table_storage import DATA_TYPE_CONFIG

        # Get the config
        config = DATA_TYPE_CONFIG[data_type]

        # Step 1: Get raw IDs (same logic as _store_data_generic)
        raw_result = await db.query_raw(
            f'SELECT "{config["raw_id_field"]}" FROM "{config["raw_table"]}" WHERE "shopId" = $1 AND "{config["raw_id_field"]}" IS NOT NULL ORDER BY "extractedAt" ASC LIMIT 10',
            shop_id,
        )

        # Extract numeric IDs from raw data
        raw_shopify_ids = [
            row[config["raw_id_field"]]
            for row in raw_result
            if row[config["raw_id_field"]]
        ]
        raw_ids_extracted = [
            storage_service._extract_shopify_id(id) for id in raw_shopify_ids
        ]
        raw_ids = [id for id in raw_ids_extracted if id]  # Filter out None values

        # Step 2: Get processed IDs (original format)
        processed_ids_raw = await storage_service._get_processed_shopify_ids(
            shop_id, data_type
        )

        # Step 3: Normalize processed IDs (same as the fix)
        processed_ids_normalized = set()
        for pid in processed_ids_raw:
            extracted_id = storage_service._extract_shopify_id(pid) if pid else None
            if extracted_id:
                processed_ids_normalized.add(extracted_id)

        # Step 4: Compare
        new_ids = [id for id in raw_ids if id not in processed_ids_normalized]

        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "analysis": {
                "raw_shopify_ids_sample": raw_shopify_ids[:5],
                "raw_ids_extracted_sample": raw_ids[:5],
                "processed_ids_raw_sample": list(processed_ids_raw)[:5],
                "processed_ids_normalized_sample": list(processed_ids_normalized)[:5],
                "new_ids_sample": new_ids[:5],
                "counts": {
                    "total_raw_ids": len(raw_ids),
                    "total_processed_ids": len(processed_ids_normalized),
                    "new_ids_to_process": len(new_ids),
                },
            },
            "conclusion": {
                "should_process": len(new_ids) > 0,
                "reason": (
                    "All records already processed"
                    if len(new_ids) == 0
                    else f"{len(new_ids)} new records found"
                ),
            },
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        import traceback

        logger.error(f"ID comparison debug failed: {e}")
        return {
            "shop_id": shop_id,
            "data_type": data_type,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": now_utc().isoformat(),
        }


@app.post("/api/shopify/permissions/cache/clear")
async def clear_permission_cache(shop_domain: Optional[str] = None):
    """Clear permission cache for a specific shop or all shops"""
    try:
        if "shopify" not in services:
            raise HTTPException(status_code=500, detail="Shopify service not available")

        shopify_service = services["shopify"]
        # Clear the cache of the permission service that's actually used by the data collection service
        await shopify_service.permission_service.clear_permission_cache(shop_domain)

        if shop_domain:
            return {"message": f"Permission cache cleared for {shop_domain}"}
        else:
            return {"message": "All permission cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear permission cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Gorse training monitoring endpoints
@app.get("/api/ml/training/monitor/status")
async def get_training_monitor_status():
    """Get Gorse training monitor status"""
    try:
        if "gorse_training_monitor" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse training monitor not available"
            )

        return services["gorse_training_monitor"].get_monitoring_status()
    except Exception as e:
        logger.error(f"Failed to get training monitor status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/training/completions")
async def get_training_completions(shop_id: Optional[str] = None):
    """Get training completion events"""
    try:
        if "gorse_training_monitor" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse training monitor not available"
            )

        events = services["gorse_training_monitor"].get_completion_events(shop_id)
        return {"events": events, "count": len(events)}
    except Exception as e:
        logger.error(f"Failed to get training completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Heuristic service endpoints
@app.post("/api/heuristic/evaluate/{shop_id}")
async def evaluate_analysis_need(shop_id: str):
    """Evaluate if analysis should be run for a shop"""
    try:
        if "heuristic" not in services:
            raise HTTPException(
                status_code=500, detail="Heuristic service not available"
            )

        decision = await services["heuristic"].evaluate_analysis_need(shop_id)
        return decision
    except Exception as e:
        logger.error(f"Failed to evaluate analysis need: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Webhook endpoints
@app.post("/collect/behavioral-events")
async def handle_behavioral_event(
    request: Request,
    x_shopify_shop_domain: Optional[str] = Header(None),
):
    """This endpoint receives behavioral events from the Shopify Web Pixel and queues them for background processing."""
    try:
        if "webhook_handler" not in services:
            raise HTTPException(status_code=500, detail="Webhook handler not available")

        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    shop_id = x_shopify_shop_domain or payload.get("context", {}).get("shop", {}).get(
        "domain"
    )

    if not shop_id:
        raise HTTPException(status_code=400, detail="Shop domain not found in request.")

    # Queue the event for background processing instead of processing directly
    result = await services["webhook_handler"].queue_behavioral_event(shop_id, payload)

    if "error" in result.get("status"):
        raise HTTPException(status_code=500, detail=result)

    return result


@app.get("/api/behavioral-events/status")
async def get_behavioral_events_status():
    """Get status of behavioral events processing"""
    try:
        if "behavioral_events_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Behavioral events consumer not available"
            )

        active_events = await services["behavioral_events_consumer"].get_active_events()

        return {
            "status": "active",
            "active_events_count": len(active_events),
            "active_events": active_events,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get behavioral events status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/behavioral-events/status/{event_id}")
async def get_behavioral_event_status(event_id: str):
    """Get status of a specific behavioral event"""
    try:
        if "behavioral_events_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Behavioral events consumer not available"
            )

        event_status = await services["behavioral_events_consumer"].get_event_status(
            event_id
        )

        if not event_status:
            raise HTTPException(status_code=404, detail="Event not found")

        return {
            "event_id": event_id,
            "status": event_status,
            "timestamp": now_utc().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get behavioral event status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Gorse sync endpoints
@app.post("/api/gorse/sync")
async def trigger_gorse_sync(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Trigger Gorse data synchronization via Redis stream"""
    try:
        from app.core.redis_client import streams_manager
        from app.shared.helpers import now_utc

        # Extract parameters from request body (JSON) or form data
        try:
            body = await request.json()
        except:
            # Fallback to form data
            form_data = await request.form()
            body = dict(form_data)

        shop_id = body.get("shop_id")
        sync_type = body.get("sync_type", "all")  # all, users, items, feedback
        since_hours = int(body.get("since_hours", 24))

        # Validate required parameters
        if not shop_id:
            raise HTTPException(status_code=400, detail="shop_id is required")

        # Validate sync_type
        valid_sync_types = ["all", "users", "items", "feedback"]
        if sync_type not in valid_sync_types:
            raise HTTPException(
                status_code=400,
                detail=f"sync_type must be one of: {', '.join(valid_sync_types)}",
            )

        # Generate a unique job ID
        job_id = f"gorse_sync_{shop_id}_{sync_type}_{int(now_utc().timestamp())}"

        # Prepare event metadata
        metadata = {
            "trigger_source": "api_endpoint",
            "timestamp": now_utc().isoformat(),
        }

        # Publish the Gorse sync event to Redis stream
        event_id = await streams_manager.publish_gorse_sync_event(
            job_id=job_id,
            shop_id=shop_id,
            sync_type=sync_type,
            since_hours=since_hours,
            metadata=metadata,
        )

        logger.info(
            f"Triggered Gorse sync",
            job_id=job_id,
            shop_id=shop_id,
            sync_type=sync_type,
            since_hours=since_hours,
            event_id=event_id,
        )

        return {
            "message": "Gorse sync triggered",
            "job_id": job_id,
            "shop_id": shop_id,
            "sync_type": sync_type,
            "since_hours": since_hours,
            "event_id": event_id,
            "status": "queued",
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger Gorse sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gorse/sync/status/{shop_id}")
async def get_gorse_sync_status(shop_id: str):
    """Get Gorse sync status for a shop"""
    try:
        # Get the Gorse sync consumer from services
        if "gorse_sync_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse sync consumer not available"
            )

        consumer = services["gorse_sync_consumer"]

        # Get active jobs for this shop
        active_jobs = {
            job_id: job_info
            for job_id, job_info in consumer.active_sync_jobs.items()
            if job_info.get("shop_id") == shop_id
        }

        return {
            "shop_id": shop_id,
            "consumer_status": consumer.status.value,
            "active_jobs": len(active_jobs),
            "jobs": active_jobs,
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get Gorse sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gorse/sync/health")
async def get_gorse_sync_health():
    """Get Gorse sync consumer health status"""
    try:
        if "gorse_sync_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse sync consumer not available"
            )

        health_status = await services["gorse_sync_consumer"].get_health_status()
        return health_status

    except Exception as e:
        logger.error(f"Failed to get Gorse sync health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gorse/train")
async def trigger_gorse_training(
    shop_id: str,
    job_type: str = Query(
        default="full_training",
        description="Type of training: full_training, incremental_training, model_refresh",
    ),
    background_tasks: BackgroundTasks = None,
):
    """Trigger Gorse model training for a shop"""
    try:
        if "gorse_training_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse training consumer not available"
            )

        consumer = services["gorse_training_consumer"]

        # Create training job
        job_id = f"training_{shop_id}_{job_type}_{int(time.time())}"

        # Prepare event metadata
        metadata = {
            "trigger_source": "api_endpoint",
            "timestamp": datetime.now().isoformat(),
        }

        # Publish the Gorse training event to Redis stream
        from app.core.redis_client import streams_manager

        event_id = await streams_manager.publish_gorse_training_event(
            job_id=job_id,
            shop_id=shop_id,
            job_type=job_type,
            trigger_source="api",
            metadata=metadata,
        )

        logger.info(
            f"Triggered Gorse training | job_id={job_id} | shop_id={shop_id} | job_type={job_type} | event_id={event_id}"
        )

        return {
            "status": "success",
            "message": "Gorse training job created and queued",
            "job_id": job_id,
            "shop_id": shop_id,
            "job_type": job_type,
        }

    except Exception as e:
        logger.error(f"Failed to trigger Gorse training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gorse/training/status/{job_id}")
async def get_training_job_status(job_id: str):
    """Get training job status"""
    try:
        if "gorse_training_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse training consumer not available"
            )

        from app.domains.ml.services.gorse_training_service import GorseTrainingService

        training_service = GorseTrainingService()
        job_status = await training_service.get_training_job_status(job_id)

        if not job_status:
            raise HTTPException(
                status_code=404, detail=f"Training job {job_id} not found"
            )

        return job_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gorse/training/health")
async def get_training_health():
    """Get training consumer health status"""
    try:
        if "gorse_training_consumer" not in services:
            raise HTTPException(
                status_code=500, detail="Gorse training consumer not available"
            )

        health_status = await services["gorse_training_consumer"].health_check()
        return health_status

    except Exception as e:
        logger.error(f"Failed to get training health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": now_utc().isoformat(),
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
