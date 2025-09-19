#!/usr/bin/env python3
"""
Simple runner script for Shopify Data Collection Service
Usage: python run_data_collection.py
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService
from app.domains.shopify.services.api_client import ShopifyAPIClient
from app.domains.shopify.services.permission_service import ShopifyPermissionService
from app.domains.shopify.services.data_storage import ShopifyDataStorageService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def main():
    """Main function to run data collection"""

    # Configuration - Update these values as needed
    SHOP_DOMAIN = "vnsaid.myshopify.com"  # Replace with actual shop domain
    ACCESS_TOKEN = (
        "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"  # Replace with actual access token
    )
    SHOP_ID = "cmfqfw77h0000v3mwy059pq80"  # Replace with actual shop ID

    # Data collection options
    INCLUDE_PRODUCTS = True
    INCLUDE_ORDERS = True
    INCLUDE_CUSTOMERS = True
    INCLUDE_COLLECTIONS = True

    print("🚀 Starting Shopify Data Collection Service")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print(f"🏪 Shop: {SHOP_DOMAIN}")
    print(
        f"📊 Data Types: Products={INCLUDE_PRODUCTS}, Orders={INCLUDE_ORDERS}, Customers={INCLUDE_CUSTOMERS}, Collections={INCLUDE_COLLECTIONS}"
    )
    print("-" * 60)

    try:
        # Initialize services
        print("🔧 Initializing services...")
        api_client = ShopifyAPIClient()
        permission_service = ShopifyPermissionService(api_client)
        data_storage = ShopifyDataStorageService()

        # Create data collection service
        collection_service = ShopifyDataCollectionService(
            api_client=api_client,
            permission_service=permission_service,
            data_storage=data_storage,
        )

        print("✅ Services initialized successfully")
        print("-" * 60)

        # Run data collection
        print("📥 Starting data collection...")
        result = await collection_service.collect_all_data(
            shop_domain=SHOP_DOMAIN,
            access_token=ACCESS_TOKEN,
            shop_id=SHOP_ID,
            include_products=INCLUDE_PRODUCTS,
            include_orders=INCLUDE_ORDERS,
            include_customers=INCLUDE_CUSTOMERS,
            include_collections=INCLUDE_COLLECTIONS,
        )

        print("-" * 60)
        print("🎉 Data Collection Completed!")
        print(f"✅ Success: {result.get('success', False)}")
        print(f"📊 Total Items: {result.get('total_items', 0)}")

        if not result.get("success", False):
            print(f"❌ Error: {result.get('message', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Error during data collection: {str(e)}")
        logger.error(f"Data collection failed: {e}")
        return False

    return True


def run_with_config():
    """Run with configuration from environment variables or file"""

    # Try to load from environment variables
    SHOP_DOMAIN = os.getenv("SHOP_DOMAIN", "your-shop.myshopify.com")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "your-access-token")
    SHOP_ID = os.getenv("SHOP_ID", "your-shop-id")

    # Check if configuration is provided
    if SHOP_DOMAIN == "your-shop.myshopify.com" or ACCESS_TOKEN == "your-access-token":
        print("⚠️  Configuration Required!")
        print("Please set the following environment variables:")
        print("  export SHOP_DOMAIN='your-shop.myshopify.com'")
        print("  export ACCESS_TOKEN='your-access-token'")
        print("  export SHOP_ID='your-shop-id'")
        print("\nOr update the values directly in this script.")
        return False

    # Update the main function with actual values
    import run_data_collection

    run_data_collection.SHOP_DOMAIN = SHOP_DOMAIN
    run_data_collection.ACCESS_TOKEN = ACCESS_TOKEN
    run_data_collection.SHOP_ID = SHOP_ID

    return asyncio.run(main())


if __name__ == "__main__":
    print("🔧 Shopify Data Collection Runner")
    print("=" * 50)

    # Check if we should use environment variables
    if len(sys.argv) > 1 and sys.argv[1] == "--env":
        success = run_with_config()
    else:
        # Run with default configuration (needs to be updated)
        success = asyncio.run(main())

    if success:
        print("\n✅ Data collection completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Data collection failed!")
        sys.exit(1)
