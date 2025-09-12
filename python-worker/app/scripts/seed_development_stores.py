"""
Development Store Seeder - Seeds realistic data into multiple Shopify development stores.
Uses configuration file for easy management of multiple stores.
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


class DevelopmentStoreSeeder:
    """Seeds realistic data into Shopify development stores using configuration."""

    def __init__(self, config_path: str = "development_stores_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.seeding_options = self.config.get("seeding_options", {})
        self.data_customization = self.config.get("data_customization", {})

        print("🎯 Development Store Seeder Initialized")
        print(f"📁 Config loaded from: {config_path}")
        print(f"🏪 Found {len(self.config['development_stores'])} configured stores")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        config_file = os.path.join(os.path.dirname(__file__), self.config_path)

        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Configuration file not found: {config_file}")
            print("   Please create the configuration file first.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def _make_api_request(
        self,
        shop_domain: str,
        access_token: str,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make authenticated API request to Shopify."""
        api_version = "2024-01"
        url = f"https://{shop_domain}/admin/api/{api_version}/{endpoint}"
        headers = {
            "X-Shopify-Access-Token": access_token,
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
            print(f"❌ API request failed for {shop_domain}: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    async def seed_store(self, store_config: Dict[str, Any]) -> bool:
        """Seed a single development store."""
        store_name = store_config["name"]
        shop_domain = store_config["domain"]
        access_token = store_config["access_token"]

        print(f"\n🏪 Seeding store: {store_name}")
        print(f"   Domain: {shop_domain}")
        print(f"   Description: {store_config.get('description', 'N/A')}")
        print("-" * 60)

        try:
            # Initialize generators for this store
            base_generator = BaseGenerator(shop_domain)
            product_generator = ProductGenerator(shop_domain)
            customer_generator = CustomerGenerator(shop_domain)
            order_generator = OrderGenerator(shop_domain)

            # Track created resources
            created_products = {}
            created_customers = {}
            created_orders = {}

            # Step 1: Seed products or get existing ones
            if self.seeding_options.get("create_products", True):
                print("📦 Seeding products...")
                products = product_generator.generate_products()

                # Limit products if specified
                product_count = self.data_customization.get(
                    "product_count", len(products)
                )
                products = products[:product_count]

                for i, product_data in enumerate(products, 1):
                    try:
                        shopify_product = self._convert_to_shopify_product(product_data)
                        response = self._make_api_request(
                            shop_domain,
                            access_token,
                            "POST",
                            "products.json",
                            {"product": shopify_product},
                        )
                        created_product = response["product"]

                        created_products[f"product_{i}"] = {
                            "id": created_product["id"],
                            "handle": created_product["handle"],
                            "variants": [v["id"] for v in created_product["variants"]],
                        }

                        print(f"  ✅ Created: {created_product['title']}")

                    except Exception as e:
                        print(f"  ❌ Failed to create product {i}: {e}")
                        continue
            else:
                print("📦 Getting existing products...")
                try:
                    response = self._make_api_request(
                        shop_domain, access_token, "GET", "products.json?limit=50"
                    )
                    existing_products = response.get("products", [])

                    for i, product in enumerate(existing_products, 1):
                        created_products[f"product_{i}"] = {
                            "id": product["id"],
                            "handle": product["handle"],
                            "variants": [v["id"] for v in product["variants"]],
                        }

                    print(f"  ✅ Found {len(existing_products)} existing products")
                except Exception as e:
                    print(f"  ❌ Failed to get existing products: {e}")

            # Step 2: Seed customers or get existing ones
            if self.seeding_options.get("create_customers", True):
                print("👥 Seeding customers...")
                customers = customer_generator.generate_customers()

                # Limit customers if specified
                customer_count = self.data_customization.get(
                    "customer_count", len(customers)
                )
                customers = customers[:customer_count]

                for i, customer_data in enumerate(customers, 1):
                    try:
                        shopify_customer = self._convert_to_shopify_customer(
                            customer_data
                        )
                        response = self._make_api_request(
                            shop_domain,
                            access_token,
                            "POST",
                            "customers.json",
                            {"customer": shopify_customer},
                        )
                        created_customer = response["customer"]

                        created_customers[f"customer_{i}"] = {
                            "id": created_customer["id"],
                            "email": created_customer["email"],
                        }

                        print(f"  ✅ Created: {created_customer['email']}")

                    except Exception as e:
                        print(f"  ❌ Failed to create customer {i}: {e}")
                        continue
            else:
                print("👥 Getting existing customers...")
                try:
                    response = self._make_api_request(
                        shop_domain, access_token, "GET", "customers.json?limit=50"
                    )
                    existing_customers = response.get("customers", [])

                    for i, customer in enumerate(existing_customers, 1):
                        created_customers[f"customer_{i}"] = {
                            "id": customer["id"],
                            "email": customer["email"],
                        }

                    print(f"  ✅ Found {len(existing_customers)} existing customers")
                except Exception as e:
                    print(f"  ❌ Failed to get existing customers: {e}")

            # Step 3: Seed orders
            if (
                self.seeding_options.get("create_orders", True)
                and created_products
                and created_customers
            ):
                print("📋 Seeding orders...")

                # Get IDs for order generation
                customer_ids = [c["id"] for c in created_customers.values()]
                variant_ids = []
                for product in created_products.values():
                    variant_ids.extend(product["variants"])

                orders = order_generator.generate_orders(customer_ids, variant_ids)

                # Limit orders if specified
                order_count = self.data_customization.get("order_count", len(orders))
                orders = orders[:order_count]

                for i, order_data in enumerate(orders, 1):
                    try:
                        shopify_order = self._convert_to_shopify_order(order_data)
                        response = self._make_api_request(
                            shop_domain,
                            access_token,
                            "POST",
                            "orders.json",
                            {"order": shopify_order},
                        )
                        created_order = response["order"]

                        created_orders[f"order_{i}"] = {
                            "id": created_order["id"],
                            "name": created_order["name"],
                        }

                        print(f"  ✅ Created: {created_order['name']}")

                    except Exception as e:
                        print(f"  ❌ Failed to create order {i}: {e}")
                        continue

            # Summary for this store
            print(f"\n📊 {store_name} Summary:")
            print(f"  ✅ Products: {len(created_products)}")
            print(f"  ✅ Customers: {len(created_customers)}")
            print(f"  ✅ Orders: {len(created_orders)}")
            print(f"  🔗 Admin URL: https://{shop_domain}/admin")

            return len(created_products) > 0 and len(created_customers) > 0

        except Exception as e:
            print(f"❌ Failed to seed {store_name}: {e}")
            return False

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

    async def run_seeding(self) -> bool:
        """Run seeding for all enabled development stores."""
        print("🚀 Starting Development Store Seeding")
        print("=" * 60)

        enabled_stores = [
            store
            for store in self.config["development_stores"]
            if store.get("enabled", False)
        ]

        if not enabled_stores:
            print("⚠️  No enabled stores found in configuration!")
            print(
                "   Please set 'enabled': true for at least one store in the config file."
            )
            return False

        print(f"📋 Found {len(enabled_stores)} enabled stores to seed")

        success_count = 0
        for store_config in enabled_stores:
            success = await self.seed_store(store_config)
            if success:
                success_count += 1

        print(
            f"\n🎯 Final Summary: {success_count}/{len(enabled_stores)} stores seeded successfully"
        )

        if success_count > 0:
            print(
                "\n🎉 Seeding completed! Your development stores now have realistic data."
            )
            print("   You can now test your recommendation system with this data.")

        return success_count > 0


async def main():
    """Main entry point."""
    seeder = DevelopmentStoreSeeder()
    success = await seeder.run_seeding()
    return success


if __name__ == "__main__":
    asyncio.run(main())
