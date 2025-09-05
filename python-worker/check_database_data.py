#!/usr/bin/env python3
"""
Script to check if behavioral events data is being saved to the database
"""

import sys
import asyncio
from datetime import datetime

sys.path.insert(0, ".")
from app.core.database.simple_db_client import get_database


async def check_database_data():
    """Check the database for behavioral events data"""
    print("🔍 Checking database for behavioral events data...\n")

    try:
        db = await get_database()

        # Check RawBehavioralEvents table
        print("📋 RawBehavioralEvents Table:")
        raw_query = """
        SELECT 
            id, 
            "shopId", 
            "receivedAt",
            jsonb_pretty(payload) as payload_preview
        FROM "RawBehavioralEvents" 
        ORDER BY "receivedAt" DESC 
        LIMIT 5
        """

        raw_results = await db.query_raw(raw_query)

        if raw_results:
            print(f"✅ Found {len(raw_results)} recent raw events:")
            for row in raw_results:
                print(f"   - ID: {row['id']}")
                print(f"     Shop: {row['shopId']}")
                print(f"     Received: {row['receivedAt']}")
                print(f"     Payload Preview: {str(row['payload_preview'])[:100]}...")
                print()
        else:
            print("❌ No raw events found in RawBehavioralEvents table")

        # Check BehavioralEvents table
        print("📋 BehavioralEvents Table:")
        main_query = """
        SELECT 
            "eventId", 
            "shopId", 
            "customerId",
            "eventType",
            "occurredAt",
            jsonb_pretty("eventData") as event_data_preview
        FROM "BehavioralEvents" 
        ORDER BY "occurredAt" DESC 
        LIMIT 5
        """

        main_results = await db.query_raw(main_query)

        if main_results:
            print(f"✅ Found {len(main_results)} recent structured events:")
            for row in main_results:
                print(f"   - Event ID: {row['eventId']}")
                print(f"     Shop: {row['shopId']}")
                print(f"     Customer: {row['customerId']}")
                print(f"     Type: {row['eventType']}")
                print(f"     Occurred: {row['occurredAt']}")
                print(f"     Data Preview: {str(row['event_data_preview'])[:100]}...")
                print()
        else:
            print("❌ No structured events found in BehavioralEvents table")

        # Summary counts
        print("📊 Summary:")
        count_raw_result = await db.query_raw(
            'SELECT COUNT(*) as count FROM "RawBehavioralEvents"'
        )
        count_main_result = await db.query_raw(
            'SELECT COUNT(*) as count FROM "BehavioralEvents"'
        )

        count_raw = count_raw_result[0] if count_raw_result else {"count": 0}
        count_main = count_main_result[0] if count_main_result else {"count": 0}

        print(f"   - Total Raw Events: {count_raw['count']}")
        print(f"   - Total Structured Events: {count_main['count']}")

        if count_raw["count"] > 0 and count_main["count"] > 0:
            print("🎉 Data is being saved to both tables successfully!")
        elif count_raw["count"] > 0 and count_main["count"] == 0:
            print(
                "⚠️  Raw events are being saved, but structured events are not. Check the consumer."
            )
        elif count_raw["count"] == 0 and count_main["count"] == 0:
            print(
                "❌ No events found in either table. Check if the webhook endpoint is working."
            )
        else:
            print("⚠️  Unexpected state. Check the logs for errors.")

    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_database_data())
