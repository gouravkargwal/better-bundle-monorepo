#!/usr/bin/env python3
"""
Test script to directly test interaction feature generation
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


async def test_interaction_generation():
    """Test interaction feature generation directly"""
    try:
        db = await get_database()

        # Test with a specific product that has 0 views
        product_id = "7903465537675"
        customer_id = "8619514265739"
        shop_id = "cmfnmj5sn0000v3gaipwx948o"

        print(f"Testing interaction feature generation for:")
        print(f"  Product: {product_id}")
        print(f"  Customer: {customer_id}")
        print(f"  Shop: {shop_id}")

        # Get behavioral events for this customer
        behavioral_events = await db.userinteraction.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

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

        print(f"\nFound {len(events_dict)} behavioral events")

        # Get orders for this customer
        orders = await db.orderdata.find_many(
            where={"shopId": shop_id, "customerId": customer_id}
        )

        # Convert to dict format
        orders_dict = []
        for order in orders:
            orders_dict.append(
                {"customerId": order.customerId, "lineItems": order.lineItems}
            )

        print(f"Found {len(orders_dict)} orders")

        # Create context
        context = {"behavioral_events": events_dict, "orders": orders_dict}

        # Test the interaction feature generator
        generator = InteractionFeatureGenerator()

        print(f"\nGenerating interaction features...")
        features = await generator.generate_features(
            shop_id, customer_id, product_id, context
        )

        print(f"\nGenerated features:")
        print(f"  viewCount: {features.get('viewCount', 0)}")
        print(f"  cartAddCount: {features.get('cartAddCount', 0)}")
        print(f"  purchaseCount: {features.get('purchaseCount', 0)}")
        print(f"  interactionScore: {features.get('interactionScore', 0)}")
        print(f"  affinityScore: {features.get('affinityScore', 0)}")

        # Check if this matches what's in the database
        db_features = await db.interactionfeatures.find_first(
            where={
                "shopId": shop_id,
                "customerId": customer_id,
                "productId": product_id,
            }
        )

        if db_features:
            print(f"\nDatabase features:")
            print(f"  viewCount: {db_features.viewCount}")
            print(f"  cartAddCount: {db_features.cartAddCount}")
            print(f"  purchaseCount: {db_features.purchaseCount}")
            print(f"  interactionScore: {db_features.interactionScore}")
            print(f"  affinityScore: {db_features.affinityScore}")
        else:
            print(f"\nNo features found in database for this product")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_interaction_generation())
