"""
Database client for BetterBundle Python Worker
"""

import asyncio
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from prisma import Prisma
from prisma.errors import PrismaError

from app.core.config import settings
from app.core.exceptions import DatabaseConnectionError, DatabaseQueryError
from app.core.logging import get_logger
from .models import DatabaseConnectionConfig, DatabaseHealthStatus, DatabaseMetrics

logger = get_logger(__name__)


class DatabaseClient:
    """Enterprise-grade database client with connection pooling and health monitoring"""

    def __init__(self, config: Optional[DatabaseConnectionConfig] = None):
        self.config = config or DatabaseConnectionConfig(
            url=settings.database.DATABASE_URL
        )
        self._client: Optional[Prisma] = None
        self._connection_time: Optional[float] = None
        self._metrics = DatabaseMetrics(last_reset=time.time())
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish database connection with retry logic"""
        async with self._lock:
            if self._client is not None:
                return

            try:
                logger.info(
                    "Establishing database connection",
                    database_url=self.config.url[:20] + "...",
                )

                self._client = Prisma()
                await self._client.connect()
                self._connection_time = time.time()

                # Test connection
                await self._test_connection()

                logger.info("Database connection established successfully")

            except Exception as e:
                self._metrics.connection_errors += 1
                error_msg = f"Failed to connect to database: {str(e)}"
                logger.error(error_msg, error=str(e), error_type=type(e).__name__)

                raise DatabaseConnectionError(
                    message=error_msg, connection_details=self.config.to_dict(), cause=e
                )

    async def disconnect(self) -> None:
        """Close database connection"""
        async with self._lock:
            if self._client is None:
                return

            try:
                await self._client.disconnect()
                self._client = None
                self._connection_time = None
                logger.info("Database connection closed")

            except Exception as e:
                logger.warning("Error closing database connection", error=str(e))

    async def _test_connection(self) -> None:
        """Test database connection with a simple query"""
        try:
            start_time = time.time()
            await self._client.query_raw("SELECT 1")
            response_time = (time.time() - start_time) * 1000

            self._metrics.total_queries += 1
            self._metrics.successful_queries += 1
            self._metrics.average_response_time_ms = (
                self._metrics.average_response_time_ms
                * (self._metrics.total_queries - 1)
                + response_time
            ) / self._metrics.total_queries

            if response_time > 100:  # Consider queries > 100ms as slow
                self._metrics.slow_queries_count += 1

        except Exception as e:
            self._metrics.total_queries += 1
            self._metrics.failed_queries += 1
            raise DatabaseQueryError(
                message="Connection test failed", query="SELECT 1", cause=e
            )

    async def get_client(self) -> Prisma:
        """Get database client, creating connection if needed"""
        if self._client is None:
            await self.connect()

        # Check if connection is still alive
        try:
            await self._test_connection()
        except Exception:
            logger.warning("Database connection lost, reconnecting...")
            await self.disconnect()
            await self.connect()

        return self._client

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        client = await self.get_client()

        try:
            async with client.tx() as transaction:
                yield transaction
        except Exception as e:
            self._metrics.failed_queries += 1
            raise DatabaseQueryError(message="Transaction failed", cause=e)

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute a raw SQL query with metrics tracking"""
        start_time = time.time()

        try:
            client = await self.get_client()
            result = await client.query_raw(query, params or {})

            response_time = (time.time() - start_time) * 1000
            self._metrics.total_queries += 1
            self._metrics.successful_queries += 1
            self._metrics.average_response_time_ms = (
                self._metrics.average_response_time_ms
                * (self._metrics.total_queries - 1)
                + response_time
            ) / self._metrics.total_queries

            if response_time > 100:
                self._metrics.slow_queries_count += 1
                logger.warning(
                    "Slow query detected",
                    query=query[:100],
                    response_time_ms=response_time,
                )

            return result

        except Exception as e:
            self._metrics.total_queries += 1
            self._metrics.failed_queries += 1

            raise DatabaseQueryError(
                message="Query execution failed", query=query, params=params, cause=e
            )

    def get_metrics(self) -> DatabaseMetrics:
        """Get database performance metrics"""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self._metrics = DatabaseMetrics(last_reset=time.time())
        logger.info("Database metrics reset")


# Global database client instance
_db_client: Optional[DatabaseClient] = None


async def get_database() -> Prisma:
    """Get database client (backward compatibility)"""
    global _db_client

    if _db_client is None:
        _db_client = DatabaseClient()

    return await _db_client.get_client()


async def close_database() -> None:
    """Close database connection (backward compatibility)"""
    global _db_client

    if _db_client:
        await _db_client.disconnect()
        _db_client = None


def get_database_client() -> DatabaseClient:
    """Get the global database client instance"""
    global _db_client

    if _db_client is None:
        _db_client = DatabaseClient()

    return _db_client
