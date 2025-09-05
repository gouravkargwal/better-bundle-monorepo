#!/usr/bin/env python3
"""
Test script to fire behavioral events to the webhook endpoint and verify data is saved to database
"""

import asyncio
import json
import sys
from datetime import datetime
import httpx

# Test payloads for all event types
test_payloads = [
    # 1. PageViewedEvent
    {
        "id": "page-viewed-123",
        "timestamp": "2025-09-05T09:30:00Z",
        "name": "page_viewed",
        "customer_id": "cust-101",
        "data": {
            "url": "https://test-shop.myshopify.com/products/test-product",
            "referrer": "https://google.com",
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 2. ProductViewedEvent
    {
        "id": "product-viewed-456",
        "timestamp": "2025-09-05T09:35:00Z",
        "name": "product_viewed",
        "customer_id": "cust-101",
        "data": {
            "productVariant": {
                "id": "variant-abc",
                "title": "Unisex Hoodie",
                "sku": "UH-101",
                "price": 45.00,
                "productId": "prod-xyz",
            }
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 3. ProductAddedToCartEvent
    {
        "id": "add-to-cart-789",
        "timestamp": "2025-09-05T09:40:00Z",
        "name": "product_added_to_cart",
        "customer_id": "cust-101",
        "data": {
            "cart": {
                "id": "cart-123",
                "totalQuantity": 2,
                "lines": [
                    {
                        "id": "variant-abc",
                        "title": "Unisex Hoodie",
                        "sku": "UH-101",
                        "price": 45.00,
                        "productId": "prod-xyz",
                    }
                ],
            },
            "productVariant": {
                "id": "variant-def",
                "title": "Running Shoes",
                "sku": "RS-202",
                "price": 99.99,
                "productId": "prod-mno",
            },
            "quantity": 1,
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 4. CollectionViewedEvent
    {
        "id": "collection-viewed-101",
        "timestamp": "2025-09-05T09:45:00Z",
        "name": "collection_viewed",
        "customer_id": "cust-101",
        "data": {
            "collectionId": "collection-555",
            "collectionTitle": "Summer Collection",
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 5. SearchSubmittedEvent
    {
        "id": "search-submitted-202",
        "timestamp": "2025-09-05T09:50:00Z",
        "name": "search_submitted",
        "customer_id": "cust-101",
        "data": {
            "query": "blue jeans",
            "results": [
                {
                    "id": "variant-456",
                    "title": "Slim Fit Blue Jeans",
                    "sku": "SFBJ-101",
                    "price": 75.00,
                    "productId": "prod-456",
                }
            ],
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 6. CheckoutStartedEvent
    {
        "id": "checkout-started-303",
        "timestamp": "2025-09-05T09:55:00Z",
        "name": "checkout_started",
        "customer_id": "cust-101",
        "data": {
            "checkout": {
                "id": "checkout-abc",
                "totalPrice": 144.99,
                "currency": "USD",
                "products": [
                    {
                        "id": "variant-abc",
                        "title": "Unisex Hoodie",
                        "sku": "UH-101",
                        "price": 45.00,
                        "productId": "prod-xyz",
                    },
                    {
                        "id": "variant-def",
                        "title": "Running Shoes",
                        "sku": "RS-202",
                        "price": 99.99,
                        "productId": "prod-mno",
                    },
                ],
            }
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 7. CheckoutCompletedEvent
    {
        "id": "checkout-completed-404",
        "timestamp": "2025-09-05T10:00:00Z",
        "name": "checkout_completed",
        "customer_id": "cust-101",
        "data": {
            "checkout": {
                "id": "checkout-def",
                "totalPrice": 144.99,
                "currency": "USD",
                "products": [
                    {
                        "id": "variant-abc",
                        "title": "Unisex Hoodie",
                        "sku": "UH-101",
                        "price": 45.00,
                        "productId": "prod-xyz",
                    },
                    {
                        "id": "variant-def",
                        "title": "Running Shoes",
                        "sku": "RS-202",
                        "price": 99.99,
                        "productId": "prod-mno",
                    },
                ],
            }
        },
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
    # 8. GenericEvent (Fallback)
    {
        "id": "generic-event-505",
        "timestamp": "2025-09-05T10:05:00Z",
        "name": "unknown_event_type",
        "customer_id": "cust-101",
        "data": {"custom_field_1": "value1", "custom_field_2": 123},
        "context": {"shop": {"domain": "test-shop.myshopify.com"}},
    },
]


async def test_webhook_endpoint():
    """Test the webhook endpoint by sending all event types"""
    base_url = "http://localhost:8001"
    endpoint = "/collect/behavioral-events"

    print("🚀 Testing behavioral events webhook endpoint...")
    print(f"📡 Endpoint: {base_url}{endpoint}")
    print(f"📊 Total events to test: {len(test_payloads)}\n")

    success_count = 0
    failed_count = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, payload in enumerate(test_payloads, 1):
            event_name = payload.get("name", "unknown")
            event_id = payload.get("id", "unknown")

            print(f"Test {i}/{len(test_payloads)}: {event_name} (ID: {event_id})")

            try:
                # Send the request
                response = await client.post(
                    f"{base_url}{endpoint}",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Shopify-Shop-Domain": "cmf4uf3tr0000v3rsmi68lnrj",
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Success! Status: {result.get('status')}")
                    print(f"   Event ID: {result.get('event_id')}")
                    print(f"   Message ID: {result.get('message_id')}")
                    success_count += 1
                else:
                    print(f"❌ Failed! Status Code: {response.status_code}")
                    print(f"   Response: {response.text}")
                    failed_count += 1

            except httpx.ConnectError:
                print(f"❌ Connection Error: Could not connect to {base_url}")
                print("   Make sure the server is running on localhost:8001")
                failed_count += 1
            except Exception as e:
                print(f"❌ Error: {e}")
                failed_count += 1

            print()  # Empty line for readability

    print(f"📊 Results: {success_count}/{len(test_payloads)} tests passed")

    if success_count == len(test_payloads):
        print("🎉 All webhook tests passed!")
        print("💡 Check the database to verify data was saved to both tables:")
        print("   - RawBehavioralEvents (raw payloads)")
        print("   - BehavioralEvents (structured data)")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")


async def check_database_status():
    """Check if the behavioral events consumer is processing events"""
    base_url = "http://localhost:8001"
    endpoint = "/api/behavioral-events/status"

    print("\n🔍 Checking behavioral events processing status...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}{endpoint}")

            if response.status_code == 200:
                status = response.json()
                print(f"✅ Consumer Status: {status.get('status')}")
                print(f"📊 Active Events: {status.get('active_events_count', 0)}")

                active_events = status.get("active_events", {})
                if active_events:
                    print("🔄 Currently Processing:")
                    for event_id, event_info in active_events.items():
                        print(
                            f"   - {event_id}: {event_info.get('status')} (Shop: {event_info.get('shop_id')})"
                        )
                else:
                    print("✅ No events currently being processed")
            else:
                print(f"❌ Status check failed: {response.status_code}")
                print(f"   Response: {response.text}")

    except Exception as e:
        print(f"❌ Error checking status: {e}")


if __name__ == "__main__":
    print("🧪 Behavioral Events Webhook Test Suite")
    print("=" * 50)

    # Run the tests
    asyncio.run(test_webhook_endpoint())

    # Wait a moment for processing
    print("\n⏳ Waiting 3 seconds for background processing...")
    import time

    time.sleep(3)

    # Check processing status
    asyncio.run(check_database_status())

    print("\n💡 Next Steps:")
    print(
        "1. Check your database for new records in RawBehavioralEvents and BehavioralEvents tables"
    )
    print("2. Verify the data structure matches your expectations")
    print("3. Check the application logs for any processing errors")
