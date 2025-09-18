#!/usr/bin/env python3
"""
Debug script to check product view events specifically
"""
import asyncio
import sys
import os
import json

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_product_views():
    """Debug product view events specifically"""
    try:
        db = await get_database()

        # Get all product_viewed events
        product_views = await db.userinteraction.find_many(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "interactionType": "product_viewed",
            },
            take=10,
        )

        print(f"Product viewed events: {len(product_views)}")

        for i, event in enumerate(product_views):
            print(f"\nEvent {i+1}:")
            print(f"  Customer: {event.customerId}")
            print(f"  Interaction Type: {event.interactionType}")
            print(f"  Event attributes: {dir(event)}")
            print(f"  Metadata: {event.metadata}")

            # Try to extract product ID from metadata
            metadata = event.metadata
            if isinstance(metadata, dict):
                print(f"  Metadata keys: {list(metadata.keys())}")
                if "productId" in metadata:
                    print(f"  Product ID: {metadata['productId']}")
                elif "data" in metadata:
                    data = metadata["data"]
                    if isinstance(data, dict):
                        print(f"  Data keys: {list(data.keys())}")
                        if "productVariant" in data:
                            variant = data["productVariant"]
                            if isinstance(variant, dict) and "product" in variant:
                                product = variant["product"]
                                if isinstance(product, dict) and "id" in product:
                                    print(f"  Product ID from variant: {product['id']}")

        # Check if there are any other event types that might contain product views
        all_events = await db.userinteraction.find_many(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o"}, take=20
        )

        print(f"\nAll events: {len(all_events)}")
        event_types = {}
        for event in all_events:
            event_type = event.interactionType
            if event_type not in event_types:
                event_types[event_type] = 0
            event_types[event_type] += 1

        print("Event types distribution:")
        for event_type, count in event_types.items():
            print(f"  {event_type}: {count}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_product_views())
