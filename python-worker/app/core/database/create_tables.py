"""
Create all database tables from SQLAlchemy models
"""

import asyncio
from sqlalchemy import text
from app.core.database.engine import get_engine
from app.core.database.models import Base
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_all_tables():
    """Create all tables defined in SQLAlchemy models"""
    try:
        engine = await get_engine()

        # Create tables one at a time without a wrapping transaction so that
        # a failure on one table/index doesn't abort the entire batch.
        # This is needed because after a hot-reload restart, indexes may already
        # exist from the first run, causing DuplicateTableError.
        async with engine.connect() as conn:
            for table in Base.metadata.sorted_tables:
                try:
                    await conn.run_sync(Base.metadata.create_all, tables=[table])
                    await conn.commit()
                except Exception as e:
                    error_msg = str(e).lower()
                    if "already exists" in error_msg:
                        # Table/index already exists — expected on restart
                        await conn.rollback()
                    else:
                        # Real error — log but don't block other tables
                        logger.warning(f"⚠️ Could not create table {table.name}: {e}")
                        await conn.rollback()

        logger.info("✅ Database tables verified/created")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        return False


async def drop_all_tables():
    """Drop all tables (use with caution!)"""
    try:
        engine = await get_engine()

        async with engine.begin() as conn:
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)

        return True

    except Exception as e:
        logger.error(f"❌ Failed to drop tables: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        print("🗑️ Dropping all tables...")
        asyncio.run(drop_all_tables())
    else:
        print("🏗️ Creating all tables...")
        asyncio.run(create_all_tables())
