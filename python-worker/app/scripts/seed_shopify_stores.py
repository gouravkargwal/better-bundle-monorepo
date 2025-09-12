"""
Shopify Store Seeder - Seeds realistic data directly into development stores via Shopify API.
"""

import asyncio
import sys
import os
import json
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.scripts.seed_data_generators.base_generator import BaseGenerator
from app.scripts.seed_data_generators.product_generator import ProductGenerator
from app.scripts.seed_data_generators.customer_generator import CustomerGenerator
from app.scripts.seed_data_generators.order_generator import OrderGenerator


class ShopifyStoreSeeder:
    """Seeds realistic data directly into Shopify development stores."""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2024-01"
        self.base_url = f"https://{shop_domain}/admin/api/{self.api_version}"

        # Initialize generators with the actual shop domain
        self.base_generator = BaseGenerator(shop_domain)
        self.product_generator = ProductGenerator(shop_domain)
        self.customer_generator = CustomerGenerator(shop_domain)
        self.order_generator = OrderGenerator(shop_domain)

        # Use the same dynamic IDs across all generators
        self.dynamic_ids = self.base_generator.dynamic_ids

        # Track created resources for relationships
        self.created_products = {}
        self.created_customers = {}
        self.created_orders = {}

        print(f"🎯 Initializing seeder for: {shop_domain}")
        print("🎲 Generated Dynamic IDs for this run:")
        for key, value in sorted(self.dynamic_ids.items()):
            print(f"  {key}: {value}")
        print()

    def _make_api_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request to Shopify."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {}

        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    async def seed_products(self) -> Dict[str, str]:
        """Seed products into the Shopify store."""
        print("📦 Seeding products...")
        products = self.product_generator.generate_products()
        created_products = {}

        for i, product_data in enumerate(products, 1):
            try:
                # Convert our generated data to Shopify API format
                shopify_product = self._convert_to_shopify_product(product_data)

                # Create product via API
                response = self._make_api_request(
                    "POST", "products.json", {"product": shopify_product}
                )
                created_product = response["product"]

                created_products[f"product_{i}"] = {
                    "id": created_product["id"],
                    "handle": created_product["handle"],
                    "variants": [v["id"] for v in created_product["variants"]],
                }

                print(
                    f"  ✅ Created product: {created_product['title']} (ID: {created_product['id']})"
                )

            except Exception as e:
                print(f"  ❌ Failed to create product {i}: {e}")
                continue

        self.created_products = created_products
        return created_products

    async def seed_customers(self) -> Dict[str, str]:
        """Seed customers into the Shopify store."""
        print("👥 Seeding customers...")
        customers = self.customer_generator.generate_customers()
        created_customers = {}

        for i, customer_data in enumerate(customers, 1):
            try:
                # Convert our generated data to Shopify API format
                shopify_customer = self._convert_to_shopify_customer(customer_data)

                # Create customer via API
                response = self._make_api_request(
                    "POST", "customers.json", {"customer": shopify_customer}
                )
                created_customer = response["customer"]

                created_customers[f"customer_{i}"] = {
                    "id": created_customer["id"],
                    "email": created_customer["email"],
                }

                print(
                    f"  ✅ Created customer: {created_customer['email']} (ID: {created_customer['id']})"
                )

            except Exception as e:
                print(f"  ❌ Failed to create customer {i}: {e}")
                continue

        self.created_customers = created_customers
        return created_customers

    async def seed_orders(self) -> Dict[str, str]:
        """Seed orders into the Shopify store."""
        print("📋 Seeding orders...")

        # Get customer and product IDs for order generation
        customer_ids = [c["id"] for c in self.created_customers.values()]
        variant_ids = []
        for product in self.created_products.values():
            variant_ids.extend(product["variants"])

        orders = self.order_generator.generate_orders(customer_ids, variant_ids)
        created_orders = {}

        for i, order_data in enumerate(orders, 1):
            try:
                # Convert our generated data to Shopify API format
                shopify_order = self._convert_to_shopify_order(order_data)

                # Create order via API
                response = self._make_api_request(
                    "POST", "orders.json", {"order": shopify_order}
                )
                created_order = response["order"]

                created_orders[f"order_{i}"] = {
                    "id": created_order["id"],
                    "name": created_order["name"],
                }

                print(
                    f"  ✅ Created order: {created_order['name']} (ID: {created_order['id']})"
                )

            except Exception as e:
                print(f"  ❌ Failed to create order {i}: {e}")
                continue

        self.created_orders = created_orders
        return created_orders

    def _convert_to_shopify_product(self, product_data: Dict) -> Dict[str, Any]:
        """Convert our generated product data to Shopify API format."""
        product = product_data["product"]

        # Build variants
        variants = []
        for variant_edge in product["variants"]["edges"]:
            variant_node = variant_edge["node"]
            variants.append(
                {
                    "title": variant_node["title"],
                    "price": variant_node["price"],
                    "sku": variant_node["sku"],
                    "inventory_quantity": variant_node["inventoryQuantity"],
                    "compare_at_price": variant_node.get("compareAtPrice"),
                    "taxable": variant_node["taxable"],
                    "inventory_policy": variant_node["inventoryPolicy"].lower(),
                    "requires_shipping": True,
                    "fulfillment_service": "manual",
                }
            )

        # Build images
        images = []
        for media_edge in product["media"]["edges"]:
            media_node = media_edge["node"]
            if "image" in media_node:
                images.append(
                    {
                        "src": media_node["image"]["url"],
                        "alt": media_node["image"]["altText"],
                    }
                )

        return {
            "title": product["title"],
            "body_html": product["description"],
            "vendor": product["vendor"],
            "product_type": product["productType"],
            "handle": product["handle"],
            "tags": ",".join(product["tags"]),
            "variants": variants,
            "images": images,
            "status": "active",
            "published": True,
            "published_at": product["createdAt"],
        }

    def _convert_to_shopify_customer(self, customer_data: Dict) -> Dict[str, Any]:
        """Convert our generated customer data to Shopify API format."""
        customer = customer_data["customer"]

        # Build address if exists
        address = None
        if customer.get("defaultAddress"):
            addr = customer["defaultAddress"]
            address = {
                "first_name": customer["firstName"],
                "last_name": customer["lastName"],
                "address1": addr["address1"],
                "city": addr["city"],
                "province": addr["province"],
                "country": addr["country"],
                "zip": addr["zip"],
                "phone": addr["phone"],
                "default": True,
            }

        return {
            "first_name": customer["firstName"],
            "last_name": customer["lastName"],
            "email": customer["email"],
            "verified_email": customer["verifiedEmail"],
            "state": customer["state"].lower(),
            "tags": ",".join(customer["tags"]),
            "addresses": [address] if address else [],
        }

    def _convert_to_shopify_order(self, order_data: Dict) -> Dict[str, Any]:
        """Convert our generated order data to Shopify API format."""
        order = order_data["order"]

        # Build line items
        line_items = []
        for line_item_edge in order["lineItems"]["edges"]:
            line_item_node = line_item_edge["node"]
            line_items.append(
                {
                    "variant_id": line_item_node["variant"]["id"],
                    "quantity": line_item_node["quantity"],
                    "price": line_item_node["originalUnitPriceSet"]["shopMoney"][
                        "amount"
                    ],
                }
            )

        # Build customer data
        customer_data = {}
        if order.get("customer"):
            customer_data = {
                "id": order["customer"]["id"],
                "email": order["customer"]["email"],
            }

        return {
            "line_items": line_items,
            "customer": customer_data,
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "currency": order["currencyCode"],
            "total_price": order["totalPriceSet"]["shopMoney"]["amount"],
            "subtotal_price": order["subtotalPriceSet"]["shopMoney"]["amount"],
            "total_tax": order["totalTaxSet"]["shopMoney"]["amount"],
            "taxes_included": True,
            "order_number": order["name"],
            "note": order.get("note", ""),
            "tags": ",".join(order.get("tags", [])),
            "created_at": order["createdAt"],
        }

    async def run_complete_seeding(self) -> bool:
        """Run the complete seeding process."""
        print(f"🚀 Starting Shopify store seeding for: {self.shop_domain}")
        print("🎯 This will create realistic products, customers, and orders")

        try:
            # Step 1: Seed products
            print("\n📊 Step 1: Seeding products...")
            products_result = await self.seed_products()

            # Step 2: Seed customers
            print("\n📊 Step 2: Seeding customers...")
            customers_result = await self.seed_customers()

            # Step 3: Seed orders
            print("\n📊 Step 3: Seeding orders...")
            orders_result = await self.seed_orders()

            # Summary
            print("\n🎯 Seeding Summary:")
            print(f"  ✅ Products created: {len(products_result)}")
            print(f"  ✅ Customers created: {len(customers_result)}")
            print(f"  ✅ Orders created: {len(orders_result)}")

            if products_result and customers_result:
                print(f"\n🎉 Successfully seeded {self.shop_domain}!")
                print(f"   Visit: https://{self.shop_domain}/admin/products")
                return True
            else:
                print(f"\n❌ Seeding failed for {self.shop_domain}")
                return False

        except Exception as e:
            print(f"\n❌ Seeding failed with error: {e}")
            return False


async def main():
    """Main entry point for seeding development stores."""

    # Development store configurations
    # You can add multiple stores here
    development_stores = [
        {
            "domain": "your-dev-store.myshopify.com",  # Replace with your actual dev store
            "access_token": "your-access-token-here",  # Replace with your actual access token
        },
        # Add more stores as needed
    ]

    print("🎯 Shopify Development Store Seeder")
    print("=" * 50)

    if not development_stores or not development_stores[0]["domain"].startswith(
        "your-dev"
    ):
        print("⚠️  Please configure your development store details in the script first!")
        print(
            "   Edit the 'development_stores' list with your actual store domain and access token."
        )
        return False

    success_count = 0
    for store_config in development_stores:
        print(f"\n🏪 Processing store: {store_config['domain']}")
        print("-" * 40)

        seeder = ShopifyStoreSeeder(
            shop_domain=store_config["domain"],
            access_token=store_config["access_token"],
        )

        success = await seeder.run_complete_seeding()
        if success:
            success_count += 1

    print(
        f"\n🎯 Final Summary: {success_count}/{len(development_stores)} stores seeded successfully"
    )
    return success_count > 0


if __name__ == "__main__":
    asyncio.run(main())
