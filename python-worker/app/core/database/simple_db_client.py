"""
Improved database client for BetterBundle Python Worker

Industry-standard database client with proper connection management,
retry logic, and health monitoring.
"""

import asyncio
import time
from typing import Optional
from prisma import Prisma
from prisma.errors import PrismaError

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global database instance with connection tracking
_db_instance: Optional[Prisma] = None
_connection_lock = asyncio.Lock()
_last_health_check = 0
_connection_attempts = 0


async def get_database() -> Prisma:
    """
    Get or create a database connection with improved error handling and retry logic.

    Industry-standard approach with:
    - Connection health monitoring
    - Exponential backoff retry
    - Proper connection lifecycle management
    - Circuit breaker pattern
    """
    global _db_instance, _last_health_check, _connection_attempts

    # Check if we need to refresh connection (every 5 minutes)
    current_time = time.time()
    if _db_instance and (current_time - _last_health_check) < 300:  # 5 minutes
        return _db_instance

    if _db_instance is None:
        async with _connection_lock:
            # Double-check pattern to avoid race conditions
            if _db_instance is None:
                await _create_connection()

    # Health check with improved error handling
    if _db_instance:
        try:
            # Quick health check with shorter timeout
            await asyncio.wait_for(
                _db_instance.query_raw("SELECT 1"),
                timeout=5,  # Short timeout for health check
            )
            _last_health_check = current_time
            _connection_attempts = 0  # Reset on successful connection
            return _db_instance
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Database health check failed: {e}")
            await _cleanup_connection()
            return await get_database()  # Retry with new connection

    return _db_instance


async def _create_connection():
    """Create a new database connection with retry logic"""
    global _db_instance, _connection_attempts

    max_attempts = 3
    base_delay = 1.0

    for attempt in range(max_attempts):
        try:
            logger.info(
                f"Creating database connection (attempt {attempt + 1}/{max_attempts})"
            )

            # Create Prisma instance
            _db_instance = Prisma()

            # Connect with timeout
            await asyncio.wait_for(
                _db_instance.connect(),
                timeout=settings.DATABASE_CONNECT_TIMEOUT,
            )

            # Test connection immediately
            await asyncio.wait_for(_db_instance.query_raw("SELECT 1"), timeout=5)

            logger.info("Database connection established successfully")
            _connection_attempts = 0
            return

        except asyncio.TimeoutError:
            logger.error(f"Database connection timeout (attempt {attempt + 1})")
            await _cleanup_connection()

        except PrismaError as e:
            logger.error(f"Database connection failed (attempt {attempt + 1}): {e}")
            await _cleanup_connection()

        except Exception as e:
            logger.error(f"Unexpected database error (attempt {attempt + 1}): {e}")
            await _cleanup_connection()

        # Exponential backoff
        if attempt < max_attempts - 1:
            delay = base_delay * (2**attempt)
            logger.info(f"Retrying database connection in {delay} seconds...")
            await asyncio.sleep(delay)

    # All attempts failed
    _connection_attempts += 1
    if _connection_attempts >= 5:
        logger.error(
            "Database connection failed after multiple attempts. Circuit breaker activated."
        )
        raise Exception("Database connection failed after multiple attempts")

    raise Exception("Failed to establish database connection")


async def _cleanup_connection():
    """Clean up database connection"""
    global _db_instance

    if _db_instance:
        try:
            await _db_instance.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting database: {e}")
        finally:
            _db_instance = None


async def close_database() -> None:
    """Close the database connection with proper cleanup"""
    global _db_instance, _last_health_check, _connection_attempts

    await _cleanup_connection()
    _last_health_check = 0
    _connection_attempts = 0
    logger.info("Database connection closed and cleaned up")


async def check_database_health() -> bool:
    """Check if the database connection is healthy with improved error handling"""
    try:
        db = await get_database()
        if not db:
            return False

        # Quick health check with short timeout
        await asyncio.wait_for(
            db.query_raw("SELECT 1"), timeout=5  # Short timeout for health check
        )
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


