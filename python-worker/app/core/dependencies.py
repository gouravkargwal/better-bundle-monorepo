"""
Dependency injection functions for BetterBundle Python Worker

This module provides FastAPI-style dependency injection for:
- Database sessions
- Repositories
- Services
- Configuration
"""

from typing import AsyncGenerator, Annotated
from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_session_context, get_transaction_context
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository

logger = get_logger(__name__)


# Database Session Dependencies
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for database sessions.

    Usage:
        async def my_handler(session: AsyncSession = Depends(get_db_session)):
            # Use session here
    """
    async with get_session_context() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for database transactions with automatic commit/rollback.

    Usage:
        async def my_handler(session: AsyncSession = Depends(get_db_transaction)):
            # Use session here - will auto-commit on success, rollback on error
    """
    async with get_transaction_context() as session:
        yield session


# Repository Dependencies
@lru_cache()
def get_shop_repository() -> ShopRepository:
    """
    Dependency for ShopRepository.

    Usage:
        async def my_handler(repo: ShopRepository = Depends(get_shop_repository)):
            # Use repository here
    """
    return ShopRepository()


# Type aliases for better IDE support
DatabaseSession = Annotated[AsyncSession, "Database session dependency"]
DatabaseTransaction = Annotated[AsyncSession, "Database transaction dependency"]
ShopRepo = Annotated[ShopRepository, "Shop repository dependency"]


# Service Dependencies (you can add more as needed)
@lru_cache()
def get_shopify_service():
    """Dependency for Shopify service"""
    from app.domains.shopify.services import ShopifyDataCollectionService

    return ShopifyDataCollectionService()


# Configuration Dependencies
@lru_cache()
def get_kafka_settings():
    """Dependency for Kafka settings"""
    from app.core.config.kafka_settings import kafka_settings

    return kafka_settings


@lru_cache()
def get_app_settings():
    """Dependency for application settings"""
    from app.core.config.settings import settings

    return settings
