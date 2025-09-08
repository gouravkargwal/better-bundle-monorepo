#!/usr/bin/env python3
"""
Raw Behavioral Events Generator - Generates realistic behavioral event data
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from base_data_generator import BaseDataGenerator


class RawBehavioralEventsGenerator(BaseDataGenerator):
    """Generates raw behavioral event data with proper relations"""

    def __init__(self):
        super().__init__()
        # Restrict to supported Web Pixel event names
        self.event_types = [
            "page_viewed",
            "product_viewed",
            "product_added_to_cart",
            "collection_viewed",
            "search_submitted",
            "checkout_started",
            "checkout_completed",
        ]

        self.page_types = [
            "home",
            "product",
            "collection",
            "cart",
            "checkout",
            "search",
            "about",
            "contact",
            "blog",
            "faq",
            "shipping",
            "returns",
        ]

        self.search_terms = [
            "shirt",
            "dress",
            "shoes",
            "bag",
            "watch",
            "phone",
            "laptop",
            "headphones",
            "book",
            "gift",
            "sale",
            "new",
            "premium",
            "cheap",
            "red",
            "blue",
            "black",
            "white",
            "large",
            "small",
            "medium",
        ]

    def generate_page_view_event(
        self, customer_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Generate Shopify Web Pixel-compatible page_viewed event"""
        href = f"https://your-store.myshopify.com/{random.choice(self.page_types)}"
        return {
            "id": f"e_{uuid.uuid4()}",
            "name": "page_viewed",
            "timestamp": self.generate_date_range(30).isoformat() + "Z",
            "clientId": str(uuid.uuid4()),
            "seq": random.randint(1, 10),
            "type": "standard",
            "context": {
                "document": {
                    "location": {
                        "href": href,
                        "pathname": "/" + href.split("/")[-1],
                        "search": "",
                    },
                    "referrer": "https://your-store.myshopify.com/",
                    "title": "Page - Your Store",
                },
            },
            "data": {},
        }

    def generate_product_view_event(
        self, customer_id: str, session_id: str, product_id: str
    ) -> Dict[str, Any]:
        """Generate Shopify Web Pixel-compatible product_viewed event"""
        href = f"https://your-store.myshopify.com/products/example-product"
        return {
            "id": f"e_{uuid.uuid4()}",
            "name": "product_viewed",
            "timestamp": self.generate_date_range(30).isoformat() + "Z",
            "clientId": str(uuid.uuid4()),
            "seq": random.randint(1, 10),
            "type": "standard",
            "context": {
                "document": {
                    "location": {
                        "href": href,
                        "pathname": "/products/example-product",
                        "search": "",
                    },
                    "referrer": "https://your-store.myshopify.com/collections/all",
                    "title": "Example Product - Your Store",
                },
            },
            "data": {
                "productVariant": {
                    "id": f"gid://shopify/ProductVariant/{product_id}",
                    "title": "Variant Title",
                    "untranslatedTitle": "Variant Title",
                    "sku": f"SKU-{product_id}",
                    "price": {
                        "amount": round(self.generate_price(10, 200), 2),
                        "currencyCode": "USD",
                    },
                    "image": {"src": "https://cdn.shopify.com/s/files/example.jpg"},
                    "product": {
                        "id": f"gid://shopify/Product/{product_id}",
                        "title": f"Product {product_id}",
                        "untranslatedTitle": f"Product {product_id}",
                        "type": random.choice(["Clothing", "Electronics"]),
                        "vendor": random.choice(self.brands),
                        "url": f"/products/{product_id}",
                    },
                }
            },
        }

    def generate_add_to_cart_event(
        self, customer_id: str, session_id: str, product_id: str
    ) -> Dict[str, Any]:
        """Generate Shopify Web Pixel-compatible product_added_to_cart event"""
        href = f"https://your-store.myshopify.com/products/{product_id}"
        return {
            "id": f"e_{uuid.uuid4()}",
            "name": "product_added_to_cart",
            "timestamp": self.generate_date_range(30).isoformat() + "Z",
            "clientId": str(uuid.uuid4()),
            "seq": random.randint(1, 10),
            "type": "standard",
            "context": {
                "document": {
                    "location": {
                        "href": href,
                        "pathname": "/products/example",
                        "search": "",
                    }
                }
            },
            "data": {
                "cartLine": {
                    "quantity": random.randint(1, 3),
                    "merchandise": {
                        "id": f"gid://shopify/ProductVariant/{product_id}",
                        "title": "Variant Title",
                        "untranslatedTitle": "Variant Title",
                        "sku": f"SKU-{product_id}",
                        "image": {"src": "https://cdn.shopify.com/s/files/example.jpg"},
                        "price": {
                            "amount": round(self.generate_price(10, 200), 2),
                            "currencyCode": "USD",
                        },
                        "product": {
                            "id": f"gid://shopify/Product/{product_id}",
                            "title": f"Product {product_id}",
                            "untranslatedTitle": f"Product {product_id}",
                            "type": random.choice(["Clothing", "Electronics"]),
                            "url": f"/products/{product_id}",
                            "vendor": random.choice(self.brands),
                        },
                    },
                    "cost": {
                        "totalAmount": {
                            "amount": round(self.generate_price(20, 400), 2),
                            "currencyCode": "USD",
                        }
                    },
                }
            },
        }

    def generate_purchase_event(
        self, customer_id: str, session_id: str, product_id: str, order_id: str
    ) -> Dict[str, Any]:
        """Generate Shopify Web Pixel-compatible checkout_completed event"""
        href = "https://your-store.myshopify.com/checkout/thank-you"
        subtotal = self.generate_price(50, 200)
        total = round(subtotal + self.generate_price(1, 5), 2)
        return {
            "id": f"e_{uuid.uuid4()}",
            "name": "checkout_completed",
            "timestamp": self.generate_date_range(30).isoformat() + "Z",
            "clientId": str(uuid.uuid4()),
            "seq": random.randint(1, 10),
            "type": "standard",
            "context": {
                "document": {
                    "location": {
                        "href": href,
                        "pathname": "/checkout/thank-you",
                        "search": "?key=abc",
                    },
                    "referrer": "https://your-store.myshopify.com/checkout/step_3",
                },
            },
            "data": {
                "checkout": {
                    "id": f"gid://shopify/Checkout/{order_id}?key=abc",
                    "token": str(uuid.uuid4()).replace("-", "")[:20],
                    "email": "customer@example.com",
                    "currencyCode": "USD",
                    "buyerAcceptsEmailMarketing": bool(random.getrandbits(1)),
                    "buyerAcceptsSmsMarketing": bool(random.getrandbits(1)),
                    "subtotalPrice": {"amount": subtotal, "currencyCode": "USD"},
                    "totalPrice": {"amount": total, "currencyCode": "USD"},
                    "totalTax": {
                        "amount": round(total - subtotal, 2),
                        "currencyCode": "USD",
                    },
                    "discountsAmount": {
                        "amount": round(self.generate_price(0, 10), 2),
                        "currencyCode": "USD",
                    },
                    "shippingLine": {"price": {"amount": 0.0, "currencyCode": "USD"}},
                    "billingAddress": {
                        "address1": "123 Main Street",
                        "city": "Anytown",
                        "country": "United States",
                        "countryCode": "US",
                        "province": "CA",
                        "provinceCode": "CA",
                        "zip": "12345",
                    },
                    "shippingAddress": {
                        "address1": "123 Main Street",
                        "city": "Anytown",
                        "country": "United States",
                        "countryCode": "US",
                        "province": "CA",
                        "provinceCode": "CA",
                        "zip": "12345",
                    },
                    "discountApplications": [],
                    "lineItems": [
                        {
                            "id": f"gid://shopify/CheckoutLineItem/{self.generate_shopify_id()}",
                            "title": f"Product {product_id}",
                            "quantity": 1,
                            "finalLinePrice": {
                                "amount": subtotal,
                                "currencyCode": "USD",
                            },
                            "discountAllocations": [],
                            "variant": {
                                "id": f"gid://shopify/ProductVariant/{product_id}",
                                "title": "Default",
                                "sku": f"SKU-{product_id}",
                                "price": {"amount": subtotal, "currencyCode": "USD"},
                                "product": {
                                    "id": f"gid://shopify/Product/{product_id}",
                                    "title": f"Product {product_id}",
                                },
                            },
                        }
                    ],
                    "transactions": [
                        {
                            "amount": {"amount": total, "currencyCode": "USD"},
                            "gateway": "shopify_payments",
                            "paymentMethod": {"name": "Visa", "type": "creditCard"},
                        }
                    ],
                    "order": {
                        "id": f"gid://shopify/Order/{order_id}",
                        "isFirstOrder": bool(random.getrandbits(1)),
                    },
                }
            },
        }

    def generate_search_event(
        self, customer_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Generate Shopify Web Pixel-compatible search_submitted event"""
        term = random.choice(self.search_terms)
        return {
            "id": f"e_{uuid.uuid4()}",
            "name": "search_submitted",
            "timestamp": self.generate_date_range(30).isoformat() + "Z",
            "clientId": str(uuid.uuid4()),
            "seq": random.randint(1, 10),
            "type": "standard",
            "context": {
                "document": {
                    "location": {
                        "href": f"https://your-store.myshopify.com/search?q={term}",
                        "pathname": "/search",
                        "search": f"?q={term}",
                    },
                    "referrer": "https://your-store.myshopify.com/",
                    "title": f"Search results for '{term}' - Your Store",
                }
            },
            "data": {"searchResult": {"query": term, "productVariants": []}},
        }

    def generate_behavioral_events_for_shop(
        self,
        shop_id: str,
        customer_ids: List[str],
        product_ids: List[str],
        num_events: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Generate behavioral events for a specific shop"""
        events = []

        for i in range(num_events):
            customer_id = random.choice(customer_ids)
            session_id = str(uuid.uuid4())
            event_type = random.choice(self.event_types)

            # Generate event based on type
            if event_type == "page_view":
                event = self.generate_page_view_event(customer_id, session_id)
            elif event_type == "product_view":
                product_id = random.choice(product_ids)
                event = self.generate_product_view_event(
                    customer_id, session_id, product_id
                )
            elif event_type == "add_to_cart":
                product_id = random.choice(product_ids)
                event = self.generate_add_to_cart_event(
                    customer_id, session_id, product_id
                )
            elif event_type == "purchase":
                product_id = random.choice(product_ids)
                order_id = self.generate_shopify_id()
                event = self.generate_purchase_event(
                    customer_id, session_id, product_id, order_id
                )
            elif event_type == "search":
                event = self.generate_search_event(customer_id, session_id)

            # Create raw behavioral event record
            raw_event = {
                "id": f"raw_behavioral_event_{shop_id}_{i}",
                "shopId": shop_id,
                "payload": event,
                "receivedAt": datetime.now().isoformat(),
            }

            events.append(raw_event)

        return events

    def generate_all_behavioral_events(
        self,
        shops: List[Dict[str, str]],
        customers_data: List[Dict],
        products_data: List[Dict],
        events_per_shop: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Generate behavioral events for all shops"""
        all_events = []

        for shop in shops:
            shop_id = shop["id"]
            print(
                f"Generating {events_per_shop} behavioral events for shop {shop_id}..."
            )

            # Get customer and product IDs for this shop
            shop_customers = [c for c in customers_data if c["shopId"] == shop_id]
            shop_products = [p for p in products_data if p["shopId"] == shop_id]

            customer_ids = [c["payload"]["id"] for c in shop_customers]
            product_ids = [p["payload"]["id"] for p in shop_products]

            if not customer_ids or not product_ids:
                print(f"Warning: No customers or products found for shop {shop_id}")
                continue

            events = self.generate_behavioral_events_for_shop(
                shop_id, customer_ids, product_ids, events_per_shop
            )
            all_events.extend(events)

        print(f"Generated {len(all_events)} total behavioral events")
        return all_events


if __name__ == "__main__":
    # Test the generator
    generator = RawBehavioralEventsGenerator()
    shops = [
        {"id": "shop_123", "name": "Fashion Store"},
        {"id": "shop_456", "name": "Electronics Hub"},
        {"id": "shop_789", "name": "Home & Garden"},
    ]

    # Mock data for testing
    customers_data = [{"shopId": "shop_123", "payload": {"id": "123456789"}}]
    products_data = [{"shopId": "shop_123", "payload": {"id": "987654321"}}]

    events = generator.generate_all_behavioral_events(
        shops, customers_data, products_data, 100
    )  # Small test
    print(f"Generated {len(events)} behavioral events")
    print("Sample event:", json.dumps(events[0], indent=2))
