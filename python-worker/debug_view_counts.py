#!/usr/bin/env python3
"""
Debug script to check view counts for specific products
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_view_counts():
    """Debug view counts for specific products"""
    try:
        db = await get_database()

        # Products that were viewed
        viewed_products = [
            "7894679355531",
            "7903465537675",
            "7903467045003",
            "7903467765899",
        ]

        print("Checking view counts for viewed products:")
        for product_id in viewed_products:
            # Get interaction features for this product
            features = await db.interactionfeatures.find_many(
                where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "productId": product_id}
            )

            print(f"\nProduct {product_id}:")
            print(f"  Total interaction features: {len(features)}")

            for feature in features:
                print(
                    f"  Customer {feature.customerId}: views={feature.viewCount}, cart_adds={feature.cartAddCount}, purchases={feature.purchaseCount}"
                )

        # Check how many product_viewed events we have for each product
        print(f"\nChecking product_viewed events:")
        for product_id in viewed_products:
            events = await db.userinteraction.find_many(
                where={
                    "shopId": "cmfnmj5sn0000v3gaipwx948o",
                    "interactionType": "product_viewed",
                }
            )

            count = 0
            for event in events:
                metadata = event.metadata
                if isinstance(metadata, dict):
                    data = metadata.get("data", {})
                    product_variant = data.get("productVariant", {})
                    product = product_variant.get("product", {})
                    event_product_id = product.get("id", "")
                    if event_product_id == product_id:
                        count += 1

            print(f"  Product {product_id}: {count} product_viewed events")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_view_counts())
