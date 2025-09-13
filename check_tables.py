#!/usr/bin/env python3
import asyncio
import sys

sys.path.append(".")
from app.db.database import get_database


async def check_tables():
    db = await get_database()

    # Check InteractionFeatures table
    print("=== InteractionFeatures Table ===")
    interactions = await db.interactionfeatures.find_many(take=5)
    for interaction in interactions:
        print(
            f"CustomerId: {interaction.customerId}, ProductId: {interaction.productId}, PurchaseCount: {interaction.purchaseCount}"
        )

    print("\n=== ProductFeatures Table ===")
    products = await db.productfeatures.find_many(take=5)
    for product in products:
        print(f"ProductId: {product.productId}, ProductName: {product.productName}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(check_tables())
