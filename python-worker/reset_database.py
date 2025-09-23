#!/usr/bin/env python3
"""
Reset database to match SQLAlchemy models
This script will:
1. Drop all existing tables
2. Recreate all tables from SQLAlchemy models
"""

import asyncio
import os
from dotenv import load_dotenv
from app.core.database.engine import get_engine
from app.core.database.models import Base
from app.core.logging import get_logger

load_dotenv()
logger = get_logger(__name__)


async def reset_database():
    """Drop all tables and recreate them from SQLAlchemy models"""
    try:
        engine = await get_engine()

        async with engine.begin() as conn:
            print("🗑️ Dropping all existing tables...")
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)

            print("🏗️ Creating all tables from SQLAlchemy models...")
            # Create all tables from models
            await conn.run_sync(Base.metadata.create_all)

        print("✅ Database reset completed successfully!")
        print(
            "All tables now match SQLAlchemy models with String columns for source/format"
        )
        return True

    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(reset_database())
