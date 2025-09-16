#!/usr/bin/env python3
"""
Test script to simulate a refund webhook event
This script will:
1. Get an existing order from the database
2. Create a refund payload
3. Test the refund webhook processing
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.database import get_database
from app.domains.shopify.services.field_extractor import FieldExtractorService
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_sample_order(shop_id: str) -> Optional[Dict[str, Any]]:
    """Get a sample order from the database"""
    try:
        db = await get_database()

        # Get the first order for the shop
        query = """
        SELECT * FROM "OrderData" 
        WHERE "shopId" = $1 
        ORDER BY "orderDate" DESC 
        LIMIT 1
        """

        result = await db.query_raw(query, shop_id)

        if result:
            order = dict(result[0])
            logger.info(
                f"Found order: {order['orderId']} - {order['orderName']} - ${order['totalAmount']}"
            )
            return order
        else:
            logger.warning(f"No orders found for shop {shop_id}")
            return None

    except Exception as e:
        logger.error(f"Error getting sample order: {e}")
        return None


def create_refund_payload(order: Dict[str, Any]) -> Dict[str, Any]:
    """Create a refund webhook payload based on an existing order"""

    # Calculate a partial refund amount (e.g., 50% of the order)
    refund_amount = order["totalAmount"] * 0.5

    refund_payload = {
        "id": 890088186047892319,  # Refund ID
        "order_id": int(order["orderId"]),  # Order ID from the database
        "created_at": datetime.now().isoformat(),
        "note": "Test refund - customer requested return",
        "user_id": 548380009,
        "processed_at": datetime.now().isoformat(),
        "duties": [],
        "total_duties_set": {
            "shop_money": {"amount": "0.00", "currency_code": "USD"},
            "presentment_money": {"amount": "0.00", "currency_code": "USD"},
        },
        "return": None,
        "restock": False,
        "refund_shipping_lines": [],
        "admin_graphql_api_id": f"gid://shopify/Refund/{890088186047892319}",
        "order_adjustments": [],
        "refund_line_items": [
            {
                "id": 487817672276298627,
                "quantity": 1,
                "line_item_id": 487817672276298554,
                "location_id": None,
                "restock_type": "no_restock",
                "subtotal": refund_amount,
                "total_tax": 0.0,
                "subtotal_set": {
                    "shop_money": {
                        "amount": str(refund_amount),
                        "currency_code": "USD",
                    },
                    "presentment_money": {
                        "amount": str(refund_amount),
                        "currency_code": "USD",
                    },
                },
                "total_tax_set": {
                    "shop_money": {"amount": "0.00", "currency_code": "USD"},
                    "presentment_money": {"amount": "0.00", "currency_code": "USD"},
                },
                "line_item": {
                    "id": 487817672276298554,
                    "variant_id": None,
                    "title": "Test Product",
                    "quantity": 1,
                    "sku": "TEST-SKU-001",
                    "variant_title": None,
                    "vendor": None,
                    "fulfillment_service": "manual",
                    "product_id": 788032119674292922,
                    "requires_shipping": True,
                    "taxable": True,
                    "gift_card": False,
                    "name": "Test Product",
                    "variant_inventory_management": None,
                    "properties": [],
                    "product_exists": True,
                    "fulfillable_quantity": 1,
                    "grams": 100,
                    "price": str(refund_amount),
                    "total_discount": "0.00",
                    "fulfillment_status": None,
                    "price_set": {
                        "shop_money": {
                            "amount": str(refund_amount),
                            "currency_code": "USD",
                        },
                        "presentment_money": {
                            "amount": str(refund_amount),
                            "currency_code": "USD",
                        },
                    },
                    "total_discount_set": {
                        "shop_money": {"amount": "0.00", "currency_code": "USD"},
                        "presentment_money": {"amount": "0.00", "currency_code": "USD"},
                    },
                    "discount_allocations": [],
                    "duties": [],
                    "admin_graphql_api_id": "gid://shopify/LineItem/487817672276298554",
                    "tax_lines": [],
                },
            }
        ],
        "transactions": [
            {
                "id": 245135271310201194,
                "order_id": int(order["orderId"]),
                "kind": "refund",
                "gateway": "bogus",
                "status": "success",
                "message": "Test refund transaction",
                "created_at": datetime.now().isoformat(),
                "test": True,
                "authorization": None,
                "location_id": None,
                "user_id": None,
                "parent_id": None,
                "processed_at": None,
                "device_id": None,
                "error_code": None,
                "source_name": "web",
                "receipt": {},
                "amount": str(refund_amount),
                "currency": None,
                "payment_id": f"#{order['orderName']}",
                "total_unsettled_set": {
                    "presentment_money": {"amount": "0.0", "currency": "XXX"},
                    "shop_money": {"amount": "0.0", "currency": "XXX"},
                },
                "manual_payment_gateway": False,
                "amount_rounding": None,
                "admin_graphql_api_id": "gid://shopify/OrderTransaction/245135271310201194",
            }
        ],
    }

    return refund_payload


async def test_refund_processing(shop_id: str):
    """Test the refund webhook processing"""

    logger.info("🧪 Starting refund webhook test...")

    # Step 1: Get a sample order
    logger.info("📋 Step 1: Getting sample order from database...")
    order = await get_sample_order(shop_id)

    if not order:
        logger.error("❌ No orders found to test with")
        return

    logger.info(
        f"✅ Found order: {order['orderId']} - {order['orderName']} - ${order['totalAmount']}"
    )
    logger.info(
        f"   Current financial status: {order.get('financialStatus', 'unknown')}"
    )
    logger.info(f"   Current refunded amount: ${order.get('totalRefundedAmount', 0)}")

    # Step 2: Create refund payload
    logger.info("📦 Step 2: Creating refund payload...")
    refund_payload = create_refund_payload(order)

    logger.info(f"✅ Created refund payload:")
    logger.info(f"   Refund ID: {refund_payload['id']}")
    logger.info(f"   Order ID: {refund_payload['order_id']}")
    logger.info(f"   Refund amount: ${refund_payload['transactions'][0]['amount']}")

    # Step 3: Test field extraction
    logger.info("🔍 Step 3: Testing field extraction...")
    field_extractor = FieldExtractorService()

    try:
        extracted_data = field_extractor.extract_order_fields(
            refund_payload, shop_id, "webhook"
        )

        if extracted_data:
            logger.info("✅ Field extraction successful!")
            logger.info(f"   Extracted order ID: {extracted_data.get('orderId')}")
            logger.info(
                f"   Extracted refund amount: ${extracted_data.get('totalRefundedAmount', 0)}"
            )
            logger.info(
                f"   Extracted financial status: {extracted_data.get('financialStatus', 'unknown')}"
            )
        else:
            logger.error("❌ Field extraction failed - no data returned")
            return

    except Exception as e:
        logger.error(f"❌ Field extraction failed: {e}")
        return

    # Step 4: Test main table storage
    logger.info("💾 Step 4: Testing main table storage...")
    storage_service = MainTableStorageService(debug_mode=True)

    try:
        # Store the refund data
        result = await storage_service._store_data_generic(
            "orders", shop_id, incremental=True
        )

        if result.success:
            logger.info("✅ Main table storage successful!")
            logger.info(f"   Processed: {result.processed_count} records")
            logger.info(f"   Errors: {result.error_count}")
            logger.info(f"   Duration: {result.duration_ms}ms")
        else:
            logger.error("❌ Main table storage failed!")
            logger.error(f"   Errors: {result.errors}")

    except Exception as e:
        logger.error(f"❌ Main table storage failed: {e}")
        return

    # Step 5: Verify the update
    logger.info("🔍 Step 5: Verifying order update...")
    updated_order = await get_sample_order(shop_id)

    if updated_order:
        logger.info("✅ Order verification:")
        logger.info(f"   Order ID: {updated_order['orderId']}")
        logger.info(
            f"   Financial status: {updated_order.get('financialStatus', 'unknown')}"
        )
        logger.info(
            f"   Refunded amount: ${updated_order.get('totalRefundedAmount', 0)}"
        )
        logger.info(f"   Note: {updated_order.get('note', 'No note')}")

        # Check if the refund was applied
        if updated_order.get("totalRefundedAmount", 0) > 0:
            logger.info("🎉 SUCCESS: Refund was successfully applied to the order!")
        else:
            logger.warning(
                "⚠️  WARNING: Refund amount is still 0 - check the processing"
            )
    else:
        logger.error("❌ Could not retrieve updated order")

    logger.info("🏁 Refund webhook test completed!")


async def main():
    """Main function"""

    # You'll need to provide a valid shop ID
    # You can get this from your database or environment
    shop_id = input(
        "Enter shop ID to test with (or press Enter to use 'test-shop-123'): "
    ).strip()

    if not shop_id:
        shop_id = "test-shop-123"

    logger.info(f"🚀 Starting refund webhook test for shop: {shop_id}")

    try:
        await test_refund_processing(shop_id)
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
