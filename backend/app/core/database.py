"""
Database configuration and connection management
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from prisma import Prisma
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global Prisma client instance
prisma_client: Prisma = None


async def get_prisma_client() -> Prisma:
    """Get the Prisma client instance"""
    global prisma_client
    if prisma_client is None:
        prisma_client = Prisma()
        await prisma_client.connect()
        logger.info("Prisma client connected")
    return prisma_client


async def close_prisma_client():
    """Close the Prisma client connection"""
    global prisma_client
    if prisma_client:
        await prisma_client.disconnect()
        prisma_client = None
        logger.info("Prisma client disconnected")


@asynccontextmanager
async def get_db() -> AsyncGenerator[Prisma, None]:
    """Database dependency for FastAPI"""
    client = await get_prisma_client()
    try:
        yield client
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        # Don't close the client here as it's a global instance
        pass


async def health_check() -> bool:
    """Check database health"""
    try:
        client = await get_prisma_client()
        # Simple query to check connection
        await client.shop.find_first(take=1)
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
