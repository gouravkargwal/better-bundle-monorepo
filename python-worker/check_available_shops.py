#!/usr/bin/env python3
"""
Script to check what shops are available in the database
"""

import sys
import asyncio

sys.path.insert(0, ".")
from app.core.database.simple_db_client import get_database


async def check_available_shops():
    """Check what shops are available in the database"""
    print("🔍 Checking available shops in the database...\n")

    try:
        db = await get_database()

        # Get all shops
        shops_query = """
        SELECT id, domain, name, "createdAt"
        FROM "Shop" 
        ORDER BY "createdAt" DESC 
        LIMIT 10
        """

        shops = await db.query_raw(shops_query)

        if shops:
            print(f"✅ Found {len(shops)} shops:")
            for shop in shops:
                print(f"   - ID: {shop['id']}")
                print(f"     Domain: {shop['domain']}")
                print(f"     Name: {shop['name']}")
                print(f"     Created: {shop['createdAt']}")
                print()
        else:
            print("❌ No shops found in the database")

    except Exception as e:
        print(f"❌ Error checking shops: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_available_shops())
