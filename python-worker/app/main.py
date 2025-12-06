"""
Main application for BetterBundle Python Worker
"""

import asyncio
import signal
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config.settings import settings
from app.core.logging import get_logger
from app.shared.helpers import now_utc

from app.domains.shopify.services import (
    ShopifyDataCollectionService,
    ShopifyAPIClient,
    ShopifyPermissionService,
)


from app.core.kafka.consumer_manager import KafkaConsumerManager


from app.api.v1.unified_gorse import router as unified_gorse_router
from app.api.v1.attribution_backfill import router as attribution_backfill_router
from app.api.v1.customer_linking import router as customer_linking_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.record_matching import router as record_matching_router
from app.api.v1.fbt_status import router as fbt_status_router
from app.api.v1.logs import router as logs_router
from app.api.v1.data_collection import router as data_collection_router
from app.domains.billing.api.billing_api import router as billing_api_router
from app.routes.auth_routes import router as auth_router
from app.routes.session_routes import router as session_router
from app.routes.interaction_routes import router as interaction_router
from app.routes.recommendation_routes import router as recommendation_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup

    # Initialize services
    await initialize_services()

    # Start Kafka consumers
    global kafka_consumer_manager
    if kafka_consumer_manager:
        await kafka_consumer_manager.start_all_consumers()

    yield

    # Shutdown

    # Stop Kafka consumers first
    if kafka_consumer_manager:
        await kafka_consumer_manager.stop_all_consumers()

    # Close topic manager
    from app.core.kafka.topic_manager import topic_manager

    await topic_manager.close()

    await cleanup_services()


# Create FastAPI app
app = FastAPI(
    title="BetterBundle Python Worker",
    description="AI-powered Shopify analytics and ML platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(unified_gorse_router)
app.include_router(attribution_backfill_router)
app.include_router(customer_linking_router)
app.include_router(recommendations_router)
app.include_router(record_matching_router)
app.include_router(fbt_status_router)
app.include_router(logs_router)
app.include_router(data_collection_router)
app.include_router(billing_api_router)
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(interaction_router)
app.include_router(recommendation_router)

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

# Kafka Consumer Manager (global instance)
kafka_consumer_manager = None


async def initialize_services():
    """Initialize only essential services at startup"""
    try:
        logger.info("Starting service initialization...")

        # 1. Check Database connectivity first (critical - fail if unavailable)
        logger.info("Checking database connectivity...")
        from app.core.database.engine import get_engine
        from sqlalchemy import text

        try:
            engine = await get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise Exception(f"Database is not available: {e}")

        # 2. Check Redis connectivity (non-blocking - log warning but continue)
        logger.info("Checking Redis connectivity...")
        from app.core.redis.health import check_redis_health

        try:
            redis_health = await check_redis_health()
            if redis_health.is_healthy:
                logger.info("✅ Redis connection verified")
            else:
                logger.warning(
                    f"⚠️ Redis connection check failed: {redis_health.error_message}"
                )
                logger.warning(
                    "⚠️ Application will start but Redis-dependent features may not work"
                )
        except Exception as e:
            logger.warning(f"⚠️ Redis health check error: {e}")
            logger.warning(
                "⚠️ Application will start but Redis-dependent features may not work"
            )

        # Initialize Shopify services
        services["shopify_api"] = ShopifyAPIClient()
        services["shopify_permissions"] = ShopifyPermissionService(
            api_client=services["shopify_api"]
        )
        services["shopify"] = ShopifyDataCollectionService(
            api_client=services["shopify_api"],
            permission_service=services["shopify_permissions"],
        )

        # Initialize database and create tables (now we know DB is accessible)
        from app.core.database.create_tables import create_all_tables

        await create_all_tables()
        logger.info("✅ Database tables verified/created")

        # Initialize Kafka Topic Manager and create topics
        from app.core.kafka.topic_manager import topic_manager

        await topic_manager.initialize()
        await topic_manager.create_topics_if_not_exist()
        logger.info("✅ Kafka topics verified/created")

        # Initialize Kafka Consumer Manager
        global kafka_consumer_manager
        kafka_consumer_manager = KafkaConsumerManager(
            shopify_service=services.get("shopify")
        )
        await kafka_consumer_manager.initialize()
        logger.info("✅ Kafka consumers initialized")

        logger.info("✅ All services initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        logger.error("Application startup failed - critical services are not available")
        raise


async def cleanup_services():
    """Cleanup all services"""
    try:

        # Kafka consumers are stopped by kafka_consumer_manager in lifespan

        # Shutdown database connections
        from app.core.database.engine import close_engine

        # Close SQLAlchemy connections
        await close_engine()  # SQLAlchemy engine

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

    return health_status


# Redis health check endpoint
@app.get("/health/redis")
async def redis_health_check():
    """Redis connection health check endpoint"""
    from app.core.redis.health import check_redis_health

    health_status = await check_redis_health()

    if health_status.is_healthy:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "redis": {
                    "is_healthy": health_status.is_healthy,
                    "connection_info": health_status.connection_info,
                    "response_time_ms": health_status.response_time_ms,
                    "last_check": health_status.last_check,
                },
            },
        )
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "redis": {
                    "is_healthy": health_status.is_healthy,
                    "error_message": health_status.error_message,
                    "response_time_ms": health_status.response_time_ms,
                    "last_check": health_status.last_check,
                },
            },
        )


