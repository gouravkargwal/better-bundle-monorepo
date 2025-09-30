"""
SQLAlchemy async session management for BetterBundle Python Worker

Industry-standard async session management with:
- Dependency injection
- Automatic transaction management
- Connection pooling
- Retry logic
- Proper cleanup
"""

import asyncio
from typing import AsyncGenerator, Optional, Callable, Any
from contextlib import asynccontextmanager
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import DisconnectionError, OperationalError, IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.logging import get_logger
from .engine import get_engine

logger = get_logger(__name__)

# Global session factory
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_session_factory_lock = asyncio.Lock()


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory"""
    global _session_factory

    if _session_factory is None:
        async with _session_factory_lock:
            if _session_factory is None:
                engine = await get_engine()
                _session_factory = async_sessionmaker(
                    bind=engine,
                    class_=AsyncSession,
                    expire_on_commit=False,  # Keep objects accessible after commit
                    autoflush=True,  # Automatically flush changes
                    autocommit=False,  # Use explicit transactions
                )

    return _session_factory


async def get_session() -> AsyncSession:
    """
    Get a new async database session.

    This creates a new session from the session factory.
    The session should be used within a context manager or properly closed.
    """
    session_factory = await get_session_factory()
    return session_factory()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Usage:
        async with get_session_context() as session:
            # Use session here
            result = await session.execute(query)
    """
    session = await get_session()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def get_transaction_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions with automatic rollback on error.

    Usage:
        async with get_transaction_context() as session:
            # Use session here - transaction will be committed automatically
            result = await session.execute(query)
    """
    session = await get_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        logger.error(f"Database transaction error: {e}")
        logger.error(
            f"Database transaction error details: {type(e).__name__}: {str(e)}"
        )
        await session.rollback()
        raise
    finally:
        await session.close()


async def with_database_retry(
    operation: Callable[[], Any],
    operation_name: str,
    context: dict = None,
    max_retries: int = None,
    retry_delay: float = None,
    backoff_multiplier: float = None,
) -> Any:
    """
    Execute database operation with retry logic.

    This provides the same retry functionality as the original database.py
    but works with SQLAlchemy sessions.
    """
    max_retries = max_retries or settings.MAX_RETRIES
    retry_delay = retry_delay or settings.RETRY_DELAY
    backoff_multiplier = backoff_multiplier or settings.RETRY_BACKOFF

    for attempt in range(max_retries + 1):
        try:
            # Wrap operation with query timeout
            result = await asyncio.wait_for(
                operation(), timeout=settings.DATABASE_QUERY_TIMEOUT
            )
            return result

        except asyncio.TimeoutError as e:
            if attempt < max_retries:
                logger.warning(
                    f"Database operation timeout on attempt {attempt + 1}, retrying",
                    timeout=settings.DATABASE_QUERY_TIMEOUT,
                    operation=operation_name,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

                await asyncio.sleep(retry_delay * (backoff_multiplier**attempt))
                continue
            else:
                logger.error(
                    f"Database operation {operation_name} timed out after {max_retries + 1} attempts",
                    timeout=settings.DATABASE_QUERY_TIMEOUT,
                    context=context,
                )
                raise Exception(
                    f"Database operation timeout after {settings.DATABASE_QUERY_TIMEOUT} seconds"
                )

        except (DisconnectionError, OperationalError) as e:
            # Check if it's a connection or timeout error
            error_str = str(e).lower()
            is_retryable_error = (
                "connection" in error_str
                or "timeout" in error_str
                or "pool" in error_str
                or "readtimeout" in error_str
                or "server has gone away" in error_str
            )

            if is_retryable_error and attempt < max_retries:
                logger.warning(
                    f"Database connection error on attempt {attempt + 1}, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error_type=type(e).__name__,
                )

                await asyncio.sleep(retry_delay * (backoff_multiplier**attempt))
                continue

            # Log error and re-raise
            logger.error(
                f"Database operation {operation_name} failed on attempt {attempt + 1}: {e}",
                operation=operation_name,
                attempt=attempt + 1,
                context=context,
            )
            raise

        except IntegrityError as e:
            # Integrity errors are usually not retryable
            logger.error(
                f"Database integrity error in {operation_name}: {e}",
                operation=operation_name,
                context=context,
            )
            raise

        except Exception as e:
            # Check if it's a timeout-related error
            error_str = str(e).lower()
            is_retryable_error = (
                "readtimeout" in error_str
                or "connecttimeout" in error_str
                or "pooltimeout" in error_str
                or "timeout" in error_str
            )

            if is_retryable_error and attempt < max_retries:
                logger.warning(
                    f"Database timeout error on attempt {attempt + 1}, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error_type=type(e).__name__,
                )

                await asyncio.sleep(retry_delay * (backoff_multiplier**attempt))
                continue

            logger.error(
                f"Database operation {operation_name} failed on attempt {attempt + 1}: {e}",
                operation=operation_name,
                attempt=attempt + 1,
                context=context,
            )
            raise


def database_retry(
    operation_name: str,
    max_retries: int = None,
    retry_delay: float = None,
    backoff_multiplier: float = None,
):
    """
    Decorator for database operations with retry logic.

    Usage:
        @database_retry("get_user")
        async def get_user(user_id: int):
            async with get_session_context() as session:
                # Database operation here
                pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def operation():
                return await func(*args, **kwargs)

            return await with_database_retry(
                operation,
                operation_name,
                max_retries=max_retries,
                retry_delay=retry_delay,
                backoff_multiplier=backoff_multiplier,
            )

        return wrapper

    return decorator


# Backward compatibility functions for existing code
async def get_database():
    """Backward compatibility function - returns session instead of Prisma client"""
    return await get_session()


async def close_database():
    """Backward compatibility function - no-op for sessions"""
    # Sessions are managed per-request, so no global cleanup needed
    pass


async def check_database_health():
    """Backward compatibility function - checks engine health"""
    from .engine import check_engine_health

    return await check_engine_health()
