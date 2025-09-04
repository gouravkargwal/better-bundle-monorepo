"""
Simple database client that uses the connection pool
"""

from typing import Optional, List, Dict, Any
from prisma import Prisma
from app.core.database.connection_pool import (
    get_connection_pool,
    DatabaseConnectionPool,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class SimpleDatabaseClient:
    """Simple database client that uses the connection pool"""

    def __init__(self, connection_pool: Optional[DatabaseConnectionPool] = None):
        self.connection_pool = connection_pool
        self._is_initialized = False

    async def initialize(self):
        """Initialize the connection pool"""
        if not self._is_initialized:
            if self.connection_pool is None:
                self.connection_pool = await get_connection_pool()
            self._is_initialized = True

    async def query(self, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        if not self._is_initialized:
            await self.initialize()

        async with self.connection_pool.get_connection() as connection:
            if params:
                result = await connection.query_raw(sql, *params)
            else:
                result = await connection.query_raw(sql)
            return result

    async def execute(self, sql: str, params: List[Any] = None) -> None:
        """Execute an INSERT/UPDATE/DELETE query"""
        if not self._is_initialized:
            await self.initialize()

        async with self.connection_pool.get_connection() as connection:
            if params:
                await connection.execute_raw(sql, *params)
            else:
                await connection.execute_raw(sql)

    async def health_check(self) -> bool:
        """Check if the database connection is healthy"""
        try:
            if not self._is_initialized:
                await self.initialize()

            async with self.connection_pool.get_connection() as connection:
                await connection.query_raw("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self._is_initialized:
            await self.initialize()

        return self.connection_pool.get_connection()

    async def __aenter__(self):
        """Async context manager entry"""
        if not self._is_initialized:
            await self.initialize()

        self._connection = await self.connection_pool.get_connection()
        return self._connection.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if hasattr(self, "_connection"):
            await self._connection.__aexit__(exc_type, exc_val, exc_tb)
