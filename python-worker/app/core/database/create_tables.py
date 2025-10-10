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

        # Use begin() for proper transaction management
        async with engine.begin() as conn:
            # Create all tables defined in the models
            # This is safe to run multiple times - it won't recreate existing tables
            await conn.run_sync(Base.metadata.create_all)

        return True

    except Exception as e:
        # Check if it's a duplicate index/table error (which is OK)
        error_msg = str(e).lower()
        if any(
            keyword in error_msg
            for keyword in ["already exists", "duplicate", "relation"]
        ):
            return True
        else:
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
