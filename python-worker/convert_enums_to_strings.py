#!/usr/bin/env python3
"""
Convert enum columns to string columns in the database
This script will:
1. Convert RawSourceType enum columns to VARCHAR
2. Convert RawDataFormat enum columns to VARCHAR
3. Drop the enum types
"""

import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import text
from app.core.database.engine import get_engine

load_dotenv()


async def convert_enums_to_strings():
    """Convert enum columns to string columns"""
    engine = await get_engine()

    async with engine.begin() as conn:
        print("🔄 Starting enum to string conversion...")

        # List of tables that have enum columns
        tables = ["RawOrder", "RawProduct", "RawCustomer", "RawCollection"]

        for table in tables:
            print(f"📝 Converting {table}...")

            # Convert source column from enum to VARCHAR
            await conn.execute(
                text(
                    f"""
                ALTER TABLE "{table}" 
                ALTER COLUMN source TYPE VARCHAR USING source::text
            """
                )
            )

            # Convert format column from enum to VARCHAR
            await conn.execute(
                text(
                    f"""
                ALTER TABLE "{table}" 
                ALTER COLUMN format TYPE VARCHAR USING format::text
            """
                )
            )

            print(f"✅ {table} converted successfully")

        # Drop the enum types (only if no other tables use them)
        print("🗑️ Dropping enum types...")

        try:
            await conn.execute(text('DROP TYPE IF EXISTS "RawSourceType"'))
            print("✅ RawSourceType enum dropped")
        except Exception as e:
            print(f"⚠️ Could not drop RawSourceType: {e}")

        try:
            await conn.execute(text('DROP TYPE IF EXISTS "RawDataFormat"'))
            print("✅ RawDataFormat enum dropped")
        except Exception as e:
            print(f"⚠️ Could not drop RawDataFormat: {e}")

        print("🎉 Database conversion completed successfully!")
        print("\nNext steps:")
        print("1. Update SQLAlchemy models to use String columns")
        print("2. Test database insertion")


if __name__ == "__main__":
    asyncio.run(convert_enums_to_strings())