async def with_database_retry(operation, operation_name: str, context: dict = None):
    """
    Execute database operation with retry logic.

    This provides the same retry functionality as the original database.py
    but works with the simplified client.
    """
    global _db_instance
    max_retries = settings.MAX_RETRIES
    retry_delay = settings.RETRY_DELAY

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

                # Reset connection and retry
                if _db_instance:
                    try:
                        await _db_instance.disconnect()
                    except Exception:
                        pass
                    _db_instance = None

                await asyncio.sleep(retry_delay * (settings.RETRY_BACKOFF**attempt))
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

        except PrismaError as e:
            # Check if it's a connection or timeout error
            error_str = str(e).lower()
            is_retryable_error = (
                "connection" in error_str
                or "timeout" in error_str
                or "pool" in error_str
                or "readtimeout" in error_str
            )

            if is_retryable_error and attempt < max_retries:
                logger.warning(
                    f"Database error on attempt {attempt + 1}, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    error_type=type(e).__name__,
                )

                # Reset connection and retry
                if _db_instance:
                    try:
                        await _db_instance.disconnect()
                    except Exception:
                        pass
                    _db_instance = None

                await asyncio.sleep(retry_delay * (settings.RETRY_BACKOFF**attempt))
                continue

            # Log error and re-raise
            logger.error(
                f"Database operation {operation_name} failed on attempt {attempt + 1}: {e}",
                operation=operation_name,
                attempt=attempt + 1,
                context=context,
            )
            raise

        except Exception as e:
            # Check if it's an httpx timeout error (which Prisma uses internally)
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

                # Reset connection and retry
                if _db_instance:
                    try:
                        await _db_instance.disconnect()
                    except Exception:
                        pass
                    _db_instance = None

                await asyncio.sleep(retry_delay * (settings.RETRY_BACKOFF**attempt))
                continue

            logger.error(
                f"Database operation {operation_name} failed on attempt {attempt + 1}: {e}",
                operation=operation_name,
                attempt=attempt + 1,
                context=context,
            )
            raise


# Database operation utilities (moved from database.py for compatibility)
async def get_or_create_shop(shop_id: str, shop_domain: str, access_token: str):
    """Get or create shop record"""
    db = await get_database()

    async def operation():
        # Try to find existing shop by id first (assuming shop_id is the database id)
        shop = await db.shop.find_unique(where={"id": shop_id})

        if not shop:
            # Try to find by shopDomain as fallback
            shop = await db.shop.find_unique(where={"shopDomain": shop_domain})

            if shop:
                # Update existing shop with new accessToken
                shop = await db.shop.update(
                    where={"id": shop.id},
                    data={
                        "accessToken": access_token,
                        "isActive": True,
                    },
                )
            else:
                # Create new shop record
                shop = await db.shop.create(
                    data={
                        "shopDomain": shop_domain,
                        "accessToken": access_token,
                        "planType": "Free",
                        "isActive": True,
                    }
                )
        else:
            # Update access token if it changed
            if shop.accessToken != access_token:
                shop = await db.shop.update(
                    where={"id": shop.id}, data={"accessToken": access_token}
                )

        return shop

    return await with_database_retry(
        operation, "get_or_create_shop", {"shop_id": shop_id}
    )


async def clear_shop_data(shop_db_id: str):
    """Clear existing data for a shop"""
    db = await get_database()

    async def operation():
        # Delete in parallel for better performance
        await asyncio.gather(
            db.orderdata.delete_many(where={"shopId": shop_db_id}),
            db.productdata.delete_many(where={"shopId": shop_db_id}),
            db.customerdata.delete_many(where={"shopId": shop_db_id}),
        )

    return await with_database_retry(
        operation, "clear_shop_data", {"shop_db_id": shop_db_id}
    )


async def update_shop_last_analysis(shop_db_id: str):
    """Update shop's last analysis timestamp"""
    db = await get_database()

    async def operation():
        await db.shop.update(
            where={"id": shop_db_id},
            data={"lastAnalysisAt": asyncio.get_event_loop().time()},
        )

    return await with_database_retry(
        operation, "update_shop_last_analysis", {"shop_db_id": shop_db_id}
    )


async def get_latest_timestamps(shop_db_id: str):
    """Get the latest timestamps from database for a shop"""
    db = await get_database()

    async def operation():
        # Use raw query for better performance
        result = await db.query_raw(
            """
            SELECT 
                MAX(o."orderDate") as latest_order_date,
                MAX(p."updatedAt") as latest_product_date
            FROM "OrderData" o
            FULL OUTER JOIN "ProductData" p ON o."shopId" = p."shopId"
            WHERE o."shopId" = $1 OR p."shopId" = $1
            """,
            shop_db_id,
        )

        if result:
            return {
                "latest_order_date": result[0].get("latest_order_date"),
                "latest_product_date": result[0].get("latest_product_date"),
            }

        return {"latest_order_date": None, "latest_product_date": None}

    return await with_database_retry(
        operation, "get_latest_timestamps", {"shop_db_id": shop_db_id}
    )
