#!/usr/bin/env python3
"""
Test script for the complete adapter system
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_test_events():
    """Create test events for all interaction types"""
    return {
        "product_viewed": {
            "id": "test_1",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "product_viewed",
            "createdAt": "2024-01-01T10:00:00Z",
            "metadata": {
                "data": {
                    "productVariant": {
                        "product": {
                            "id": "product_123",
                            "title": "Test Product",
                            "price": 29.99,
                            "type": "clothing",
                            "vendor": "Test Vendor",
                            "url": "/products/test-product",
                        }
                    }
                },
                "page_url": "/products/test-product",
                "referrer": "https://google.com",
                "user_agent": "Mozilla/5.0...",
            },
        },
        "product_added_to_cart": {
            "id": "test_2",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "product_added_to_cart",
            "createdAt": "2024-01-01T10:05:00Z",
            "metadata": {
                "data": {
                    "cartLine": {
                        "merchandise": {
                            "product": {
                                "id": "product_123",
                                "title": "Test Product",
                                "price": 29.99,
                            }
                        },
                        "quantity": 2,
                    }
                }
            },
        },
        "product_removed_from_cart": {
            "id": "test_3",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "product_removed_from_cart",
            "createdAt": "2024-01-01T10:10:00Z",
            "metadata": {
                "data": {
                    "cartLine": {
                        "merchandise": {
                            "product": {
                                "id": "product_123",
                                "title": "Test Product",
                                "price": 29.99,
                            }
                        },
                        "quantity": 1,
                    }
                }
            },
        },
        "page_viewed": {
            "id": "test_4",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "page_viewed",
            "createdAt": "2024-01-01T10:15:00Z",
            "metadata": {
                "data": {
                    "pageType": "product",
                    "url": "/products/test-product",
                    "title": "Test Product Page",
                    "referrer": "https://google.com",
                }
            },
        },
        "cart_viewed": {
            "id": "test_5",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "cart_viewed",
            "createdAt": "2024-01-01T10:20:00Z",
            "metadata": {
                "data": {
                    "cart": {
                        "id": "cart_123",
                        "totalPrice": {"amount": "59.98"},
                        "totalQuantity": 2,
                        "lines": [
                            {
                                "merchandise": {
                                    "product": {
                                        "id": "product_123",
                                        "title": "Test Product",
                                    }
                                }
                            }
                        ],
                    }
                }
            },
        },
        "collection_viewed": {
            "id": "test_6",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "collection_viewed",
            "createdAt": "2024-01-01T10:25:00Z",
            "metadata": {
                "data": {
                    "collection": {
                        "id": "collection_123",
                        "title": "Test Collection",
                        "handle": "test-collection",
                        "productsCount": 10,
                        "products": [{"id": "product_123", "title": "Test Product"}],
                    }
                }
            },
        },
        "search_submitted": {
            "id": "test_7",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "search_submitted",
            "createdAt": "2024-01-01T10:30:00Z",
            "metadata": {
                "data": {
                    "query": "test product",
                    "filters": {"type": "clothing"},
                    "resultsCount": 5,
                    "results": [{"id": "product_123", "title": "Test Product"}],
                }
            },
        },
        "checkout_started": {
            "id": "test_8",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "checkout_started",
            "createdAt": "2024-01-01T10:35:00Z",
            "metadata": {
                "data": {
                    "checkout": {
                        "id": "checkout_123",
                        "totalPrice": {"amount": "59.98"},
                        "totalQuantity": 2,
                        "lineItems": [
                            {
                                "variant": {
                                    "product": {
                                        "id": "product_123",
                                        "title": "Test Product",
                                    }
                                }
                            }
                        ],
                    }
                }
            },
        },
        "checkout_completed": {
            "id": "test_9",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "checkout_completed",
            "createdAt": "2024-01-01T10:40:00Z",
            "metadata": {
                "data": {
                    "order": {
                        "id": "order_123",
                        "orderNumber": "1001",
                        "totalPrice": {"amount": "59.98"},
                        "totalQuantity": 2,
                        "lineItems": [
                            {
                                "variant": {
                                    "product": {
                                        "id": "product_123",
                                        "title": "Test Product",
                                    }
                                }
                            }
                        ],
                    }
                }
            },
        },
        "customer_linked": {
            "id": "test_10",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "customer_linked",
            "createdAt": "2024-01-01T10:45:00Z",
            "metadata": {
                "data": {
                    "customer": {
                        "id": "customer_456",
                        "email": "test@example.com",
                        "firstName": "Test",
                        "lastName": "User",
                        "ordersCount": 5,
                        "totalSpent": {"amount": "299.95"},
                    }
                }
            },
        },
        "recommendation_viewed": {
            "id": "test_11",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "recommendation_viewed",
            "createdAt": "2024-01-01T10:50:00Z",
            "metadata": {
                "data": {
                    "type": "related_products",
                    "position": "product_page",
                    "widget": "product_recommendations",
                    "algorithm": "collaborative_filtering",
                    "confidence": 0.85,
                    "recommendations": [
                        {"id": "product_456", "title": "Related Product"}
                    ],
                }
            },
        },
        "recommendation_clicked": {
            "id": "test_12",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "recommendation_clicked",
            "createdAt": "2024-01-01T10:55:00Z",
            "metadata": {
                "data": {
                    "product": {
                        "id": "product_456",
                        "title": "Related Product",
                        "price": 39.99,
                    },
                    "type": "related_products",
                    "position": 1,
                    "widget": "product_recommendations",
                    "algorithm": "collaborative_filtering",
                    "confidence": 0.85,
                    "clickPosition": 1,
                }
            },
        },
        "recommendation_add_to_cart": {
            "id": "test_13",
            "sessionId": "session_123",
            "customerId": "customer_456",
            "shopId": "shop_789",
            "interactionType": "recommendation_add_to_cart",
            "createdAt": "2024-01-01T11:00:00Z",
            "metadata": {
                "data": {
                    "cartLine": {
                        "merchandise": {
                            "product": {
                                "id": "product_456",
                                "title": "Related Product",
                                "price": 39.99,
                            }
                        },
                        "quantity": 1,
                    },
                    "type": "related_products",
                    "position": 1,
                    "widget": "product_recommendations",
                    "algorithm": "collaborative_filtering",
                    "confidence": 0.85,
                }
            },
        },
    }


async def test_adapter_system():
    """Test the complete adapter system"""
    logger.info("🧪 Testing Complete Adapter System")

    factory = InteractionEventAdapterFactory()
    test_events = create_test_events()

    results = {
        "total_events": len(test_events),
        "successful_extractions": 0,
        "failed_extractions": 0,
        "product_events": 0,
        "cart_events": 0,
        "view_events": 0,
        "purchase_events": 0,
        "search_events": 0,
        "recommendation_events": 0,
        "details": [],
    }

    for event_type, event_data in test_events.items():
        logger.info(f"\n🔍 Testing {event_type} event...")

        try:
            # Test adapter extraction
            extracted_data = factory.extract_data_from_event(event_data)
            product_id = factory.extract_product_id(event_data)
            customer_id = factory.extract_customer_id(event_data)

            # Test event classification
            is_product = factory.is_product_event(event_data)
            is_cart = factory.is_cart_event(event_data)
            is_view = factory.is_view_event(event_data)
            is_purchase = factory.is_purchase_event(event_data)
            is_search = factory.is_search_event(event_data)
            is_recommendation = factory.is_recommendation_event(event_data)

            success = product_id is not None or event_type in ["customer_linked"]

            if success:
                results["successful_extractions"] += 1
            else:
                results["failed_extractions"] += 1

            if is_product:
                results["product_events"] += 1
            if is_cart:
                results["cart_events"] += 1
            if is_view:
                results["view_events"] += 1
            if is_purchase:
                results["purchase_events"] += 1
            if is_search:
                results["search_events"] += 1
            if is_recommendation:
                results["recommendation_events"] += 1

            results["details"].append(
                {
                    "event_type": event_type,
                    "success": success,
                    "product_id": product_id,
                    "customer_id": customer_id,
                    "is_product": is_product,
                    "is_cart": is_cart,
                    "is_view": is_view,
                    "is_purchase": is_purchase,
                    "is_search": is_search,
                    "is_recommendation": is_recommendation,
                    "extracted_data_keys": (
                        list(extracted_data.keys()) if extracted_data else []
                    ),
                }
            )

            logger.info(f"✅ {event_type}: {'SUCCESS' if success else 'FAILED'}")
            logger.info(f"   Product ID: {product_id}")
            logger.info(f"   Customer ID: {customer_id}")
            logger.info(
                f"   Classifications: Product={is_product}, Cart={is_cart}, View={is_view}, Purchase={is_purchase}, Search={is_search}, Recommendation={is_recommendation}"
            )

        except Exception as e:
            logger.error(f"❌ Error testing {event_type}: {str(e)}")
            results["failed_extractions"] += 1
            results["details"].append(
                {"event_type": event_type, "success": False, "error": str(e)}
            )

    # Print summary
    logger.info(f"\n📊 ADAPTER SYSTEM TEST RESULTS:")
    logger.info(f"   Total Events: {results['total_events']}")
    logger.info(f"   Successful Extractions: {results['successful_extractions']}")
    logger.info(f"   Failed Extractions: {results['failed_extractions']}")
    logger.info(
        f"   Success Rate: {(results['successful_extractions'] / results['total_events']) * 100:.1f}%"
    )

    logger.info(f"\n📈 EVENT CLASSIFICATION:")
    logger.info(f"   Product Events: {results['product_events']}")
    logger.info(f"   Cart Events: {results['cart_events']}")
    logger.info(f"   View Events: {results['view_events']}")
    logger.info(f"   Purchase Events: {results['purchase_events']}")
    logger.info(f"   Search Events: {results['search_events']}")
    logger.info(f"   Recommendation Events: {results['recommendation_events']}")

    # Show failed extractions
    failed_events = [
        detail for detail in results["details"] if not detail.get("success", True)
    ]
    if failed_events:
        logger.info(f"\n❌ FAILED EXTRACTIONS:")
        for detail in failed_events:
            logger.info(
                f"   {detail['event_type']}: {detail.get('error', 'No product ID extracted')}"
            )

    return results


if __name__ == "__main__":
    asyncio.run(test_adapter_system())
