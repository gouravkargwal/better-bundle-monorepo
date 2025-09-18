#!/usr/bin/env python3
"""
Debug script to understand why some products don't get interaction features
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_feature_generation():
    """Debug why some products don't get interaction features"""
    try:
        db = await get_database()

        # Get all product IDs that were viewed
        viewed_events = await db.userinteraction.find_many(
            where={
                "shopId": "cmfnmj5sn0000v3gaipwx948o",
                "interactionType": "product_viewed",
            }
        )

        viewed_product_ids = set()
        for event in viewed_events:
            metadata = event.metadata
            if isinstance(metadata, dict):
                data = metadata.get("data", {})
                product_variant = data.get("productVariant", {})
                product = product_variant.get("product", {})
                product_id = product.get("id", "")
                if product_id:
                    viewed_product_ids.add(product_id)

        print(f"Products viewed: {len(viewed_product_ids)}")
        print(f"Product IDs: {sorted(viewed_product_ids)}")

        # Get all interaction features
        interaction_features = await db.interactionfeatures.find_many(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o"}
        )

        feature_product_ids = set()
        for feature in interaction_features:
            feature_product_ids.add(feature.productId)

        print(f"\nProducts with interaction features: {len(feature_product_ids)}")
        print(f"Product IDs: {sorted(feature_product_ids)}")

        # Find missing products
        missing_products = viewed_product_ids - feature_product_ids
        print(f"\nMissing products: {len(missing_products)}")
        print(f"Missing Product IDs: {sorted(missing_products)}")

        # Check if these products exist in ProductData
        for product_id in missing_products:
            product = await db.productdata.find_first(
                where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "productId": product_id}
            )
            print(f"Product {product_id} exists in ProductData: {product is not None}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_feature_generation())
