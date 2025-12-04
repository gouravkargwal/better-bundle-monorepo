#!/usr/bin/env python3
"""
Simple Database Reset Script - Drop and Recreate All Tables

Usage:
    python -m app.scripts.reset_all_tables
"""

import asyncio
import sys
from pathlib import Path

# Add the python-worker directory to Python path
python_worker_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(python_worker_dir))

# TODO: Update this with your actual production database URL
DATABASE_URL = (
    "postgresql+asyncpg://postgres:9414318317g@140.245.16.80:5432/betterbundle"
)

# Set the database URL in environment before importing
import os

os.environ["DATABASE_URL"] = DATABASE_URL

# Now import app modules
from app.core.database.engine import get_engine
from app.core.database.models import Base
from sqlalchemy import text

print("=" * 70)
print("🗄️  Database Reset Script")
print("=" * 70)
print(
    f"\n📊 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}"
)

# Ask for confirmation
response = input("\n⚠️  This will DELETE ALL DATA. Continue? (yes/no): ")
if response.lower() not in ["yes", "y"]:
    print("❌ Cancelled.")
    sys.exit(0)


async def drop_all_tables():
    """Drop all tables"""
    try:
        print("\n🗑️  Dropping all tables...")
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("✅ All tables dropped!")
        return True
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        return False


async def create_all_tables():
    """Create all tables"""
    try:
        print("\n🏗️  Creating all tables...")
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ All tables created!")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


async def list_tables():
    """List all tables"""
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
                )
            )
            return [row[0] for row in result]
    except Exception as e:
        print(f"⚠️  Could not list tables: {e}")
        return []


async def main():
    """Main function"""
    # Drop tables
    if not await drop_all_tables():
        sys.exit(1)

    # Create tables
    if not await create_all_tables():
        sys.exit(1)

    # List created tables
    print("\n📋 Created tables:")
    tables = await list_tables()
    for table in tables:
        print(f"   - {table}")

    print("\n" + "=" * 70)
    print("🎯 Done!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
