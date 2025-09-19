#!/usr/bin/env python3
"""
Test script to verify incremental collection is working properly
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService
from app.domains.shopify.services.api_client import ShopifyAPIClient
from app.domains.shopify.services.permission_service import ShopifyPermissionService
from app.domains.shopify.services.data_storage import ShopifyDataStorageService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_incremental_collection():
    """Test incremental collection logic"""

    print("🧪 Testing Incremental Collection Logic")
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

        # Test 1: Check if we have existing data
        print("\n📊 Test 1: Checking existing data...")
        shop = await data_storage.get_shop_by_domain(SHOP_DOMAIN)
        if shop:
            print(f"✅ Shop found: {shop.id}")

            # Check raw data counts
            from app.core.database.simple_db_client import get_database

            db = await get_database()

            products_count = await db.rawproduct.count(where={"shopId": shop.id})
            orders_count = await db.raworder.count(where={"shopId": shop.id})
            customers_count = await db.rawcustomer.count(where={"shopId": shop.id})

            print(
                f"📦 Existing data: Products={products_count}, Orders={orders_count}, Customers={customers_count}"
            )
        else:
            print("❌ Shop not found")
            return False

        # Test 2: Check last collection times
        print("\n⏰ Test 2: Checking last collection times...")
        for data_type in ["products", "orders", "customers"]:
            last_time = await collection_service._get_last_collection_time(
                SHOP_DOMAIN, data_type
            )
            if last_time:
                from app.shared.helpers import now_utc

                hours_ago = (now_utc() - last_time).total_seconds() / 3600
                print(
                    f"📅 {data_type.title()}: Last collected {hours_ago:.1f} hours ago"
                )
            else:
                print(f"📅 {data_type.title()}: No last collection time found")

        # Test 3: Test incremental collection decision
        print("\n🤔 Test 3: Testing incremental collection decision...")
        for data_type in ["products", "orders", "customers"]:
            should_do_full = await collection_service._should_do_full_collection(
                SHOP_DOMAIN, data_type, False
            )
            collection_type = "FULL" if should_do_full else "INCREMENTAL"
            print(f"📋 {data_type.title()}: {collection_type} collection")

        # Test 4: Run actual incremental collection
        print("\n🚀 Test 4: Running incremental collection...")
        result = await collection_service.collect_all_data(
            shop_domain=SHOP_DOMAIN,
            access_token=ACCESS_TOKEN,
            shop_id=SHOP_ID,
            include_products=True,
            include_orders=True,
            include_customers=True,
            include_collections=False,
        )

        print(f"📊 Collection result: {result}")

        if result.get("success"):
            total_items = result.get("total_items", 0)
            if total_items == 0:
                print(
                    "✅ Incremental collection working correctly - No new data to collect"
                )
            else:
                print(
                    f"⚠️ Collected {total_items} items - This might indicate full collection instead of incremental"
                )
        else:
            print(f"❌ Collection failed: {result.get('message', 'Unknown error')}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Incremental test failed: {e}")
        return False


async def main():
    """Main test function"""

    print("🔍 Incremental Collection Test")
    print("=" * 60)

    success = await test_incremental_collection()

    print("\n" + "=" * 60)
    if success:
        print("✅ Incremental collection test completed!")
    else:
        print("❌ Incremental collection test failed!")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
