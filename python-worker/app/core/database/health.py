"""
Database health monitoring and reconnection utilities
"""

import asyncio
import time
from typing import Optional
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import DatabaseConnectionError
from app.core.logging import get_logger
from .client import get_database_client
from .models import DatabaseHealthStatus

logger = get_logger(__name__)


async def check_database_health() -> DatabaseHealthStatus:
    """Check database connection health with detailed status"""
    start_time = time.time()

    try:
        db_client = get_database_client()
        client = await db_client.get_client()

        # Test connection with a simple query
        await client.query_raw("SELECT 1")

        response_time = (time.time() - start_time) * 1000

        # Get metrics
        metrics = db_client.get_metrics()

        return DatabaseHealthStatus(
            is_healthy=True,
            connection_count=1,  # Simplified for now
            last_check=datetime.now().isoformat(),
            response_time_ms=response_time,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000

        logger.error(
            "Database health check failed", error=str(e), response_time_ms=response_time
        )

        return DatabaseHealthStatus(
            is_healthy=False,
            connection_count=0,
            last_check=datetime.now().isoformat(),
            error_message=str(e),
            response_time_ms=response_time,
        )


async def reconnect_database() -> bool:
    """Reconnect to database with retry logic"""
    logger.info("Attempting database reconnection")

    try:
        db_client = get_database_client()

        # Close existing connection
        await db_client.disconnect()

        # Wait before reconnecting
        await asyncio.sleep(1)

        # Create new connection
        await db_client.connect()

        # Test connection
        health_status = await check_database_health()

        if health_status.is_healthy:
            logger.info("Database reconnection successful")
            return True
        else:
            logger.error("Database reconnection failed - health check failed")
            return False

    except Exception as e:
        logger.error("Database reconnection failed", error=str(e))
        return False


async def wait_for_database_ready(
    max_attempts: int = 30, delay_seconds: float = 2.0
) -> bool:
    """Wait for database to be ready (useful for container startup)"""
    logger.info(
        "Waiting for database to be ready",
        max_attempts=max_attempts,
        delay_seconds=delay_seconds,
    )

    for attempt in range(max_attempts):
        try:
            health_status = await check_database_health()

            if health_status.is_healthy:
                logger.info("Database is ready", attempt=attempt + 1)
                return True

        except Exception as e:
            logger.debug("Database not ready yet", attempt=attempt + 1, error=str(e))

        if attempt < max_attempts - 1:
            await asyncio.sleep(delay_seconds)

    logger.error(
        "Database failed to become ready",
        max_attempts=max_attempts,
        total_wait_time=max_attempts * delay_seconds,
    )
    return False


async def monitor_database_health(interval_seconds: int = 60) -> None:
    """Continuous database health monitoring"""
    logger.info(
        "Starting database health monitoring", interval_seconds=interval_seconds
    )

    while True:
        try:
            health_status = await check_database_health()

            if not health_status.is_healthy:
                logger.warning(
                    "Database health check failed",
                    error=health_status.error_message,
                    response_time_ms=health_status.response_time_ms,
                )

                # Attempt reconnection
                if await reconnect_database():
                    logger.info("Database reconnection successful")
                else:
                    logger.error("Database reconnection failed")

            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logger.error("Error in database health monitoring", error=str(e))
            await asyncio.sleep(interval_seconds)