# Generic Kafka Event Endpoints
@app.post("/api/kafka/events/publish")
async def publish_kafka_event(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Generic endpoint to publish events to any Kafka topic"""
    try:
        from app.core.messaging.event_publisher import EventPublisher

        # Extract parameters from request body
        try:
            body = await request.json()
        except:
            form_data = await request.form()
            body = dict(form_data)

        # Required fields
        topic = body.get("topic")
        event_data = body.get("event_data", {})
        event_type = body.get("event_type")
        shop_id = body.get("shop_id")
        key = body.get("key", shop_id)  # Use shop_id as default key

        # Validate required parameters
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")
        if not event_data:
            raise HTTPException(status_code=400, detail="event_data is required")

        # Initialize event publisher
        from app.core.config.kafka_settings import kafka_settings

        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()

        try:
            # Add metadata to event data
            event_with_metadata = {
                **event_data,
                "timestamp": now_utc().isoformat(),
                "event_type": event_type,
                "shop_id": shop_id,
                "source": "api_trigger",
            }

            # Publish event based on topic
            if topic == "shopify-events":
                message_id = await publisher.publish_shopify_event(event_with_metadata)
            elif topic == "data-collection-jobs":
                message_id = await publisher.publish_data_job_event(event_with_metadata)
            elif topic == "normalization-jobs":
                message_id = await publisher.publish_normalization_event(
                    event_with_metadata
                )
            elif topic == "ml-training":
                message_id = await publisher.publish_ml_training_event(
                    event_with_metadata
                )
            elif topic == "behavioral-events":
                message_id = await publisher.publish_behavioral_event(
                    event_with_metadata
                )
            elif topic == "billing-events":
                message_id = await publisher.publish_billing_event(event_with_metadata)
            elif topic == "access-control":
                message_id = await publisher.publish_access_control_event(
                    event_with_metadata
                )
            elif topic == "analytics-events":
                message_id = await publisher.publish_analytics_event(
                    event_with_metadata
                )
            elif topic == "notification-events":
                message_id = await publisher.publish_notification_event(
                    event_with_metadata
                )
            elif topic == "integration-events":
                message_id = await publisher.publish_integration_event(
                    event_with_metadata
                )
            elif topic == "audit-events":
                message_id = await publisher.publish_audit_event(event_with_metadata)
            elif topic == "feature-computation-jobs":
                message_id = await publisher.publish_feature_computation_event(
                    event_with_metadata
                )
            elif topic == "customer-linking-jobs":
                message_id = await publisher.publish_customer_linking_event(
                    event_with_metadata
                )
            elif topic == "purchase-attribution-jobs":
                message_id = await publisher.publish_purchase_attribution_event(
                    event_with_metadata
                )
            # ✅ REFUND ATTRIBUTION REMOVED - No refund commission policy
            else:
                raise HTTPException(status_code=400, detail=f"Unknown topic: {topic}")

            return {
                "message": f"Event published to {topic}",
                "topic": topic,
                "message_id": message_id,
                "event_type": event_type,
                "shop_id": shop_id,
                "status": "published",
                "timestamp": now_utc().isoformat(),
            }
        finally:
            await publisher.close()

    except Exception as e:
        logger.error(f"Failed to publish Kafka event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kafka/topics")
async def get_available_topics():
    """Get list of available Kafka topics and their configurations"""
    try:
        from app.core.config.kafka_settings import kafka_settings

        topics_info = {}
        for topic_name, config in kafka_settings.topics.items():
            topics_info[topic_name] = {
                "partitions": config.get("partitions", 1),
                "replication_factor": config.get("replication_factor", 1),
                "retention_ms": config.get("retention_ms"),
                "compression_type": config.get("compression_type", "none"),
                "cleanup_policy": config.get("cleanup_policy", "delete"),
            }

        return {
            "topics": topics_info,
            "total_topics": len(topics_info),
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get Kafka topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kafka/consumers/status")
async def get_consumers_status():
    """Get status of all Kafka consumers"""
    try:
        consumer_status = {}

        # Check each consumer type
        consumer_types = [
            "shopify_events_consumer",
            "data_collection_consumer",
            "normalization_consumer",
            "purchase_attribution_consumer",
            "feature_computation_consumer",
            "customer_linking_consumer",
            "shopify_events_consumer",
        ]

        for consumer_type in consumer_types:
            if consumer_type in services:
                consumer = services[consumer_type]
                if hasattr(consumer, "get_health_status"):
                    status = await consumer.get_health_status()
                elif hasattr(consumer, "active_jobs"):
                    status = {
                        "status": "running",
                        "active_jobs": len(consumer.active_jobs),
                        "last_health_check": now_utc().isoformat(),
                    }
                else:
                    status = {"status": "unknown"}

                consumer_status[consumer_type] = status
            else:
                consumer_status[consumer_type] = {"status": "not_initialized"}

        # Add Kafka consumer manager status
        global kafka_consumer_manager
        if kafka_consumer_manager:
            kafka_status = await kafka_consumer_manager.get_health_status()
            consumer_status["kafka_consumer_manager"] = kafka_status
        else:
            consumer_status["kafka_consumer_manager"] = {"status": "not_initialized"}

        return {
            "consumers": consumer_status,
            "total_consumers": len(consumer_status),
            "timestamp": now_utc().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get consumers status: {e}")
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


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""

    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        # The lifespan manager will handle the actual cleanup

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
