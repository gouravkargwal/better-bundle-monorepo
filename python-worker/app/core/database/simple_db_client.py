"""
Simplified database client for BetterBundle Python Worker

This client uses a single, long-lived Prisma instance that connects directly
to Neon's built-in connection pooler. This is the optimal pattern for serverless
databases like Neon, eliminating the need for complex connection pooling.
"""

import asyncio
from typing import Optional
from prisma import Prisma
from prisma.errors import PrismaError

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global database instance
_db_instance: Optional[Prisma] = None
_connection_lock = asyncio.Lock()


async def get_database() -> Prisma:
    """
    Get or create a single, long-lived database connection.

    This function ensures we have one Prisma instance that connects directly
    to Neon's built-in connection pooler. Neon handles connection pooling
    at the database level, so we don't need to implement our own.
    """
    global _db_instance

    if _db_instance is None:
        async with _connection_lock:
            # Double-check pattern to avoid race conditions
            if _db_instance is None:
                logger.info("Creating new Prisma database connection")

                # Create Prisma instance (connection pool settings are configured via environment variables)
                _db_instance = Prisma()

                try:
                    await _db_instance.connect()
                    logger.info("Database connection established successfully")
                except PrismaError as e:
                    logger.error(f"Database connection failed: {e}")
                    _db_instance = None
                    raise Exception(f"Failed to connect to database: {str(e)}")

    # Verify connection is still alive
    try:
        await _db_instance.query_raw("SELECT 1")
    except Exception as e:
        logger.warning(f"Database connection lost, reconnecting: {e}")
        try:
            await _db_instance.disconnect()
        except Exception:
            pass

        _db_instance = None
        return await get_database()  # Recursive call to reconnect

    return _db_instance


async def close_database() -> None:
    """Close the database connection"""
    global _db_instance

    if _db_instance:
        try:
            await _db_instance.disconnect()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Database disconnection failed: {e}")
        finally:
            _db_instance = None


async def check_database_health() -> bool:
    """Check if the database connection is healthy"""
    try:
        db = await get_database()
        await db.query_raw("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
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
            result = await operation()
            return result

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
