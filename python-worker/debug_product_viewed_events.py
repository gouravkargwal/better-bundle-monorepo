#!/usr/bin/env python3
"""
Debug script to check product_viewed events specifically
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_product_viewed_events():
    """Debug product_viewed events specifically"""
    try:
        db = await get_database()

        # Get product_viewed events for the customer
        product_viewed_events = await db.userinteraction.find_many(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "customerId": "8619514265739",
                "interactionType": "product_viewed",
            }
        )

        print(f"Found {len(product_viewed_events)} product_viewed events")

        for i, event in enumerate(product_viewed_events):
            print(f"\nEvent {i+1}:")
            print(f"  Customer: {event.customerId}")
            print(f"  Type: {event.interactionType}")

            # Extract product ID manually
            metadata = event.metadata
            if isinstance(metadata, dict):
                data = metadata.get("data", {})
                product_variant = data.get("productVariant", {})
                product = product_variant.get("product", {})
                product_id = product.get("id", "")
                print(f"  Product ID: {product_id}")

        # Test the feature engineering service extraction
        from app.domains.ml.services.feature_engineering import (
            FeatureEngineeringService,
        )

        service = FeatureEngineeringService()

        print(f"\nTesting feature engineering service extraction:")
        for i, event in enumerate(product_viewed_events):
            event_dict = {
                "interactionType": event.interactionType,
                "customerId": event.customerId,
                "metadata": event.metadata,
            }

            extracted_id = service._extract_product_id_from_event(event_dict)
            print(f"  Event {i+1}: {extracted_id}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_product_viewed_events())
