#!/usr/bin/env python3
"""
Raw Customers Generator - Generates realistic Shopify customer data
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from base_data_generator import BaseDataGenerator


class RawCustomersGenerator(BaseDataGenerator):
    """Generates raw Shopify customer data"""

    def __init__(self):
        super().__init__()
        self.customer_notes = [
            "VIP customer - high value",
            "Prefers email communication",
            "Frequent buyer",
            "New customer",
            "Returning customer",
            "Bulk order customer",
            "International shipping",
            "Local pickup preferred",
            "Seasonal buyer",
            "Discount code user",
        ]

        self.customer_tags = [
            "vip",
            "frequent-buyer",
            "new-customer",
            "returning",
            "bulk-order",
            "international",
            "local",
            "seasonal",
            "discount-user",
            "newsletter",
            "premium",
            "wholesale",
            "retail",
            "online-only",
            "store-visitor",
        ]

    def generate_customer_addresses(self) -> List[Dict[str, Any]]:
        """Generate realistic customer addresses"""
        addresses = []
        num_addresses = random.randint(1, 3)

        for i in range(num_addresses):
            address = self.generate_address()
            address.update(
                {
                    "id": self.generate_shopify_id(),
                    "customer_id": None,  # Will be set later
                    "first_name": address["first_name"],
                    "last_name": address["last_name"],
                    "company": address["company"],
                    "address1": address["address1"],
                    "address2": address["address2"],
                    "city": address["city"],
                    "province": address["province"],
                    "country": address["country"],
                    "zip": address["zip"],
                    "phone": address["phone"],
                    "name": f"{address['first_name']} {address['last_name']}",
                    "province_code": address["province"],
                    "country_code": "US",
                    "country_name": "United States",
                    "default": i == 0,  # First address is default
                }
            )
            addresses.append(address)

        return addresses

    def generate_customer_metafields(self) -> List[Dict[str, Any]]:
        """Generate realistic customer metafields"""
        metafields = []

        # Common metafields
        if random.random() < 0.7:  # 70% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "birthday",
                    "value": self.generate_date_range(365 * 50).strftime("%Y-%m-%d"),
                    "type": "single_line_text_field",
                    "description": "Customer birthday",
                }
            )

        if random.random() < 0.5:  # 50% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "preferred_contact",
                    "value": random.choice(["email", "phone", "sms"]),
                    "type": "single_line_text_field",
                    "description": "Preferred contact method",
                }
            )

        if random.random() < 0.3:  # 30% chance
            metafields.append(
                {
                    "id": self.generate_shopify_id(),
                    "namespace": "custom",
                    "key": "loyalty_points",
                    "value": str(random.randint(0, 5000)),
                    "type": "number_integer",
                    "description": "Loyalty points balance",
                }
            )

        return metafields

    def generate_single_customer(
        self, shop_id: str, customer_id: str
    ) -> Dict[str, Any]:
        """Generate a single realistic customer"""
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        email = self.generate_email(first_name, last_name)

        # Generate dates
        created_at = self.generate_date_range(365)
        updated_at = created_at + timedelta(days=random.randint(1, 30))

        # Generate customer data
        total_spent = self.generate_price(0, 5000)
        order_count = random.randint(0, 50)
        last_order_date = self.generate_date_range(90) if order_count > 0 else None

        # Generate addresses and metafields
        addresses = self.generate_customer_addresses()
        metafields = self.generate_customer_metafields()

        # Set customer_id references
        for address in addresses:
            address["customer_id"] = customer_id

        customer = {
            "id": customer_id,
            "email": email,
            "accepts_marketing": random.choice([True, False]),
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
            "first_name": first_name,
            "last_name": last_name,
            "orders_count": order_count,
            "state": random.choice(["enabled", "disabled", "invited", "declined"]),
            "total_spent": f"{total_spent:.2f}",
            "last_order_id": self.generate_shopify_id() if order_count > 0 else None,
            "note": (
                random.choice(self.customer_notes) if random.random() < 0.3 else None
            ),
            "verified_email": random.choice([True, False]),
            "multipass_identifier": None,
            "tax_exempt": random.choice([True, False]),
            "phone": self.generate_phone(),
            "tags": ", ".join(random.sample(self.customer_tags, random.randint(1, 4))),
            "last_order_name": (
                f"#{random.randint(1000, 9999)}" if order_count > 0 else None
            ),
            "currency": "USD",
            "accepts_marketing_updated_at": created_at.isoformat(),
            "marketing_opt_in_level": random.choice(
                ["single_opt_in", "confirmed_opt_in", "unknown"]
            ),
            "tax_exemptions": [],
            "admin_graphql_api_id": f"gid://shopify/Customer/{customer_id}",
            "default_address": addresses[0] if addresses else None,
            "addresses": addresses,
            "metafields": metafields,
        }

        return customer

    def generate_customers_for_shop(
        self, shop_id: str, num_customers: int = 1000
    ) -> List[Dict[str, Any]]:
        """Generate customers for a specific shop"""
        customers = []

        for i in range(num_customers):
            customer_id = self.generate_shopify_id()
            customer = self.generate_single_customer(shop_id, customer_id)

            # Create raw customer record
            raw_customer = {
                "id": f"raw_customer_{shop_id}_{customer_id}",
                "shopId": shop_id,
                "payload": customer,
                # Align extractedAt with Shopify updated_at
                "extractedAt": customer["updated_at"],
                "shopifyId": customer_id,
                "shopifyCreatedAt": customer["created_at"],
                "shopifyUpdatedAt": customer["updated_at"],
            }

            customers.append(raw_customer)

        return customers

    def generate_all_customers(
        self, shops: List[Dict[str, str]], customers_per_shop: int = 1000
    ) -> List[Dict[str, Any]]:
        """Generate customers for all shops"""
        all_customers = []

        for shop in shops:
            shop_id = shop["id"]
            print(f"Generating {customers_per_shop} customers for shop {shop_id}...")

            customers = self.generate_customers_for_shop(shop_id, customers_per_shop)
            all_customers.extend(customers)

        print(f"Generated {len(all_customers)} total customers")
        return all_customers


if __name__ == "__main__":
    # Test the generator
    generator = RawCustomersGenerator()
    shops = [
        {"id": "shop_123", "name": "Fashion Store"},
        {"id": "shop_456", "name": "Electronics Hub"},
        {"id": "shop_789", "name": "Home & Garden"},
    ]

    customers = generator.generate_all_customers(shops, 10)  # Small test
    print(f"Generated {len(customers)} customers")
    print("Sample customer:", json.dumps(customers[0], indent=2))
