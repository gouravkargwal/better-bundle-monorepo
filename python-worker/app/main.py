"""
Main FastAPI application for Python Worker
"""

import asyncio
import multiprocessing
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import get_database, close_database
from app.core.redis_client import get_redis_client, close_redis_client
from app.api.v1 import data_jobs, health, scheduler, gorse

# Setup logging
from app.core.logger import get_logger

logger = get_logger(__name__)

# Global consumer process
_consumer_process = None


def start_consumer_process():
    """Start the Redis consumer in a separate process"""
    global _consumer_process

    if _consumer_process and _consumer_process.is_alive():
        logger.warning("Consumer process is already running")
        return

    try:
        from app.services.data_processor import data_processor
        from app.services.ml_training_consumer import ml_training_consumer

        # Start consumer in separate process
        _consumer_process = multiprocessing.Process(
            target=run_consumer_worker, name="redis-consumer-worker", daemon=True
        )
        _consumer_process.start()

        logger.info(f"Consumer process started with PID: {_consumer_process.pid}")

    except Exception as e:
        logger.error(f"Failed to start consumer process: {e}")
        raise


def run_consumer_worker():
    """Run the consumer in a separate process"""
    try:
        import asyncio
        from app.services.data_processor import data_processor
        from app.services.ml_training_consumer import ml_training_consumer

        # Setup logging for the worker process
        from app.core.logger import get_logger

        worker_logger = get_logger("consumer-worker")
        worker_logger.info("Starting consumer worker process")

        # Run both consumers
        async def run_consumers():
            # Start both consumers
            await data_processor.initialize()
            await ml_training_consumer.initialize()

            # Start consumer tasks
            await data_processor.start_consumer()
            await ml_training_consumer.start_consumer()

            # Wait for both to complete (they run indefinitely)
            await asyncio.gather(
                data_processor._consumer_task,
                ml_training_consumer._consumer_task,
                return_exceptions=True,
            )

        asyncio.run(run_consumers())

    except KeyboardInterrupt:
        worker_logger.info("Consumer worker interrupted")
    except Exception as e:
        worker_logger.error(f"Consumer worker error: {e}")
        sys.exit(1)


def stop_consumer_process():
    """Stop the Redis consumer process"""
    global _consumer_process

    if _consumer_process and _consumer_process.is_alive():
        logger.info(f"Stopping consumer process (PID: {_consumer_process.pid})")
        _consumer_process.terminate()
        _consumer_process.join(timeout=5)

        if _consumer_process.is_alive():
            logger.warning("Consumer process didn't terminate gracefully, forcing kill")
            _consumer_process.kill()
            _consumer_process.join()

        _consumer_process = None
        logger.info("Consumer process stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    stop_consumer_process()
    sys.exit(0)


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

    # Start Redis stream consumer in separate process
    start_consumer_process()
    logger.info("Redis stream consumer started in separate process")

    yield

    # Shutdown
    logger.info("Shutting down Python Worker application")

    # Stop consumer process
    stop_consumer_process()

    await close_database()
    await close_redis_client()
    logger.info("Application shutdown complete")


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
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

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(data_jobs.router, prefix="/api/v1", tags=["data-jobs"])
app.include_router(scheduler.router, prefix="/api/v1", tags=["scheduler"])
app.include_router(gorse.router, prefix="/api/v1", tags=["gorse"])


@app.get("/")
async def root():
    return {"message": "BetterBundle Python Worker", "version": settings.VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
