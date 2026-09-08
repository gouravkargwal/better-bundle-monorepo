"""
Create all database tables from SQLAlchemy models.

Runs on startup. `create_all` is create-if-not-exists, so it is safe to run
repeatedly — but note it will NEVER alter an existing table. Adding a column to
a model that is already in the database is silently ignored here; that needs a
hand-written migration or a `prisma db pull` round trip.
"""

import asyncio

from sqlalchemy import text

from app.core.database.engine import get_engine
from app.core.database.models import Base
from app.core.logging import get_logger

logger = get_logger(__name__)

# `product_vectors.vector` is a pgvector column, so the type has to exist before
# any table referencing it can be created. The image is pgvector/pgvector:pg17,
# which ships the extension but does not enable it in the database.
REQUIRED_EXTENSIONS = ("vector",)


async def create_all_tables() -> bool:
    """Enable required extensions, then create any missing tables."""
    try:
        engine = await get_engine()

        async with engine.begin() as conn:
            for ext in REQUIRED_EXTENSIONS:
                await conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
                logger.debug(f"Extension ready: {ext}")

            await conn.run_sync(Base.metadata.create_all)

        logger.info(f"✅ {len(Base.metadata.tables)} tables verified/created")
        return True

    except Exception as e:
        # Deliberately narrow.
        #
        # The previous version also swallowed anything containing "relation",
        # which appears in nearly every Postgres error message — including
        # `type "vector" does not exist`. A genuine failure was therefore
        # reported as success and the app carried on with tables missing,
        # failing later at query time with no clue as to why.
        message = str(e).lower()
        benign = ("already exists", "duplicate key", "duplicate table")
        if any(k in message for k in benign):
            logger.info("Tables already present, nothing to create")
            return True

        logger.error(f"❌ Failed to create tables: {e}", exc_info=True)
        return False


async def drop_all_tables() -> bool:
    """Drop all tables. Destroys data — used only by the reset script."""
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        return True
    except Exception as e:
        logger.error(f"❌ Failed to drop tables: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        print("🗑️  Dropping all tables...")
        asyncio.run(drop_all_tables())
    else:
        print("🏗️  Creating all tables...")
        asyncio.run(create_all_tables())
