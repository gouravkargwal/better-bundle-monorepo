"""
Database health monitoring and reconnection utilities
"""

import asyncio
import time
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from app.shared.helpers import now_utc

from app.core.config.settings import settings
from app.core.exceptions import DatabaseConnectionError
from app.core.logging import get_logger
from .simple_db_client import get_database

logger = get_logger(__name__)


@dataclass
class DatabaseHealthStatus:
    """Database health status information"""

    is_healthy: bool
    connection_count: int
    last_check: str
    response_time_ms: float
    error_message: Optional[str] = None


async def check_database_health() -> DatabaseHealthStatus:
    """Check database connection health with detailed status"""
    start_time = time.time()

    try:
        db = await get_database()

        # Test connection with a simple query
        await db.query_raw("SELECT 1")

        response_time = (time.time() - start_time) * 1000

        return DatabaseHealthStatus(
            is_healthy=True,
            connection_count=1,  # Simplified for single connection
            last_check=now_utc().isoformat(),
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
            last_check=now_utc().isoformat(),
            error_message=str(e),
            response_time_ms=response_time,
        )


async def reconnect_database() -> bool:
    """Reconnect to database with retry logic"""

    try:
        from .simple_db_client import close_database

        # Close existing connection
        await close_database()

        # Wait before reconnecting
        await asyncio.sleep(1)

        # Create new connection
        await get_database()

        # Test connection
        health_status = await check_database_health()

        if health_status.is_healthy:
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

    for attempt in range(max_attempts):
        try:
            health_status = await check_database_health()

            if health_status.is_healthy:
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
