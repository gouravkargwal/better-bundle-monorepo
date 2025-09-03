#!/usr/bin/env python3
"""
Database connection test script
"""

import asyncio
import os
import json
from datetime import datetime
from prisma import Prisma


async def test_database_connection():
    """Test database connection and create a test record"""

    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    print(f"Database URL: {database_url}")

    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return

    try:
        # Initialize Prisma client
        db = Prisma()
        await db.connect()
        print("✅ Database connection successful")

        # Test creating a test record in RawOrder table
        test_data = {
            "test": True,
            "message": "Database connection test",
            "timestamp": datetime.now().isoformat(),
        }

        test_order = await db.raworder.create(
            data={"shopId": "test_shop_123", "payload": json.dumps(test_data)}
        )
        print(f"✅ Test record created: {test_order.id}")

        # Verify the record exists
        retrieved_order = await db.raworder.find_unique(where={"id": test_order.id})
        if retrieved_order:
            print(f"✅ Record retrieved successfully: {retrieved_order.shopId}")
            print(f"   Payload: {retrieved_order.payload}")
        else:
            print("❌ Failed to retrieve test record")

        # Clean up test record
        await db.raworder.delete(where={"id": test_order.id})
        print("✅ Test record cleaned up")

        await db.disconnect()
        print("✅ Database connection closed")

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_database_connection())
