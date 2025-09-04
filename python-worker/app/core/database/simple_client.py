"""
Simple database client that uses the connection pool
"""

from typing import Optional
from prisma import Prisma
from app.core.database.connection_pool import get_connection_pool
from app.core.logging import get_logger

logger = get_logger(__name__)


class SimpleDatabaseClient:
    """Simple database client that uses the connection pool"""

    def __init__(self):
        self.connection_pool = None
        self._is_initialized = False

    async def initialize(self):
        """Initialize the connection pool"""
        if not self._is_initialized:
            self.connection_pool = await get_connection_pool()
            self._is_initialized = True

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
