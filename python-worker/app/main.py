"""
Main FastAPI application for Python Worker
"""

import structlog
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import get_database, close_database
from app.core.redis_client import get_redis_client, close_redis_client
from app.api.v1 import data_jobs, health, scheduler, gorse
from app.services.data_processor import data_processor


# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Python Worker application")

    # Initialize database connection
    await get_database()
    logger.info("Database connection initialized")

    # Initialize Redis connection
    await get_redis_client()
    logger.info("Redis connection initialized")

    # Initialize data processor
    await data_processor.initialize()
    logger.info("Data processor initialized")

    # Start Redis stream consumer in background
    consumer_task = asyncio.create_task(
        data_processor.consume_data_jobs(),
        name="redis-stream-consumer"
    )
    logger.info("Redis stream consumer started in background")

    yield

    # Shutdown
    logger.info("Shutting down Python Worker application")
    
    # Cancel consumer task
    if not consumer_task.done():
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        logger.info("Redis stream consumer stopped")
    
    await close_database()
    await close_redis_client()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Python FastAPI Worker for data collection, processing, and ML event streaming",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(
    data_jobs.router,
    prefix="/api/v1/data-jobs",
    tags=["data-jobs"],
)

app.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

app.include_router(
    scheduler.router,
    prefix="/api/v1/scheduler",
    tags=["scheduler"],
)

app.include_router(
    gorse.router,
    prefix="/api/v1/gorse",
    tags=["gorse"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"{settings.PROJECT_NAME} is running",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
