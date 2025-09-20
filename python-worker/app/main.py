"""
Main application for BetterBundle Python Worker
"""

import asyncio
import json
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

# All analytics services removed - they were causing async_timing decorator errors

# Consumer imports
from app.consumers.consumer_manager import consumer_manager
from app.consumers.data_collection_consumer import DataCollectionConsumer
from app.consumers.normalization_consumer import NormalizationConsumer
from app.consumers.purchase_attribution_consumer import PurchaseAttributionConsumer

# AnalyticsConsumer removed - was using deleted analytics services
from app.consumers.feature_computation_consumer import FeatureComputationConsumer

# Webhook imports
from app.webhooks.handler import WebhookHandler
from app.webhooks.repository import WebhookRepository

# from app.consumers.behavioral_events_consumer import BehavioralEventsConsumer  # Removed - using unified analytics
from app.consumers.customer_linking_consumer import CustomerLinkingConsumer
from app.consumers.shopify_events_consumer import ShopifyEventsConsumer
from app.consumers.refund_normalization_consumer import RefundNormalizationConsumer
from app.consumers.refund_attribution_consumer import RefundAttributionConsumer

# Note: Old Gorse consumers removed - using unified_gorse_service.py instead
from app.core.database.simple_db_client import get_database, close_database
from app.core.redis_client import streams_manager
from datetime import datetime
from typing import Optional

# API imports
from app.api.v1.unified_gorse import router as unified_gorse_router
from app.api.v1.customer_linking import router as customer_linking_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.extension_activity import router as extension_activity_router

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
app.include_router(unified_gorse_router)
app.include_router(customer_linking_router)
app.include_router(recommendations_router)
app.include_router(extension_activity_router)

# Include unified analytics routers
from app.domains.analytics.api import (
    venus_router,
    atlas_router,
    phoenix_router,
    apollo_router,
    customer_identity_router,
)

app.include_router(venus_router)
app.include_router(atlas_router)
app.include_router(phoenix_router)
app.include_router(apollo_router)
app.include_router(customer_identity_router)

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

        # Initialize normalization consumer
        services["normalization_consumer"] = NormalizationConsumer()

        # Initialize purchase attribution consumer
        services["purchase_attribution_consumer"] = PurchaseAttributionConsumer()

        # Initialize feature computation consumer
        services["feature_computation_consumer"] = FeatureComputationConsumer()

        # Behavioral events consumer removed - using unified analytics system

        # Initialize customer linking consumer
        services["customer_linking_consumer"] = CustomerLinkingConsumer()

        # Initialize Shopify events consumer
        services["shopify_events_consumer"] = ShopifyEventsConsumer()

        # Initialize refund consumers
        services["refund_normalization_consumer"] = RefundNormalizationConsumer()
        services["refund_attribution_consumer"] = RefundAttributionConsumer()

        # Note: Old Gorse consumers removed - using unified_gorse_service.py instead

        # Initialize webhook services
        services["webhook_repository"] = WebhookRepository()
        services["webhook_handler"] = WebhookHandler(services["webhook_repository"])

        # Initialize billing services
        from app.domains.billing.services.billing_service import BillingService
        from app.domains.billing.jobs.monthly_billing_job import MonthlyBillingJob

        services["billing_service"] = BillingService(prisma)
        services["monthly_billing_job"] = MonthlyBillingJob(prisma)

        # Register and start consumers
        consumer_manager.register_consumers(
            data_collection_consumer=services["data_collection_consumer"],
            normalization_consumer=services["normalization_consumer"],
            purchase_attribution_consumer=services["purchase_attribution_consumer"],
            feature_computation_consumer=services["feature_computation_consumer"],
            customer_linking_consumer=services["customer_linking_consumer"],
            shopify_events_consumer=services["shopify_events_consumer"],
            refund_normalization_consumer=services["refund_normalization_consumer"],
            refund_attribution_consumer=services["refund_attribution_consumer"],
            # Note: Old Gorse consumers removed - using unified_gorse_service.py instead
            # Note: BehavioralEventsConsumer removed - using unified analytics system
        )

        # Start consumer manager (this will start all registered consumers)
        await consumer_manager.start()

        # Note: Monthly billing now handled by GitHub Actions
        # See .github/workflows/monthly-billing.yml

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
            # Note: gorse_ml service removed - using unified_gorse_service.py instead
        # All analytics services removed - they were causing async_timing decorator errors
        # Analytics consumer removed - was using deleted analytics services
        elif service_name == "feature_computation_consumer":
            services["feature_computation_consumer"] = FeatureComputationConsumer()

    return services[service_name]


# Monthly billing scheduler removed - now handled by GitHub Actions
# See .github/workflows/monthly-billing.yml for the cron job


