#!/usr/bin/env python3
"""
Debug script to understand why specific products have 0 view counts
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


async def debug_specific_product():
    """Debug why specific products have 0 view counts"""
    try:
        db = await get_database()

        # Test with a product that has 0 views but should have views
        product_id = "7903465537675"
        customer_id = "8619514265739"

        print(f"Debugging product {product_id} for customer {customer_id}")

        # Get all behavioral events for this customer
        behavioral_events = await db.userinteraction.find_many(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "customerId": customer_id}
        )

        print(f"Total behavioral events for customer: {len(behavioral_events)}")

        # Convert to dict format
        events_dict = []
        for event in behavioral_events:
            events_dict.append(
                {
                    "interactionType": event.interactionType,
                    "customerId": event.customerId,
                    "metadata": event.metadata,
                }
            )

        # Test the interaction feature generator
        generator = InteractionFeatureGenerator()

        # Test product ID extraction for all events
        print(f"\nTesting product ID extraction:")
        for i, event in enumerate(events_dict):
            extracted_id = generator._extract_product_id_from_event(event)
            if extracted_id == product_id:
                print(
                    f"  Event {i}: {event['interactionType']} -> Product ID: {extracted_id}"
                )

        # Test filtering
        filtered_events = generator._filter_product_events(
            events_dict, customer_id, product_id
        )

        print(f"\nFiltered events for product {product_id}: {len(filtered_events)}")
        for event in filtered_events:
            print(f"  Event: {event['interactionType']}")

        # Test view counting
        view_count = generator._count_product_views(filtered_events)
        print(f"\nView count: {view_count}")

        # Manual check of product_viewed events
        product_viewed_events = [
            e for e in events_dict if e["interactionType"] == "product_viewed"
        ]
        print(f"\nManual check - product_viewed events: {len(product_viewed_events)}")

        for event in product_viewed_events:
            extracted_id = generator._extract_product_id_from_event(event)
            print(f"  Product ID: {extracted_id}")
            if extracted_id == product_id:
                print(f"    -> This should be counted!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_specific_product())
