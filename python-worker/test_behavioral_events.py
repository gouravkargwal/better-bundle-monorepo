#!/usr/bin/env python3
"""
Test script for ShopifyBehavioralEvent validation with all event types
"""

import sys
from pydantic import ValidationError, TypeAdapter
from datetime import datetime

sys.path.insert(0, ".")
from app.webhooks.models import ShopifyBehavioralEvent

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


def test_validation():
    """Test validation for all event types"""
    print("🧪 Testing ShopifyBehavioralEvent validation with all event types...\n")

    adapter = TypeAdapter(ShopifyBehavioralEvent)

    success_count = 0
    total_count = len(test_payloads)

    for i, payload in enumerate(test_payloads, 1):
        event_name = payload.get("name", "unknown")
        event_id = payload.get("id", "unknown")

        print(f"Test {i}/{total_count}: {event_name} (ID: {event_id})")

        try:
            validated_event = adapter.validate_python(payload)
            print(f"✅ Validation successful!")
            print(f"   Event Type: {type(validated_event).__name__}")
            print(f"   Event ID: {validated_event.id}")
            print(f"   Event Name: {validated_event.name}")
            print(f"   Customer ID: {validated_event.customer_id}")
            print(f"   Timestamp: {validated_event.timestamp}")
            success_count += 1

        except ValidationError as e:
            print(f"❌ Validation failed:")
            print(f"   Error count: {e.error_count()}")
            for error in e.errors():
                print(f"   - {error['loc']}: {error['msg']}")

        except Exception as e:
            print(f"❌ Other error: {e}")

        print()  # Empty line for readability

    print(f"📊 Results: {success_count}/{total_count} tests passed")

    if success_count == total_count:
        print("🎉 All tests passed! The Union validation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the error messages above.")


if __name__ == "__main__":
    test_validation()
