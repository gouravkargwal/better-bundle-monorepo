#!/usr/bin/env python3
"""
Complete test of the refund webhook flow:
1. Simulate webhook receiving refund payload
2. Store in raw table (like the webhook handler does)
3. Process through field extractor
4. Update main table
5. Verify the order was updated correctly
"""

import asyncio
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
from prisma import Json

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


async def simulate_webhook_storage(
    shop_id: str, refund_payload: Dict[str, Any]
) -> bool:
    """Simulate storing the refund payload in the raw table (like the webhook handler does)"""
    try:
        db = await get_database()

        # Get the shop record
        shop_record = await db.query_raw('SELECT id FROM "Shop" WHERE id = $1', shop_id)

        if not shop_record:
            logger.error(f"Shop not found: {shop_id}")
            return False

        shop_db_id = shop_record[0]["id"]
        order_id = str(refund_payload["order_id"])

        # Check if raw order already exists
        existing = await db.query_raw(
            'SELECT id, payload FROM "RawOrder" WHERE "shopId" = $1 AND "shopifyId" = $2',
            shop_db_id,
            order_id,
        )

        if existing:
            # Update existing raw order with refund data
            existing_payload = existing[0]["payload"]
            updated_payload = {
                **existing_payload,
                "refunds": [
                    *(existing_payload.get("refunds", [])),
                    refund_payload,
                ],
            }

            await db.raworder.update(
                where={"id": existing[0]["id"]},
                data={
                    "payload": Json(updated_payload),
                    "shopifyUpdatedAt": datetime.now(),
                },
            )

            logger.info(f"✅ Updated existing raw order {order_id} with refund data")
        else:
            # Create new raw order with refund data
            await db.raworder.create(
                data={
                    "shopId": shop_db_id,
                    "payload": Json({"refunds": [refund_payload]}),
                    "shopifyId": order_id,
                    "shopifyCreatedAt": datetime.now(),
                    "shopifyUpdatedAt": datetime.now(),
                }
            )

            logger.info(f"✅ Created new raw order {order_id} with refund data")

        return True

    except Exception as e:
        logger.error(f"❌ Error storing refund in raw table: {e}")
        return False


async def test_complete_refund_flow(shop_id: str):
    """Test the complete refund webhook flow"""

    logger.info("🧪 Starting complete refund webhook flow test...")

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

    # Step 3: Simulate webhook storage (store in raw table)
    logger.info("💾 Step 3: Simulating webhook storage in raw table...")
    storage_success = await simulate_webhook_storage(shop_id, refund_payload)

    if not storage_success:
        logger.error("❌ Failed to store refund in raw table")
        return

    # Step 4: Test field extraction from raw data
    logger.info("🔍 Step 4: Testing field extraction from raw data...")
    field_extractor = FieldExtractorService()

    try:
        # Get the raw order data we just stored
        db = await get_database()
        raw_order = await db.query_raw(
            'SELECT payload FROM "RawOrder" WHERE "shopId" = $1 AND "shopifyId" = $2',
            shop_id,
            str(refund_payload["order_id"]),
        )

        if not raw_order:
            logger.error("❌ Could not find raw order data")
            return

        raw_payload = raw_order[0]["payload"]

        # Debug: Check the raw payload structure
        logger.info(f"Raw payload keys: {list(raw_payload.keys())}")
        logger.info(f"Raw payload type: {type(raw_payload)}")
        if "refunds" in raw_payload and raw_payload["refunds"]:
            logger.info(f"First refund keys: {list(raw_payload['refunds'][0].keys())}")
            logger.info(
                f"First refund order_id: {raw_payload['refunds'][0].get('order_id')}"
            )

        # Extract fields from the raw payload
        extracted_data = field_extractor.extract_order_fields(
            raw_payload, shop_id, "webhook"
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

    # Step 5: Test main table storage
    logger.info("💾 Step 5: Testing main table storage...")
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

    # Step 6: Verify the update
    logger.info("🔍 Step 6: Verifying order update...")
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

    logger.info("🏁 Complete refund webhook flow test completed!")


async def main():
    """Main function"""

    # You'll need to provide a valid shop ID
    shop_id = input(
        "Enter shop ID to test with (or press Enter to use 'cmfj9sixy0000v3qj40in5yt6'): "
    ).strip()

    if not shop_id:
        shop_id = "cmfj9sixy0000v3qj40in5yt6"

    logger.info(f"🚀 Starting complete refund webhook flow test for shop: {shop_id}")

    try:
        await test_complete_refund_flow(shop_id)
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
