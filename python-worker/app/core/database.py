"""
Database connection and utilities using Prisma Python
"""

import asyncio
from typing import Optional
from prisma import Prisma
from prisma.errors import PrismaError

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Global database instance
_db_instance: Optional[Prisma] = None


async def get_database() -> Prisma:
    """Get or create database connection with retry logic"""
    global _db_instance

    if _db_instance is None:
        logger.info("Initializing database connection")
        _db_instance = Prisma()

        try:
            start_time = asyncio.get_event_loop().time()
            await _db_instance.connect()
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            logger.info(f"Database connection established in {duration_ms:.2f}ms")
            logger.info("Database connection established successfully")

        except PrismaError as e:
            logger.error(f"Database connection failed: {e}")
            raise Exception(f"Failed to connect to database: {str(e)}")

    # Check if connection is still alive
    try:
        # Test connection with a simple query
        await _db_instance.query_raw("SELECT 1")
    except Exception:
        logger.warning("Database connection lost, reconnecting...")
        try:
            await _db_instance.disconnect()
        except Exception:
            pass

        _db_instance = None
        return await get_database()  # Recursive call to reconnect

    return _db_instance


async def close_database() -> None:
    """Close database connection"""
    global _db_instance

    if _db_instance:
        logger.info("Closing database connection")
        try:
            await _db_instance.disconnect()
            _db_instance = None
            logger.info("Database connection closed successfully")
        except Exception as e:
            logger.error(f"Database disconnection failed: {e}")


async def check_database_health() -> bool:
    """Check database connection health"""
    try:
        db = await get_database()
        # Simple query to test connection
        await db.query_raw("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def reconnect_database() -> bool:
    """Reconnect to database with retry logic"""
    global _db_instance

    try:
        # Close existing connection
        if _db_instance:
            await _db_instance.disconnect()
            _db_instance = None

        # Wait before reconnecting
        await asyncio.sleep(1)

        # Create new connection
        await get_database()

        # Test connection
        if await check_database_health():
            logger.info("Database reconnection successful")
            return True
        else:
            logger.error("Database reconnection failed - health check failed")
            return False

    except Exception as e:
        logger.error(f"Database reconnection failed: {e}")
        return False


async def with_database_retry(operation, operation_name: str, context: dict = None):
    """Execute database operation with retry logic"""
    max_retries = settings.MAX_RETRIES
    retry_delay = settings.RETRY_DELAY

    for attempt in range(max_retries + 1):
        try:
            result = await operation()
            return result

        except PrismaError as e:
            # Check if it's a connection error
            if "connection" in str(e).lower() and attempt < max_retries:
                logger.warning(
                    f"Database connection error on attempt {attempt + 1}, retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

                # Try to reconnect
                if await reconnect_database():
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
            logger.error(
                f"Database operation {operation_name} failed on attempt {attempt + 1}: {e}",
                operation=operation_name,
                attempt=attempt + 1,
                context=context,
            )
            raise


# Database operation utilities
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
                logger.info(
                    "Updating existing shop access token",
                    shop_id=shop.id,
                    shop_domain=shop_domain,
                )
                shop = await db.shop.update(
                    where={"id": shop.id},
                    data={
                        "accessToken": access_token,
                        "isActive": True,
                    },
                )
            else:
                # Create new shop record
                logger.info(
                    "Creating new shop record", shop_id=shop_id, shop_domain=shop_domain
                )
                shop = await db.shop.create(
                    data={
                        "shopDomain": shop_domain,
                        "accessToken": access_token,
                        "planType": "Free",
                        "isActive": True,
                    }
                )
                logger.info("Shop record created successfully", shop_id=shop.id)
        else:
            # Update access token if it changed
            if shop.accessToken != access_token:
                logger.info("Updating shop access token", shop_id=shop.id)
                shop = await db.shop.update(
                    where={"id": shop.id}, data={"accessToken": access_token}
                )
            else:
                logger.info("Using existing shop record", shop_id=shop.id)

        return shop

    return await with_database_retry(
        operation, "get_or_create_shop", {"shop_id": shop_id}
    )


async def clear_shop_data(shop_db_id: str):
    """Clear existing data for a shop"""
    db = await get_database()

    async def operation():
        logger.info("Clearing existing data", shop_db_id=shop_db_id)

        # Delete in parallel for better performance
        await asyncio.gather(
            db.orderdata.delete_many(where={"shopId": shop_db_id}),
            db.productdata.delete_many(where={"shopId": shop_db_id}),
            db.customerdata.delete_many(where={"shopId": shop_db_id}),
        )

        logger.info("Data cleanup completed", shop_db_id=shop_db_id)

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
        logger.info("Updated shop last analysis timestamp", shop_db_id=shop_db_id)

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
