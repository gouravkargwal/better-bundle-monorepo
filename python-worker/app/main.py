"""
Main application for BetterBundle Python Worker
"""

import asyncio
import signal
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config.settings import settings
from app.core.logging import get_logger
from app.core.logging.otel_logger import init_otel_logger
from app.core.logging.otel_metrics import init_otel_metrics
from app.core.logging.otel_tracing import init_otel_tracing
from app.shared.helpers import now_utc

from app.domains.shopify.services import (
    ShopifyDataCollectionService,
    ShopifyAPIClient,
    ShopifyPermissionService,
)


from app.core.kafka.consumer_manager import KafkaConsumerManager


from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.edges_status import router as edges_status_router
from app.api.v1.impact import router as impact_router
from app.domains.billing.api.billing_api import router as billing_api_router
from app.routes.auth_routes import router as auth_router
from app.api.v1.outcome import router as outcome_router
from app.api.v1.attribution_backfill import router as attribution_backfill_router

logger = get_logger(__name__)

# OTel provider instances – kept alive for graceful shutdown
_otel_provider = None
_metrics_provider = None
_tracer_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup

    # Initialize OpenTelemetry tracing (must precede logs so log records
    # carry trace_id/span_id)
    global _tracer_provider
    _tracer_provider = init_otel_tracing(settings)
    logger.info("✅ OpenTelemetry tracing initialized")

    # Initialize OpenTelemetry logging
    global _otel_provider
    _otel_provider = init_otel_logger(settings)
    logger.info("✅ OpenTelemetry logging initialized")

    # Initialize OpenTelemetry metrics
    global _metrics_provider
    _metrics_provider = init_otel_metrics(settings)
    logger.info("✅ OpenTelemetry metrics initialized")

    # Initialize services
    await initialize_services()

    # Start Kafka consumers
    global kafka_consumer_manager
    if kafka_consumer_manager:
        await kafka_consumer_manager.start_all_consumers()

    # Retry driver for LLM enrichment. Without this, a product whose enrichment
    # failed stays unenriched until its next products/update webhook — which
    # for a quiet catalog may be never.
    from app.recommandations.edges import enrichment_sweeper

    sweeper_task = asyncio.create_task(enrichment_sweeper.run_forever())
    logger.info("✅ Enrichment retry sweeper started")

    # Safety net for missed order webhooks. Shopify retries for 48h then gives
    # up; a deploy, an outage or a consumer rebalance in that window means the
    # order arrives only via the periodic collection, which is deliberately not
    # attributed. Without this sweep that sale is never billed and never shown
    # to the merchant, and nothing reports it.
    from app.domains.billing.services import attribution_reconciler

    reconciler_task = asyncio.create_task(attribution_reconciler.run_forever())
    logger.info("✅ Attribution reconciler started")

    # Rollover reconciler for usage-based billing. Detects 30-day Shopify cycle
    # rollovers for suspended shops and reactivates them while draining backlogged
    # commissions.
    from app.domains.billing.services import rollover_reconciler

    rollover_task = asyncio.create_task(rollover_reconciler.run_forever())
    logger.info("✅ Rollover reconciler started")

    # FX rates for billing. Attributed revenue is in the shopper's currency and
    # commissions are USD; without these rates every non-USD shop is either
    # unbillable or billed at its FX rate, which over-charged an INR merchant
    # by about 95x. Refreshes once at startup so a fresh database is billable
    # immediately.
    from app.domains.billing.services import fx_refresher

    fx_task = asyncio.create_task(fx_refresher.run_forever())
    logger.info("✅ FX rate refresher started")

    # Asks Shopify what we have not seen. Data had exactly two routes in — the
    # onboarding backfill and webhooks — so when webhook delivery broke (the
    # subscriptions were pinned to a removed api_version) nothing arrived and
    # nothing noticed for days. The attribution reconciler could not help: it
    # reconciles orders already stored, so it swept correctly and found nothing.
    # A non-empty sweep here is also the webhook-failure alarm.
    from app.domains.shopify.services import ingestion_backstop

    backstop_task = asyncio.create_task(ingestion_backstop.run_forever())
    logger.info("✅ Ingestion backstop started")

    yield

    # Shutdown

    for task in (sweeper_task, reconciler_task, rollover_task, fx_task, backstop_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Stop Kafka consumers first
    if kafka_consumer_manager:
        await kafka_consumer_manager.stop_all_consumers()

    # Close topic manager
    from app.core.kafka.topic_manager import topic_manager

    await topic_manager.close()

    await cleanup_services()

    # Graceful shutdown of OTel providers
    if _otel_provider is not None and hasattr(_otel_provider, "shutdown"):
        _otel_provider.shutdown()
        logger.info("✅ OpenTelemetry logging provider shut down")

    if _metrics_provider is not None and hasattr(_metrics_provider, "shutdown"):
        _metrics_provider.shutdown()
        logger.info("✅ OpenTelemetry metrics provider shut down")

    if _tracer_provider is not None and hasattr(_tracer_provider, "shutdown"):
        _tracer_provider.shutdown()
        logger.info("✅ OpenTelemetry tracing provider shut down")


# Create FastAPI app
app = FastAPI(
    title="BetterBundle Python Worker",
    description="AI-powered Shopify analytics and ML platform",
    version="1.0.0",
    lifespan=lifespan,
)

# OpenTelemetry instrumentation for FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)

# Include API routers
app.include_router(recommendations_router)
app.include_router(edges_status_router)
# Incrementality. Serves a real measured lift, or an explicit reason there
# isn't one — replacing a dashboard that reported a literal p-value of 0.01
# and a confidence interval of revenue ± 10%.
app.include_router(impact_router)
app.include_router(billing_api_router)
app.include_router(auth_router)
app.include_router(outcome_router)
# Recovery path for orders that reached us by backfill rather than webhook.
# Normalisation only publishes an attribution job for webhook-delivered orders
# (so importing pre-install history cannot bill the merchant), which means an
# order whose webhook was never delivered is otherwise never attributed. This
# router was written for exactly that and had never been mounted.
app.include_router(attribution_backfill_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# No metrics middleware.
#
# opentelemetry-instrumentation-fastapi already records every request as
# `http.server.request.duration` (a histogram, so count comes free from its
# _count series) plus `http.server.active_requests` and the request/response
# size histograms — with semconv-correct attributes including `http.route`, the
# TEMPLATED path. The middleware here recorded the same requests a second time
# under `http.requests.total` / `http.requests.duration`, and used
# `request.url.path`, the RAW path: every product id became its own attribute
# value, so the series count grew without bound as traffic grew. Two names for
# one measurement, and the hand-rolled one was the cardinality bomb.


# Global service instances
services = {}

# Kafka Consumer Manager (global instance)
kafka_consumer_manager = None


async def initialize_services():
    """Initialize only essential services at startup"""
    try:
        logger.info("Starting service initialization...")

        # Instrument the outbound clients.
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        HTTPXClientInstrumentor().instrument()
        RedisInstrumentor().instrument()

        # SQLAlchemy was in requirements.txt but was never instrumented, which
        # is why there was no database signal of any kind — the hand-written
        # `db.query.duration` metric it was presumably meant to pair with had no
        # callers either. This emits a span per statement, carrying the SQL and
        # the table, so a slow endpoint can be traced down to the query.
        #
        # `enable_commenter` off deliberately: it appends the trace id as a SQL
        # comment, which defeats prepared-statement caching in pgbouncer and
        # shows up as a different query text per request in pg_stat_statements.
        from app.core.database.engine import get_engine as _engine_for_otel

        # Process-level saturation. The config is explicit and short on purpose:
        # the default set emits around forty streams covering every filesystem,
        # NIC and CPU state on the box, which is precisely the unreadable metric
        # list this work set out to fix. These four answer "is the worker itself
        # the bottleneck", which is the only question the box can answer that
        # the request metrics cannot.
        #
        # Guarded, and the guard is load-bearing: this is the only optional
        # package in the list. An image built before it was added to
        # requirements.txt raises ImportError here, and an unguarded import
        # takes the whole service down at startup over a metric. Telemetry is
        # never worth refusing to serve traffic for.
        try:
            from opentelemetry.instrumentation.system_metrics import (
                SystemMetricsInstrumentor,
            )

            SystemMetricsInstrumentor(
                config={
                    "process.runtime.cpu.utilization": None,
                    "process.runtime.memory": ["rss"],
                    "process.runtime.thread_count": None,
                    "process.runtime.gc_count": None,
                }
            ).instrument()
        except ImportError:
            logger.warning(
                "opentelemetry-instrumentation-system-metrics not installed; "
                "process CPU/memory metrics unavailable. Rebuild the image."
            )

        SQLAlchemyInstrumentor().instrument(
            engine=(await _engine_for_otel()).sync_engine,
            enable_commenter=False,
        )
        logger.info("✅ OpenTelemetry instrumentations applied")

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
        from app.core.redis_client import check_redis_health

        try:
            redis_healthy = await check_redis_health()
            if redis_healthy:
                logger.info("✅ Redis connection verified")
            else:
                logger.warning("⚠️ Redis connection check failed")
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

        # Bring the schema up to date. Replaces the previous create_all() call:
        # that created missing tables but silently ignored any change to an
        # existing one, so column additions never reached the database.
        from app.core.database.migrations import upgrade_to_head

        if not await upgrade_to_head():
            raise RuntimeError(
                "Database migrations failed - refusing to start against an "
                "unknown schema. See the logged traceback."
            )

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
    from app.core.redis_client import check_redis_health

    is_healthy = await check_redis_health()

    if is_healthy:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "redis": {
                    "is_healthy": True,
                },
            },
        )
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "redis": {
                    "is_healthy": False,
                },
            },
        )


# Generic Kafka Event Endpoints
@app.post("/api/kafka/events/publish")
async def publish_kafka_event(
    request: Request,
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



