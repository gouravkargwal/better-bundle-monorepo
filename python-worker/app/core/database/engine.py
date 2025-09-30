"""
SQLAlchemy async engine configuration for BetterBundle Python Worker

Industry-standard async database engine with:
- Connection pooling
- Health monitoring
- Retry logic
- Proper lifecycle management
"""

import asyncio
import time
from typing import Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy import event
from sqlalchemy.exc import DisconnectionError, OperationalError

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine instance
_engine: Optional[AsyncEngine] = None
_engine_lock = asyncio.Lock()
_last_health_check = 0
_connection_attempts = 0


def get_database_url() -> str:
    """Get the database URL with proper async driver"""
    database_url = settings.database.DATABASE_URL

    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("mysql://"):
        database_url = database_url.replace("mysql://", "mysql+aiomysql://", 1)
    elif database_url.startswith("sqlite://"):
        database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    return database_url


def create_engine() -> AsyncEngine:
    """Create SQLAlchemy async engine with optimized configuration"""

    database_url = get_database_url()

    # Debug: log the resolved DB target without secrets
    try:
        url_obj = make_url(database_url)
        safe_url = url_obj.set(password="***")
    except Exception:
        # Avoid failing on logging; continue silently
        pass

    # Engine configuration optimized for async operations
    engine_kwargs = {
        "url": database_url,
        "echo": settings.database.SQLALCHEMY_ECHO,  # Log SQL queries when enabled
        "echo_pool": settings.database.SQLALCHEMY_ECHO_POOL,  # Log pool events when enabled
        "poolclass": NullPool,  # Use NullPool for async engines
        # Note: NullPool doesn't support pool_size, max_overflow, pool_timeout
        "connect_args": (
            {
                "command_timeout": settings.DATABASE_QUERY_TIMEOUT,
                "server_settings": {
                    "application_name": "betterbundle-python-worker",
                    "tcp_keepalives_idle": "600",
                    "tcp_keepalives_interval": "30",
                    "tcp_keepalives_count": "3",
                },
            }
            if "postgresql" in database_url
            else {}
        ),
    }

    # Note: For asyncpg, SSL should be configured via the DATABASE_URL (e.g., ?ssl=require)
    # or using the "ssl" connect_arg with an SSLContext. We avoid injecting unsupported
    # parameters like "sslmode" here to keep compatibility across drivers.

    engine = create_async_engine(**engine_kwargs)

    # Add event listeners for connection monitoring
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite pragmas for better performance"""
        if "sqlite" in database_url:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

    @event.listens_for(engine.sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Log connection checkout for monitoring"""
        logger.debug("Database connection checked out")

    @event.listens_for(engine.sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Log connection checkin for monitoring"""
        logger.debug("Database connection checked in")

    return engine


async def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine with connection management.

    Features:
    - Singleton pattern for engine reuse
    - Health monitoring with automatic reconnection
    - Connection pool management
    - Circuit breaker pattern for failures
    """
    global _engine, _last_health_check, _connection_attempts

    # Check if we need to refresh engine (every 5 minutes)
    current_time = time.time()
    if (
        _engine
        and (current_time - _last_health_check)
        < settings.DATABASE_HEALTH_CHECK_INTERVAL
    ):
        return _engine

    if _engine is None:
        async with _engine_lock:
            # Double-check pattern to avoid race conditions
            if _engine is None:
                await _create_engine()

    # Health check with improved error handling
    if _engine:
        try:
            # Quick health check with shorter timeout
            await asyncio.wait_for(
                _health_check_engine(_engine),
                timeout=5,  # Short timeout for health check
            )
            _last_health_check = current_time
            _connection_attempts = 0  # Reset on successful connection
            return _engine
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Database engine health check failed: {e}")
            await _cleanup_engine()
            return await get_engine()  # Retry with new engine

    return _engine


async def _create_engine():
    """Create a new database engine with retry logic"""
    global _engine, _connection_attempts

    max_attempts = 3
    base_delay = 1.0

    for attempt in range(max_attempts):
        try:

            # Create engine
            _engine = create_engine()

            # Test connection immediately
            await asyncio.wait_for(
                _health_check_engine(_engine),
                timeout=settings.DATABASE_CONNECT_TIMEOUT,
            )

            _connection_attempts = 0
            return

        except asyncio.TimeoutError:
            logger.error(f"Database engine creation timeout (attempt {attempt + 1})")
            await _cleanup_engine()

        except Exception as e:
            logger.error(
                f"Database engine creation failed (attempt {attempt + 1}): {e}"
            )
            await _cleanup_engine()

        # Exponential backoff
        if attempt < max_attempts - 1:
            delay = base_delay * (2**attempt)
            await asyncio.sleep(delay)

    # All attempts failed
    _connection_attempts += 1
    if _connection_attempts >= 5:
        logger.error(
            "Database engine creation failed after multiple attempts. Circuit breaker activated."
        )
        raise Exception("Database engine creation failed after multiple attempts")

    raise Exception("Failed to create database engine")


async def _health_check_engine(engine: AsyncEngine) -> bool:
    """Perform a health check on the engine"""
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.debug(f"Engine health check failed: {e}")
        return False


async def _cleanup_engine():
    """Clean up database engine"""
    global _engine

    if _engine:
        try:
            await _engine.dispose()
        except Exception as e:
            logger.warning(f"Error disposing engine: {e}")
        finally:
            _engine = None


async def close_engine() -> None:
    """Close the database engine with proper cleanup"""
    global _engine, _last_health_check, _connection_attempts

    await _cleanup_engine()
    _last_health_check = 0
    _connection_attempts = 0


async def check_engine_health() -> bool:
    """Check if the database engine is healthy"""
    try:
        engine = await get_engine()
        if not engine:
            return False

        # Quick health check with short timeout
        await asyncio.wait_for(
            _health_check_engine(engine), timeout=5  # Short timeout for health check
        )
        return True
    except Exception as e:
        logger.warning(f"Database engine health check failed: {e}")
        return False


@asynccontextmanager
async def get_engine_context():
    """Context manager for database engine with automatic cleanup"""
    engine = await get_engine()
    try:
        yield engine
    finally:
        # Engine is managed globally, so we don't dispose it here
        pass


# Backward compatibility functions
async def get_database():
    """Backward compatibility function - returns engine instead of Prisma client"""
    return await get_engine()


async def close_database():
    """Backward compatibility function - closes engine"""
    await close_engine()


async def check_database_health():
    """Backward compatibility function - checks engine health"""
    return await check_engine_health()
