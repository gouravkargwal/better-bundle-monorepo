#!/usr/bin/env python3
"""
Debug script to check if products exist in ProductData
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_product_data():
    """Debug if products exist in ProductData"""
    try:
        db = await get_database()

        # Products that were viewed
        viewed_products = [
            "7894679355531",
            "7903465537675",
            "7903467045003",
            "7903467765899",
        ]

        print("Checking if products exist in ProductData:")
        for product_id in viewed_products:
            product = await db.productdata.find_first(
                where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "productId": product_id}
            )

            exists = product is not None
            print(f"Product {product_id}: {'EXISTS' if exists else 'MISSING'}")

            if exists:
                print(f"  Title: {product.title}")
                print(f"  Vendor: {product.vendor}")
            else:
                print(f"  This product is missing from ProductData!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_product_data())
