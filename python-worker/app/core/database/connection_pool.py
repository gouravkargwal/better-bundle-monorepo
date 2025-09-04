"""
Enterprise-grade database connection pool for BetterBundle Python Worker
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

from prisma import Prisma
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConnectionMetrics:
    """Connection pool metrics"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connection_requests: int = 0
    connection_waits: int = 0
    average_wait_time: float = 0.0
    max_wait_time: float = 0.0
    connection_errors: int = 0
    last_reset: datetime = None


class DatabaseConnectionPool:
    """
    Enterprise-grade connection pool with:
    - Connection reuse and pooling
    - Automatic connection health checks
    - Connection lifecycle management
    - Performance monitoring
    - Graceful degradation
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_connections: int = 2,
        max_connections: int = 10,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,  # 5 minutes
        health_check_interval: float = 60.0,  # 1 minute
    ):
        self.database_url = database_url
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.health_check_interval = health_check_interval

        # Connection pool
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections: Dict[str, Prisma] = {}
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Metrics
        self.metrics = ConnectionMetrics()
        self.metrics.last_reset = datetime.utcnow()

        # Control
        self._is_initialized = False
        self._shutdown_event = asyncio.Event()
        self._health_check_task: Optional[asyncio.Task] = None

        # Locks
        self._pool_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool"""
        if self._is_initialized:
            return

        logger.info(
            f"Initializing database connection pool (min: {self.min_connections}, max: {self.max_connections})"
        )

        try:
            # Create minimum connections
            for _ in range(self.min_connections):
                await self._create_connection()

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            self._is_initialized = True
            logger.info(
                f"Database connection pool initialized with {self.min_connections} connections"
            )

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown the connection pool"""
        if not self._is_initialized:
            return

        logger.info("Shutting down database connection pool...")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._pool_lock:
            # Close idle connections
            while not self._pool.empty():
                try:
                    connection = self._pool.get_nowait()
                    await connection.disconnect()
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.warning(f"Error closing idle connection: {e}")

            # Close active connections
            for connection_id, connection in self._active_connections.items():
                try:
                    await connection.disconnect()
                    logger.debug(f"Closed active connection: {connection_id}")
                except Exception as e:
                    logger.warning(
                        f"Error closing active connection {connection_id}: {e}"
                    )

            self._active_connections.clear()
            self._connection_metadata.clear()

        self._is_initialized = False
        logger.info("Database connection pool shutdown complete")

    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self._is_initialized:
            await self.initialize()

        connection = None
        connection_id = None
        start_time = time.time()

        try:
            # Try to get connection from pool
            try:
                connection = await asyncio.wait_for(
                    self._pool.get(), timeout=self.connection_timeout
                )
                connection_id = id(connection)

                # Mark as active
                self._active_connections[connection_id] = connection
                self.metrics.active_connections = len(self._active_connections)
                self.metrics.idle_connections = self._pool.qsize()

                logger.debug(f"Retrieved connection from pool: {connection_id}")

            except asyncio.TimeoutError:
                # Pool exhausted, create new connection if under limit
                async with self._pool_lock:
                    if len(self._active_connections) < self.max_connections:
                        connection = await self._create_connection()
                        connection_id = id(connection)
                        self._active_connections[connection_id] = connection
                        self.metrics.active_connections = len(self._active_connections)
                        logger.debug(f"Created new connection: {connection_id}")
                    else:
                        self.metrics.connection_waits += 1
                        raise Exception(
                            "Connection pool exhausted and max connections reached"
                        )

            # Update metrics
            wait_time = time.time() - start_time
            self.metrics.connection_requests += 1
            self.metrics.average_wait_time = (
                self.metrics.average_wait_time * (self.metrics.connection_requests - 1)
                + wait_time
            ) / self.metrics.connection_requests
            self.metrics.max_wait_time = max(self.metrics.max_wait_time, wait_time)

            # Update connection metadata
            self._connection_metadata[connection_id] = {
                "created_at": datetime.utcnow(),
                "last_used": datetime.utcnow(),
                "usage_count": self._connection_metadata.get(connection_id, {}).get(
                    "usage_count", 0
                )
                + 1,
            }

            yield connection

        except Exception as e:
            self.metrics.connection_errors += 1
            logger.error(f"Error getting database connection: {e}")
            raise

        finally:
            # Return connection to pool
            if connection and connection_id:
                try:
                    # Update last used time
                    if connection_id in self._connection_metadata:
                        self._connection_metadata[connection_id][
                            "last_used"
                        ] = datetime.utcnow()

                    # Remove from active connections
                    if connection_id in self._active_connections:
                        del self._active_connections[connection_id]
                        self.metrics.active_connections = len(self._active_connections)

                    # Return to pool if not shutting down
                    if not self._shutdown_event.is_set():
                        try:
                            self._pool.put_nowait(connection)
                            self.metrics.idle_connections = self._pool.qsize()
                            logger.debug(
                                f"Returned connection to pool: {connection_id}"
                            )
                        except asyncio.QueueFull:
                            # Pool full, close connection
                            await connection.disconnect()
                            logger.debug(
                                f"Pool full, closed connection: {connection_id}"
                            )

                except Exception as e:
                    logger.warning(f"Error returning connection to pool: {e}")
                    try:
                        await connection.disconnect()
                    except:
                        pass

    async def _create_connection(self) -> Prisma:
        """Create a new database connection"""
        try:
            connection = Prisma()
            await connection.connect()

            # Test connection
            await connection.query_raw("SELECT 1")

            self.metrics.total_connections += 1
            logger.debug(
                f"Created new database connection (total: {self.metrics.total_connections})"
            )

            return connection

        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise

    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on connections"""
        if not self._is_initialized:
            return

        logger.debug("Performing connection health checks...")

        # Check idle connections in pool
        idle_connections = []
        while not self._pool.empty():
            try:
                connection = self._pool.get_nowait()
                if await self._is_connection_healthy(connection):
                    idle_connections.append(connection)
                else:
                    await connection.disconnect()
                    logger.debug("Removed unhealthy idle connection")
            except asyncio.QueueEmpty:
                break

        # Return healthy connections to pool
        for connection in idle_connections:
            try:
                self._pool.put_nowait(connection)
            except asyncio.QueueFull:
                await connection.disconnect()

        # Update metrics
        self.metrics.idle_connections = self._pool.qsize()

        logger.debug(
            f"Health check complete (idle: {self.metrics.idle_connections}, active: {self.metrics.active_connections})"
        )

    async def _is_connection_healthy(self, connection: Prisma) -> bool:
        """Check if a connection is healthy"""
        try:
            await asyncio.wait_for(connection.query_raw("SELECT 1"), timeout=5.0)
            return True
        except Exception as e:
            logger.debug(f"Connection health check failed: {e}")
            return False

    def get_metrics(self) -> ConnectionMetrics:
        """Get connection pool metrics"""
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset connection pool metrics"""
        self.metrics = ConnectionMetrics()
        self.metrics.last_reset = datetime.utcnow()
        logger.info("Connection pool metrics reset")


# Global connection pool instance
_connection_pool: Optional[DatabaseConnectionPool] = None


async def get_connection_pool() -> DatabaseConnectionPool:
    """Get the global database connection pool"""
    global _connection_pool

    if _connection_pool is None:
        from app.core.config import settings

        _connection_pool = DatabaseConnectionPool(
            database_url=settings.database.DATABASE_URL,
            min_connections=2,
            max_connections=10,
        )
        await _connection_pool.initialize()

    return _connection_pool


async def shutdown_connection_pool() -> None:
    """Shutdown the global database connection pool"""
    global _connection_pool

    if _connection_pool is not None:
        await _connection_pool.shutdown()
        _connection_pool = None
