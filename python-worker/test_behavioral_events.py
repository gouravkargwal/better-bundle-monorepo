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
        "id": "e_b15b565a-5282-4f73-af5c-097561f38e6e",
        "name": "product_viewed",
        "timestamp": "2025-09-05T13:35:00.000Z",
        "clientId": "b5a939f5-4e00-4e2b-8b29-9e8c1b3f2e1a",
        "seq": 4,
        "type": "standard",
        "context": {
            "document": {
                "location": {
                    "href": "https://your-store.myshopify.com/products/example-hoodie",
                    "pathname": "/products/example-hoodie",
                    "search": "",
                },
                "referrer": "https://your-store.myshopify.com/collections/all",
                "title": "Example Hoodie - Your Store",
            },
            "navigator": {
                "cookieEnabled": True,
                "language": "en-US",
                "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            },
            "window": {
                "innerHeight": 800,
                "innerWidth": 1440,
                "outerHeight": 900,
                "outerWidth": 1540,
            },
        },
        "data": {
            "productVariant": {
                "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0VmFyaWFudC8zNzgzNjk2NTQ5OTI3",
                "title": "Unisex Hoodie - Grey / Small",
                "untranslatedTitle": "Unisex Hoodie - Grey / Small",
                "sku": "UH-GS-101",
                "price": {"amount": 45.00, "currencyCode": "USD"},
                "image": {
                    "src": "https://cdn.shopify.com/s/files/1/0000/0000/products/hoodie-grey-small.jpg",
                },
                "product": {
                    "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0LzgyMTA4MjM1NzU4MjM",
                    "title": "Unisex Hoodie",
                    "untranslatedTitle": "Unisex Hoodie",
                    "type": "Clothing",
                    "vendor": "My Clothing Store",
                    "url": "/products/unisex-hoodie",
                },
            },
        },
    },
    # 3. ProductAddedToCartEvent
    {
        "id": "e_8a7c6f5e-4d3b-2c1a-9f8e-7d6c5b4a3c2b",
        "name": "product_added_to_cart",
        "timestamp": "2025-09-05T13:30:00.000Z",
        "clientId": "b5a939f5-4e00-4e2b-8b29-9e8c1b3f2e1a",
        "seq": 3,
        "type": "standard",
        "context": {
            "document": {
                "location": {
                    "href": "https://your-store.myshopify.com/products/example-product-hoodie",
                    "pathname": "/products/example-product-hoodie",
                    "search": "",
                },
                "referrer": "https://your-store.myshopify.com/collections/all",
                "title": "Example Hoodie - Your Store",
            },
            "navigator": {
                "cookieEnabled": True,
                "language": "en-US",
                "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            },
            "window": {
                "innerHeight": 800,
                "innerWidth": 1440,
                "outerHeight": 900,
                "outerWidth": 1540,
            },
        },
        "data": {
            "cartLine": {
                "quantity": 1,
                "merchandise": {
                    "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0VmFyaWFudC8zNzgzNjk2NTQ5OTI3",
                    "title": "Unisex Hoodie - Grey / Small",
                    "untranslatedTitle": "Unisex Hoodie - Grey / Small",
                    "sku": "UH-GS-101",
                    "image": {
                        "src": "https://cdn.shopify.com/s/files/1/0000/0000/products/hoodie-grey-small.jpg",
                    },
                    "price": {"amount": 45.00, "currencyCode": "USD"},
                    "product": {
                        "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0LzgyMTA4MjM1NzU4MjM",
                        "title": "Unisex Hoodie",
                        "untranslatedTitle": "Unisex Hoodie",
                        "type": "T-Shirt",
                        "url": "/products/unisex-hoodie",
                        "vendor": "My Clothing Store",
                    },
                },
                "cost": {
                    "totalAmount": {"amount": 45.00, "currencyCode": "USD"},
                },
            },
        },
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
    # 7. CheckoutCompletedEvent
    {
        "id": "e_b15b565a-5282-4f73-af5c-097561f38e6e",
        "name": "checkout_completed",
        "timestamp": "2025-09-05T13:00:00.000Z",
        "clientId": "b5a939f5-4e00-4e2b-8b29-9e8c1b3f2e1a",
        "seq": 2,
        "type": "standard",
        "context": {
            "document": {
                "location": {
                    "href": "https://your-store.myshopify.com/checkout/thank-you",
                    "pathname": "/checkout/thank-you",
                    "search": "?key=2ba4ba4ba4",
                },
                "referrer": "https://your-store.myshopify.com/checkout/step_3",
            },
            "customer": None,
            "shop": {
                "id": "67040441",
                "domain": "your-store.myshopify.com",
                "plan": "basic",
            },
        },
        "data": {
            "checkout": {
                "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9DaGVja291dC83NzgzNjk2NTQ5OTI3P2tleT0yYmE0YmE0YmE0",
                "token": "2ba4ba4ba452c92a95c935",
                "email": "customer@example.com",
                "currencyCode": "USD",
                "buyerAcceptsEmailMarketing": True,
                "buyerAcceptsSmsMarketing": False,
                "subtotalPrice": {"amount": 140.00, "currencyCode": "USD"},
                "totalPrice": {"amount": 142.00, "currencyCode": "USD"},
                "totalTax": {"amount": 10.00, "currencyCode": "USD"},
                "discountsAmount": {"amount": 8.00, "currencyCode": "USD"},
                "shippingLine": {"price": {"amount": 0.00, "currencyCode": "USD"}},
                "billingAddress": {
                    "address1": "123 Main Street",
                    "city": "Anytown",
                    "country": "United States",
                    "countryCode": "US",
                    "province": "California",
                    "provinceCode": "CA",
                    "zip": "12345",
                },
                "shippingAddress": {
                    "address1": "123 Main Street",
                    "city": "Anytown",
                    "country": "United States",
                    "countryCode": "US",
                    "province": "California",
                    "provinceCode": "CA",
                    "zip": "12345",
                },
                "discountApplications": [
                    {
                        "type": "DISCOUNT_CODE",
                        "title": "WELCOME",
                        "value": {"amount": 8.00, "currencyCode": "USD"},
                        "targetType": "LINE_ITEM",
                        "allocationMethod": "ACROSS",
                    }
                ],
                "lineItems": [
                    {
                        "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9DaGVja291dExpbmVJdGVtLzEyMzQ1Njc4OTc4MjE",
                        "title": "Unisex Hoodie - Grey / Small",
                        "quantity": 1,
                        "finalLinePrice": {"amount": 42.00, "currencyCode": "USD"},
                        "discountAllocations": [
                            {
                                "amount": {"amount": 3.00, "currencyCode": "USD"},
                                "discountApplication": {
                                    "title": "WELCOME",
                                    "type": "DISCOUNT_CODE",
                                },
                            }
                        ],
                        "variant": {
                            "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0VmFyaWFudC8zNzgzNjk2NTQ5OTI3",
                            "title": "Grey / Small",
                            "sku": "UH-GS-101",
                            "price": {"amount": 45.00, "currencyCode": "USD"},
                            "product": {
                                "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0LzgyMTA4MjM1NzU4MjM",
                                "title": "Unisex Hoodie",
                            },
                        },
                    },
                    {
                        "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9DaGVja291dExpbmVJdGVtLzEyMzQ1Njc4OTc4MjI",
                        "title": "Running Shoes - Red / 10",
                        "quantity": 1,
                        "finalLinePrice": {"amount": 98.00, "currencyCode": "USD"},
                        "discountAllocations": [
                            {
                                "amount": {"amount": 5.00, "currencyCode": "USD"},
                                "discountApplication": {
                                    "title": "WELCOME",
                                    "type": "DISCOUNT_CODE",
                                },
                            }
                        ],
                        "variant": {
                            "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0VmFyaWFudC80NTY5NTg0MzQzMDYzNQ",
                            "title": "Red / 10",
                            "sku": "RS-RED-10",
                            "price": {"amount": 103.00, "currencyCode": "USD"},
                            "product": {
                                "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9Qcm9kdWN0Lzc2MzI5NDMzNDMwNjM1",
                                "title": "Running Shoes",
                            },
                        },
                    },
                ],
                "transactions": [
                    {
                        "amount": {"amount": 142.00, "currencyCode": "USD"},
                        "gateway": "shopify_payments",
                        "paymentMethod": {"name": "Visa", "type": "creditCard"},
                    }
                ],
                "order": {
                    "id": "Z2lkOi8vbm9kZS8vU2hvcGlmeS9PcmRlci80MzYzNDM2MjcyNDUz",
                    "isFirstOrder": True,
                },
            }
        },
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
