#!/usr/bin/env python3
"""
Test script for Shopify Data Collection Service
This script tests the data collection service with mock data
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.domains.shopify.services.data_collection import ShopifyDataCollectionService


async def test_data_collection():
    """Test the data collection service with mock data"""

    print("🧪 Testing Shopify Data Collection Service")
    print("=" * 50)

    # Create mock services
    mock_api_client = Mock()
    mock_permission_service = Mock()
    mock_data_storage = Mock()

    # Mock API client methods
    mock_api_client.connect = AsyncMock()
    mock_api_client.set_access_token = AsyncMock()
    mock_api_client.get_products = AsyncMock(
        return_value={
            "edges": [
                {"node": {"id": "1", "title": "Test Product 1"}},
                {"node": {"id": "2", "title": "Test Product 2"}},
            ],
            "pageInfo": {"hasNextPage": False},
        }
    )
    mock_api_client.get_orders = AsyncMock(
        return_value={
            "edges": [
                {"node": {"id": "1", "name": "#1001"}},
                {"node": {"id": "2", "name": "#1002"}},
            ],
            "pageInfo": {"hasNextPage": False},
        }
    )

    # Mock permission service
    mock_permission_service.check_shop_permissions = AsyncMock(
        return_value={
            "products": True,
            "orders": True,
            "customers": True,
            "collections": True,
        }
    )

    # Mock data storage
    mock_data_storage.store_products_data = AsyncMock(
        return_value={"new": 2, "updated": 0}
    )
    mock_data_storage.store_orders_data = AsyncMock(
        return_value={"new": 2, "updated": 0}
    )

    # Create service instance
    service = ShopifyDataCollectionService(
        api_client=mock_api_client,
        permission_service=mock_permission_service,
        data_storage=mock_data_storage,
    )

    print("✅ Mock services created")

    # Test data collection
    try:
        print("📥 Testing data collection...")
        result = await service.collect_all_data(
            shop_domain="test-shop.myshopify.com",
            access_token="test-token",
            shop_id="test-shop-id",
            include_products=True,
            include_orders=True,
            include_customers=False,
            include_collections=False,
        )

        print("✅ Data collection test completed")
        print(f"📊 Result: {result}")

        # Verify results
        assert result["success"] == True, "Collection should succeed"
        assert result["total_items"] > 0, "Should collect some items"

        print("✅ All tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


async def test_individual_methods():
    """Test individual methods of the service"""

    print("\n🔧 Testing individual methods...")

    # Create mock services
    mock_api_client = Mock()
    mock_permission_service = Mock()
    mock_data_storage = Mock()

    service = ShopifyDataCollectionService(
        api_client=mock_api_client,
        permission_service=mock_permission_service,
        data_storage=mock_data_storage,
    )

    # Test permission checking
    print("🔐 Testing permission checking...")
    mock_permission_service.check_shop_permissions = AsyncMock(
        return_value={"products": True, "orders": False}
    )

    permissions = await service._check_permissions("test-shop.com", "test-token")
    assert permissions["products"] == True, "Products permission should be True"
    assert permissions["orders"] == False, "Orders permission should be False"
    print("✅ Permission checking works")

    # Test data type filtering
    print("📋 Testing data type filtering...")
    collectable = service._get_collectable_data_types(
        {"products": True, "orders": False},
        {"products": True, "orders": True, "customers": False, "collections": False},
    )
    assert "products" in collectable, "Products should be collectable"
    assert "orders" not in collectable, "Orders should not be collectable"
    print("✅ Data type filtering works")

    print("✅ All individual method tests passed!")


async def main():
    """Main test function"""

    print("🚀 Starting Data Collection Service Tests")
    print("=" * 60)

    # Run tests
    test1_passed = await test_data_collection()
    test2_passed = await test_individual_methods()

    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 All tests passed! Service is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Check the output above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
