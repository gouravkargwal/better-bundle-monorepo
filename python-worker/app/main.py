"""
Main application for BetterBundle Python Worker
"""

import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from app.core.config import settings
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
    GorseMLService,
    MLPipelineService,
)
from app.domains.analytics.services import (
    BusinessMetricsService,
    PerformanceAnalyticsService,
    CustomerAnalyticsService,
    ProductAnalyticsService,
    RevenueAnalyticsService,
    HeuristicService,
)
from app.domains.ml.services.gorse_training_monitor import GorseTrainingMonitor

# Consumer imports
from app.consumers.consumer_manager import consumer_manager
from app.consumers.data_collection_consumer import DataCollectionConsumer
from app.consumers.ml_training_consumer import MLTrainingConsumer
from app.consumers.analytics_consumer import AnalyticsConsumer

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

        # Register and start only data collection consumer
        consumer_manager.register_consumers(
            data_collection_consumer=services["data_collection_consumer"],
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
            services["feature_engineering"] = FeatureEngineeringService()
        elif service_name == "gorse_ml":
            services["gorse_ml"] = GorseMLService()
        elif service_name == "ml_pipeline":
            if "feature_engineering" not in services:
                await get_service("feature_engineering")
            if "gorse_ml" not in services:
                await get_service("gorse_ml")
            services["ml_pipeline"] = MLPipelineService(
                feature_service=services["feature_engineering"],
                gorse_service=services["gorse_ml"],
            )
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
        elif service_name == "gorse_training_monitor":
            if "heuristic" not in services:
                await get_service("heuristic")
            services["gorse_training_monitor"] = GorseTrainingMonitor(
                heuristic_service=services["heuristic"]
            )
        elif service_name == "ml_training_consumer":
            if "ml_pipeline" not in services:
                await get_service("ml_pipeline")
            services["ml_training_consumer"] = MLTrainingConsumer(
                ml_pipeline_service=services["ml_pipeline"]
            )
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

    return services[service_name]


async def cleanup_services():
    """Cleanup all services"""
    try:
        logger.info("Cleaning up services...")

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

        logger.info("Services cleaned up successfully")

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
            services["shopify"].collect_all_data,
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


@app.post("/api/consumers/{consumer_name}/circuit-breaker/reset")
async def reset_circuit_breaker(consumer_name: str):
    """Manually reset circuit breaker for a specific consumer"""
    try:
        consumer = consumer_manager.get_consumer(consumer_name)
        if not consumer:
            raise HTTPException(
                status_code=404, detail=f"Consumer {consumer_name} not found"
            )

        consumer.reset_circuit_breaker()
        return {"message": f"Circuit breaker reset for {consumer_name}"}
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