async def cleanup_services():
    """Cleanup all services"""
    try:

        # Stop consumer manager
        await consumer_manager.stop()

        # Note: Old Gorse services removed - using unified_gorse_service.py instead

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
    health_status = {
        "status": "healthy",
        "timestamp": now_utc().isoformat(),
        "version": "1.0.0",
        "services": list(services.keys()),
    }

    # ShopifyEventsConsumer health check removed - consumer was replaced by NormalizationConsumer

    return health_status


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

        # Validate that the shop exists and is active
        try:
            from app.core.database.simple_db_client import get_database

            db = await get_database()
            shop = await db.shop.find_unique(where={"id": shop_id})

            if not shop:
                raise HTTPException(
                    status_code=404, detail=f"Shop not found for ID: {shop_id}"
                )

            if not shop.isActive:
                raise HTTPException(
                    status_code=400, detail=f"Shop is inactive for ID: {shop_id}"
                )

            logger.info(
                f"Shop validation successful for main table processing: {shop_id} (domain: {shop.shopDomain})"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to validate shop for main table processing: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to validate shop: {str(e)}"
            )

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
        import traceback

        error_detail = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        logger.error(f"Failed to trigger main table processing: {error_detail}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_detail)


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


# Billing endpoints
@app.post("/api/billing/run-monthly")
async def run_monthly_billing():
    """Manually trigger monthly billing for all shops"""
    try:
        if "monthly_billing_job" not in services:
            raise HTTPException(
                status_code=500, detail="Monthly billing job not available"
            )

        logger.info("🔄 Manual monthly billing triggered")
        result = await services["monthly_billing_job"].run_monthly_billing()

        return {
            "message": "Monthly billing completed",
            "result": result,
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to run monthly billing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/run-shop/{shop_id}")
async def run_shop_billing(shop_id: str):
    """Manually trigger billing for a specific shop"""
    try:
        if "monthly_billing_job" not in services:
            raise HTTPException(
                status_code=500, detail="Monthly billing job not available"
            )

        logger.info(f"🔄 Manual billing triggered for shop {shop_id}")
        result = await services["monthly_billing_job"].run_shop_billing(shop_id)

        return {
            "message": f"Billing completed for shop {shop_id}",
            "result": result,
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to run billing for shop {shop_id}: {e}")
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


# Webhook endpoints
@app.post("/collect/behavioral-events")
async def handle_behavioral_event(request: Request):
    """This endpoint receives behavioral events from the Shopify Web Pixel and queues them for background processing.

    Authentication: Uses shop domain validation for basic security.
    """
    try:
        if "webhook_handler" not in services:
            raise HTTPException(status_code=500, detail="Webhook handler not available")

        # Get payload from request body
        payload = await request.json()
        shop_domain = payload.get("shop_domain")

        # Validate shop domain
        if not shop_domain:
            raise HTTPException(
                status_code=400, detail="shop_domain required in payload."
            )

        # Basic shop validation with Redis caching
        try:
            from app.core.redis_client import get_redis_client

            # Try Redis cache first
            redis_client = await get_redis_client()
            cache_key = f"shop_domain:{shop_domain}"
            cached_shop_data = await redis_client.get(cache_key)

            if cached_shop_data:
                # Cache hit - decode and validate
                shop_data = json.loads(
                    cached_shop_data.decode("utf-8")
                    if isinstance(cached_shop_data, bytes)
                    else cached_shop_data
                )
                if not shop_data.get("isActive", False):
                    raise HTTPException(status_code=403, detail="Shop is not active.")
            else:
                # Cache miss - query database
                db = await get_database()
                shop = await db.shop.find_unique(
                    where={"shopDomain": shop_domain},
                )

                if not shop:
                    raise HTTPException(
                        status_code=404, detail="Shop not found in our system."
                    )

                if not shop.isActive:
                    raise HTTPException(status_code=403, detail="Shop is not active.")

                # Cache the result for 1 hour
                shop_data = {
                    "id": shop.id,
                    "shopDomain": shop.shopDomain,
                    "isActive": shop.isActive,
                }
                await redis_client.setex(cache_key, 3600, json.dumps(shop_data))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to validate shop domain: {e}")
            raise HTTPException(status_code=500, detail="Failed to validate request.")

        logger.info(f"Shop validation successful for: {shop_domain}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process behavioral event: {e}")
        raise HTTPException(status_code=500, detail="Failed to process request.")

    # Queue the event for background processing
    result = await services["webhook_handler"].queue_behavioral_event(
        shop_domain, payload
    )

    if "error" in result.get("status"):
        raise HTTPException(status_code=500, detail=result)

    return result


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
