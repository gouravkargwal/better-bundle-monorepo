#!/usr/bin/env python3
"""
Raw Orders Generator - Generates realistic Shopify order data with proper relations
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from base_data_generator import BaseDataGenerator


class RawOrdersGenerator(BaseDataGenerator):
    """Generates raw Shopify order data with proper customer and product relations"""

    def __init__(self):
        super().__init__()
        self.order_statuses = ["open", "closed", "cancelled", "pending"]
        self.fulfillment_statuses = ["fulfilled", "partial", "unfulfilled", "restocked"]
        self.financial_statuses = [
            "pending",
            "authorized",
            "partially_paid",
            "paid",
            "partially_refunded",
            "refunded",
            "voided",
        ]
        self.currencies = ["USD", "EUR", "GBP", "CAD", "AUD"]
        self.payment_gateways = [
            "shopify_payments",
            "paypal",
            "stripe",
            "square",
            "manual",
        ]

    def generate_order_line_items(self, product_ids: List[str]) -> List[Dict[str, Any]]:
        """Generate realistic order line items using actual product IDs"""
        num_items = random.randint(1, 5)
        selected_products = random.sample(product_ids, min(num_items, len(product_ids)))

        line_items = []
        for product_id in selected_products:
            quantity = random.randint(1, 3)
            price = self.generate_price(10, 200)

            line_items.append(
                {
                    "id": self.generate_shopify_id(),
                    "product_id": product_id,
                    "variant_id": self.generate_shopify_id(),
                    "title": f"Product {product_id}",
                    "variant_title": random.choice(
                        ["Default", "Large", "Small", "Red", "Blue"]
                    ),
                    "sku": f"SKU-{product_id}",
                    "quantity": quantity,
                    "price": f"{price:.2f}",
                    "total_discount": f"{random.uniform(0, price * 0.2):.2f}",
                    "fulfillment_status": random.choice(self.fulfillment_statuses),
                    "requires_shipping": True,
                    "taxable": True,
                    "gift_card": False,
                    "name": f"Product {product_id} - {random.choice(['Default', 'Large', 'Small'])}",
                    "variant_inventory_management": "shopify",
                    "properties": [],
                    "product_exists": True,
                    "fulfillable_quantity": quantity,
                    "grams": random.randint(100, 2000),
                    "price_set": {
                        "shop_money": {
                            "amount": f"{price:.2f}",
                            "currency_code": "USD",
                        },
                        "presentment_money": {
                            "amount": f"{price:.2f}",
                            "currency_code": "USD",
                        },
                    },
                    "total_discount_set": {
                        "shop_money": {
                            "amount": f"{random.uniform(0, price * 0.2):.2f}",
                            "currency_code": "USD",
                        },
                        "presentment_money": {
                            "amount": f"{random.uniform(0, price * 0.2):.2f}",
                            "currency_code": "USD",
                        },
                    },
                    "discount_allocations": [],
                    "duties": [],
                    "admin_graphql_api_id": f"gid://shopify/LineItem/{self.generate_shopify_id()}",
                }
            )

        return line_items

    def generate_order_fulfillments(
        self, line_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate realistic order fulfillments"""
        if random.random() < 0.8:  # 80% chance of fulfillment
            fulfillment = {
                "id": self.generate_shopify_id(),
                "order_id": None,  # Will be set later
                "status": random.choice(["fulfilled", "partial", "unfulfilled"]),
                "created_at": self.generate_date_range(30).isoformat(),
                "service": "manual",
                "updated_at": self.generate_date_range(30).isoformat(),
                "tracking_company": random.choice(["UPS", "FedEx", "USPS", "DHL"]),
                "tracking_number": f"TRK{random.randint(100000000, 999999999)}",
                "tracking_numbers": [f"TRK{random.randint(100000000, 999999999)}"],
                "tracking_url": f"https://tracking.example.com/TRK{random.randint(100000000, 999999999)}",
                "tracking_urls": [
                    f"https://tracking.example.com/TRK{random.randint(100000000, 999999999)}"
                ],
                "receipt": {},
                "name": f"#{random.randint(1000, 9999)}",
                "admin_graphql_api_id": f"gid://shopify/Fulfillment/{self.generate_shopify_id()}",
                "line_items": line_items,
            }
            return [fulfillment]
        return []

    def generate_order_refunds(
        self, line_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate realistic order refunds"""
        if random.random() < 0.1:  # 10% chance of refund
            refund = {
                "id": self.generate_shopify_id(),
                "order_id": None,  # Will be set later
                "created_at": self.generate_date_range(30).isoformat(),
                "note": random.choice(
                    [
                        "Customer requested",
                        "Defective product",
                        "Wrong item",
                        "Late delivery",
                    ]
                ),
                "user_id": self.generate_shopify_id(),
                "processed_at": self.generate_date_range(30).isoformat(),
                "restock": random.choice([True, False]),
                "admin_graphql_api_id": f"gid://shopify/Refund/{self.generate_shopify_id()}",
                "refund_line_items": [],
                "transactions": [],
                "order_adjustments": [],
            }
            return [refund]
        return []

    def generate_single_order(
        self, shop_id: str, order_id: str, customer_id: str, product_ids: List[str]
    ) -> Dict[str, Any]:
        """Generate a single realistic order with proper relations"""
        # Generate dates
        created_at = self.generate_date_range(90)  # Last 90 days
        updated_at = created_at + timedelta(days=random.randint(1, 7))

        # Generate order data
        line_items = self.generate_order_line_items(product_ids)
        fulfillments = self.generate_order_fulfillments(line_items)
        refunds = self.generate_order_refunds(line_items)

        # Calculate totals
        subtotal = sum(float(item["price"]) * item["quantity"] for item in line_items)
        total_tax = subtotal * random.uniform(0.05, 0.15)  # 5-15% tax
        shipping = random.uniform(5, 25)
        total = subtotal + total_tax + shipping

        # Generate order
        order = {
            "id": order_id,
            "admin_graphql_api_id": f"gid://shopify/Order/{order_id}",
            "app_id": None,
            "browser_ip": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "buyer_accepts_marketing": random.choice([True, False]),
            "cancel_reason": None,
            "cancelled_at": None,
            "cart_token": str(uuid.uuid4()),
            "checkout_id": self.generate_shopify_id(),
            "checkout_token": str(uuid.uuid4()),
            "client_details": {
                "accept_language": "en-US,en;q=0.9",
                "browser_height": random.randint(600, 1200),
                "browser_ip": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                "browser_width": random.randint(800, 1920),
                "session_hash": str(uuid.uuid4()),
                "user_agent": random.choice(
                    [
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
                    ]
                ),
            },
            "closed_at": None,
            "confirmed": random.choice([True, False]),
            "contact_email": f"customer{random.randint(1000, 9999)}@example.com",
            "created_at": created_at.isoformat(),
            "currency": random.choice(self.currencies),
            "current_subtotal_price": f"{subtotal:.2f}",
            "current_subtotal_price_set": {
                "shop_money": {"amount": f"{subtotal:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{subtotal:.2f}",
                    "currency_code": "USD",
                },
            },
            "current_total_discounts": f"{random.uniform(0, subtotal * 0.1):.2f}",
            "current_total_discounts_set": {
                "shop_money": {
                    "amount": f"{random.uniform(0, subtotal * 0.1):.2f}",
                    "currency_code": "USD",
                },
                "presentment_money": {
                    "amount": f"{random.uniform(0, subtotal * 0.1):.2f}",
                    "currency_code": "USD",
                },
            },
            "current_total_duties_set": None,
            "current_total_price": f"{total:.2f}",
            "current_total_price_set": {
                "shop_money": {"amount": f"{total:.2f}", "currency_code": "USD"},
                "presentment_money": {"amount": f"{total:.2f}", "currency_code": "USD"},
            },
            "current_total_tax": f"{total_tax:.2f}",
            "current_total_tax_set": {
                "shop_money": {"amount": f"{total_tax:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{total_tax:.2f}",
                    "currency_code": "USD",
                },
            },
            "customer_locale": "en",
            "device_id": None,
            "discount_codes": [],
            "email": f"customer{random.randint(1000, 9999)}@example.com",
            "estimated_taxes": False,
            "financial_status": random.choice(self.financial_statuses),
            "fulfillment_status": random.choice(self.fulfillment_statuses),
            "fulfillments": fulfillments,
            "gateway": random.choice(self.payment_gateways),
            "landing_site": f"https://{shop_id}.myshopify.com/",
            "landing_site_ref": None,
            "location_id": None,
            "name": f"#{random.randint(1000, 9999)}",
            "note": random.choice(
                ["Rush order", "Gift wrapping", "Special instructions", None]
            ),
            "note_attributes": [],
            "number": random.randint(1000, 9999),
            "order_number": random.randint(1000, 9999),
            "order_status_url": f"https://{shop_id}.myshopify.com/orders/{order_id}/authenticate",
            "original_total_duties_set": None,
            "payment_gateway_names": [random.choice(self.payment_gateways)],
            "phone": self.generate_phone(),
            "presentment_currency": "USD",
            "processed_at": created_at.isoformat(),
            "processing_method": "direct",
            "reference": None,
            "referring_site": random.choice(
                [
                    "https://google.com",
                    "https://facebook.com",
                    "https://instagram.com",
                    "https://twitter.com",
                    "direct",
                    "email",
                ]
            ),
            "source_identifier": None,
            "source_name": "web",
            "source_url": None,
            "subtotal_price": f"{subtotal:.2f}",
            "subtotal_price_set": {
                "shop_money": {"amount": f"{subtotal:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{subtotal:.2f}",
                    "currency_code": "USD",
                },
            },
            "tags": ", ".join(
                random.sample(
                    ["rush", "gift", "bulk", "wholesale", "retail"],
                    random.randint(0, 2),
                )
            ),
            "tax_lines": [],
            "taxes_included": False,
            "test": False,
            "token": str(uuid.uuid4()),
            "total_discounts": f"{random.uniform(0, subtotal * 0.1):.2f}",
            "total_discounts_set": {
                "shop_money": {
                    "amount": f"{random.uniform(0, subtotal * 0.1):.2f}",
                    "currency_code": "USD",
                },
                "presentment_money": {
                    "amount": f"{random.uniform(0, subtotal * 0.1):.2f}",
                    "currency_code": "USD",
                },
            },
            "total_line_items_price": f"{subtotal:.2f}",
            "total_line_items_price_set": {
                "shop_money": {"amount": f"{subtotal:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{subtotal:.2f}",
                    "currency_code": "USD",
                },
            },
            "total_outstanding": "0.00",
            "total_price": f"{total:.2f}",
            "total_price_set": {
                "shop_money": {"amount": f"{total:.2f}", "currency_code": "USD"},
                "presentment_money": {"amount": f"{total:.2f}", "currency_code": "USD"},
            },
            "total_price_usd": f"{total:.2f}",
            "total_shipping_price_set": {
                "shop_money": {"amount": f"{shipping:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{shipping:.2f}",
                    "currency_code": "USD",
                },
            },
            "total_tax": f"{total_tax:.2f}",
            "total_tax_set": {
                "shop_money": {"amount": f"{total_tax:.2f}", "currency_code": "USD"},
                "presentment_money": {
                    "amount": f"{total_tax:.2f}",
                    "currency_code": "USD",
                },
            },
            "total_tip_received": "0.00",
            "total_weight": random.randint(100, 5000),
            "updated_at": updated_at.isoformat(),
            "user_id": self.generate_shopify_id(),
            "billing_address": self.generate_address(),
            "customer": {
                "id": customer_id,
                "email": f"customer{random.randint(1000, 9999)}@example.com",
                "accepts_marketing": random.choice([True, False]),
                "created_at": self.generate_date_range(365).isoformat(),
                "updated_at": self.generate_date_range(30).isoformat(),
                "first_name": random.choice(self.first_names),
                "last_name": random.choice(self.last_names),
                "orders_count": random.randint(1, 20),
                "state": "enabled",
                "total_spent": f"{random.uniform(100, 5000):.2f}",
                "last_order_id": None,
                "note": None,
                "verified_email": True,
                "multipass_identifier": None,
                "tax_exempt": False,
                "phone": self.generate_phone(),
                "tags": "",
                "last_order_name": None,
                "currency": "USD",
                "accepts_marketing_updated_at": self.generate_date_range(
                    365
                ).isoformat(),
                "marketing_opt_in_level": "single_opt_in",
                "tax_exemptions": [],
                "admin_graphql_api_id": f"gid://shopify/Customer/{customer_id}",
                "default_address": self.generate_address(),
            },
            "discount_applications": self.generate_discount_applications(),
            "fulfillments": fulfillments,
            "line_items": line_items,
            "payment_terms": None,
            "refunds": refunds,
            "shipping_address": self.generate_address(),
        }

        return order

    def generate_orders_for_shop(
        self,
        shop_id: str,
        customer_ids: List[str],
        product_ids: List[str],
        num_orders: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Generate orders for a specific shop with proper relations"""
        orders = []

        for i in range(num_orders):
            order_id = self.generate_shopify_id()
            customer_id = random.choice(customer_ids)

            order = self.generate_single_order(
                shop_id, order_id, customer_id, product_ids
            )

            # Create raw order record
            raw_order = {
                "id": f"raw_order_{shop_id}_{order_id}",
                "shopId": shop_id,
                "payload": order,
                # Align extractedAt with Shopify updated_at
                "extractedAt": order["updated_at"],
                "shopifyId": order_id,
                "shopifyCreatedAt": order["created_at"],
                "shopifyUpdatedAt": order["updated_at"],
            }

            orders.append(raw_order)

        return orders

    def generate_all_orders(
        self,
        shops: List[Dict[str, str]],
        customers_data: List[Dict],
        products_data: List[Dict],
        orders_per_shop: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Generate orders for all shops with proper relations"""
        all_orders = []

        for shop in shops:
            shop_id = shop["id"]
            print(f"Generating {orders_per_shop} orders for shop {shop_id}...")

            # Get customer and product IDs for this shop
            shop_customers = [c for c in customers_data if c["shopId"] == shop_id]
            shop_products = [p for p in products_data if p["shopId"] == shop_id]

            customer_ids = [c["payload"]["id"] for c in shop_customers]
            product_ids = [p["payload"]["id"] for p in shop_products]

            if not customer_ids or not product_ids:
                print(f"Warning: No customers or products found for shop {shop_id}")
                continue

            orders = self.generate_orders_for_shop(
                shop_id, customer_ids, product_ids, orders_per_shop
            )
            all_orders.extend(orders)

        print(f"Generated {len(all_orders)} total orders")
        return all_orders


if __name__ == "__main__":
    # Test the generator
    generator = RawOrdersGenerator()
    shops = [
        {"id": "shop_123", "name": "Fashion Store"},
        {"id": "shop_456", "name": "Electronics Hub"},
        {"id": "shop_789", "name": "Home & Garden"},
    ]

    # Mock data for testing
    customers_data = [{"shopId": "shop_123", "payload": {"id": "123456789"}}]
    products_data = [{"shopId": "shop_123", "payload": {"id": "987654321"}}]

    orders = generator.generate_all_orders(
        shops, customers_data, products_data, 10
    )  # Small test
    print(f"Generated {len(orders)} orders")
    print("Sample order:", json.dumps(orders[0], indent=2))
