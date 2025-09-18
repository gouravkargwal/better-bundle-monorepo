#!/usr/bin/env python3
"""
Debug script to test interaction pair detection
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database
from app.domains.ml.services.feature_engineering import FeatureEngineeringService


async def debug_interaction_pairs():
    """Debug interaction pair detection"""
    try:
        db = await get_database()

        # Get sample data
        user_interactions = await db.userinteraction.find_many(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "customerId": "8619514265739",
            },
            take=10,
        )

        # Convert to dict format
        events_dict = []
        for event in user_interactions:
            events_dict.append(
                {
                    "interactionType": event.interactionType,
                    "customerId": event.customerId,
                    "metadata": event.metadata,
                }
            )

        print(f"Testing with {len(events_dict)} events")

        # Test the feature engineering service
        service = FeatureEngineeringService()

        # Test product ID extraction
        print(f"\nTesting product ID extraction:")
        for i, event in enumerate(events_dict):
            extracted_id = service._extract_product_id_from_event(event)
            if extracted_id:
                print(
                    f"  Event {i}: {event['interactionType']} -> Product ID: {extracted_id}"
                )

        # Test interaction pair detection logic
        print(f"\nTesting interaction pair detection:")
        interaction_pairs = set()

        for event in events_dict:
            if event.get("customerId") and "metadata" in event:
                customer_id = event.get("customerId")
                event_type = event.get("interactionType", "")

                if event_type == "product_viewed":
                    event_product_id = service._extract_product_id_from_event(event)
                    if event_product_id:
                        interaction_pairs.add((customer_id, event_product_id))
                        print(f"  Added pair: ({customer_id}, {event_product_id})")

        print(f"\nTotal interaction pairs: {len(interaction_pairs)}")
        for pair in interaction_pairs:
            print(f"  {pair}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_interaction_pairs())
