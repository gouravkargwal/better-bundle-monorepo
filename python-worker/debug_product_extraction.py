#!/usr/bin/env python3
"""
Debug script to test product ID extraction from events
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database
from app.domains.ml.generators.interaction_feature_generator import (
    InteractionFeatureGenerator,
)


async def debug_product_extraction():
    """Debug product ID extraction from events"""
    try:
        db = await get_database()

        # Get a sample product_viewed event
        event = await db.userinteraction.find_first(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "interactionType": "product_viewed",
            }
        )

        if not event:
            print("No product_viewed event found")
            return

        print(f"Event: {event.interactionType}")
        print(f"Customer: {event.customerId}")
        print(f"Metadata: {event.metadata}")

        # Test the extraction method
        generator = InteractionFeatureGenerator()

        # Convert Prisma object to dict
        event_dict = {
            "interactionType": event.interactionType,
            "customerId": event.customerId,
            "metadata": event.metadata,
        }

        extracted_id = generator._extract_product_id_from_event(event_dict)
        print(f"Extracted Product ID: {extracted_id}")

        # Test with all product_viewed events
        all_events = await db.userinteraction.find_many(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "interactionType": "product_viewed",
            },
            take=5,
        )

        print(f"\nTesting {len(all_events)} product_viewed events:")
        for i, event in enumerate(all_events):
            event_dict = {
                "interactionType": event.interactionType,
                "customerId": event.customerId,
                "metadata": event.metadata,
            }

            extracted_id = generator._extract_product_id_from_event(event_dict)
            print(f"Event {i+1}: {extracted_id}")

            # Manual extraction to debug
            metadata = event.metadata
            if isinstance(metadata, dict):
                data = metadata.get("data", {})
                product_variant = data.get("productVariant", {})
                product = product_variant.get("product", {})
                manual_id = product.get("id", "")
                print(f"  Manual extraction: {manual_id}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_product_extraction())
