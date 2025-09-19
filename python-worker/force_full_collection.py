#!/usr/bin/env python3
"""
Force full collection script - bypasses incremental logic
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService
from app.domains.shopify.services.api_client import ShopifyAPIClient
from app.domains.shopify.services.permission_service import ShopifyPermissionService
from app.domains.shopify.services.data_storage import ShopifyDataStorageService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def force_full_collection():
    """Force full collection for all data types"""

    print("🔄 Force Full Collection Script")
    print("=" * 50)

    # Configuration
    SHOP_DOMAIN = "vnsaid.myshopify.com"
    ACCESS_TOKEN = "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"
    SHOP_ID = "cmfqfw77h0000v3mwy059pq80"

    try:
        # Initialize services
        print("🔧 Initializing services...")
        api_client = ShopifyAPIClient()
        permission_service = ShopifyPermissionService(api_client)
        data_storage = ShopifyDataStorageService()

        collection_service = ShopifyDataCollectionService(
            api_client=api_client,
            permission_service=permission_service,
            data_storage=data_storage,
        )

        print("✅ Services initialized")

        # Force full collection for each data type
        print("\n🚀 Starting force full collection...")

        for data_type in ["products", "orders", "customers", "collections"]:
            print(f"\n📥 Force collecting {data_type}...")

            try:
                # Force full collection by setting force_full_collection=True
                result = await collection_service._collect_data_by_type(
                    data_type=data_type,
                    shop_domain=SHOP_DOMAIN,
                    access_token=ACCESS_TOKEN,
                    force_full_collection=True,
                    limit=50,  # Limit to 50 items for testing
                )

                print(
                    f"✅ {data_type.title()}: Collected {len(result) if result else 0} items"
                )

            except Exception as e:
                print(f"❌ {data_type.title()}: Collection failed - {e}")

        print("\n🎉 Force full collection completed!")
        return True

    except Exception as e:
        print(f"❌ Force collection failed: {e}")
        logger.error(f"Force collection failed: {e}")
        return False


async def main():
    """Main function"""

    print("🔄 Force Full Collection")
    print("=" * 60)
    print("⚠️  This will force full collection for all data types")
    print("⚠️  This bypasses incremental logic and collects all data")
    print("=" * 60)

    success = await force_full_collection()

    if success:
        print("\n✅ Force full collection completed successfully!")
    else:
        print("\n❌ Force full collection failed!")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
