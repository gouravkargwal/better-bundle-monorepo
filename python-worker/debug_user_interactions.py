#!/usr/bin/env python3
"""
Debug script to check user interaction data and calculation
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_user_interactions():
    """Debug user interaction data"""
    try:
        db = await get_database()

        # Check user interactions for the test customer
        customer_id = "8619514265739"

        # Get user interactions
        interactions = await db.userinteraction.find_many(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "customerId": customer_id},
            take=20,
        )

        print(f"User interactions for customer {customer_id}: {len(interactions)}")

        # Group by interaction type
        interaction_types = {}
        product_views = []

        for interaction in interactions:
            event_type = interaction.interactionType
            if event_type not in interaction_types:
                interaction_types[event_type] = 0
            interaction_types[event_type] += 1

            # Check for product views
            if event_type == "product_viewed":
                # Try to extract product ID from metadata
                metadata = interaction.metadata
                if isinstance(metadata, dict):
                    product_id = metadata.get("productId")
                    if product_id:
                        product_views.append(product_id)
                        print(f"  Product view: {product_id}")

        print(f"\nInteraction types:")
        for event_type, count in interaction_types.items():
            print(f"  {event_type}: {count}")

        print(f"\nUnique products viewed: {len(set(product_views))}")
        print(f"Product IDs: {list(set(product_views))}")

        # Check interaction features for this customer
        interaction_features = await db.interactionfeatures.find_many(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "customerId": customer_id}
        )

        print(
            f"\nInteraction features for customer {customer_id}: {len(interaction_features)}"
        )

        for feature in interaction_features:
            print(
                f"  Product {feature.productId}: views={feature.viewCount}, cart_adds={feature.cartAddCount}, purchases={feature.purchaseCount}"
            )

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_user_interactions())
