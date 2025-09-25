"""
Shopify Development Store Seeder with Collections
Creates products, customers, collections, and orders in a Shopify development store.

Usage:
  - Env vars: export SHOP_DOMAIN=your-store.myshopify.com SHOPIFY_ACCESS_TOKEN=shpat_...
  - Or CLI:   python seed_shopify_with_collections.py --shop your-store.myshopify.com --token shpat_...
"""

import asyncio
import sys
import os
import argparse
import requests
import time
import random
from typing import Dict, Any, List, Optional, Tuple

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.scripts.seed_data_generators.base_generator import BaseGenerator
from app.scripts.seed_data_generators.product_generator import ProductGenerator
from app.scripts.seed_data_generators.customer_generator import CustomerGenerator
from app.scripts.seed_data_generators.order_generator import OrderGenerator


class ShopifySeederWithCollections:
    """Seeds products, customers, collections, and orders into a Shopify store."""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2024-01"
        self.base_url = f"https://{shop_domain}/admin/api/{self.api_version}"

        # Generators
        self.base_generator = BaseGenerator(shop_domain)
        self.product_generator = ProductGenerator(shop_domain)
        self.customer_generator = CustomerGenerator(shop_domain)
        self.order_generator = OrderGenerator(shop_domain)

        # Track created resources
        self.created_products: Dict[str, Dict[str, Any]] = {}
        self.created_customers: Dict[str, Dict[str, Any]] = {}
        self.created_orders: Dict[str, Dict[str, Any]] = {}
        self.created_collections: Dict[str, Dict[str, Any]] = {}

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        # Add delay to respect rate limits
        if retry_count > 0:
            delay = min(
                2**retry_count + random.uniform(0, 2), 15
            )  # Exponential backoff with jitter, max 15s
            print(f"    ⏳ Rate limited, waiting {delay:.1f}s...")
            time.sleep(delay)
        else:
            # Longer delay between requests to avoid hitting rate limits
            time.sleep(1.0)

        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                resp = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                resp = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()
            return resp.json() if resp.content else {}

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and retry_count < 3:  # Rate limited
                return self._request(method, endpoint, data, retry_count + 1)
            else:
                # Add detailed error logging
                error_details = (
                    f"Status: {e.response.status_code}, Response: {e.response.text}"
                )
                print(f"    🔍 Detailed error: {error_details}")
                raise e

    async def create_products(self) -> Dict[str, Dict[str, Any]]:
        print("📦 Creating products...")
        products = self.product_generator.generate_products()
        for i, product_data in enumerate(products, 1):
            try:
                payload = self._convert_product(product_data)
                res = self._request("POST", "products.json", {"product": payload})
                product = res["product"]
                self.created_products[f"product_{i}"] = {
                    "id": product["id"],
                    "handle": product["handle"],
                    "variants": [v["id"] for v in product["variants"]],
                }
                print(f"  ✅ Product: {product['title']} ({product['id']})")
            except Exception as e:
                print(f"  ❌ Product {i} failed: {e}")
        return self.created_products

    async def create_customers(self) -> Dict[str, Dict[str, Any]]:
        print("👥 Creating customers...")
        customers = self.customer_generator.generate_customers()
        for i, customer_data in enumerate(customers, 1):
            try:
                # Make email unique by adding timestamp
                import time

                original_email = customer_data["email"]
                unique_email = f"{original_email.split('@')[0]}+{int(time.time())}@{original_email.split('@')[1]}"
                customer_data["email"] = unique_email

                payload = self._convert_customer(customer_data)
                res = self._request("POST", "customers.json", {"customer": payload})
                customer = res["customer"]
                self.created_customers[f"customer_{i}"] = {
                    "id": customer["id"],
                    "email": customer["email"],
                }
                print(f"  ✅ Customer: {customer['email']} ({customer['id']})")
            except Exception as e:
                print(f"  ❌ Customer {i} failed: {e}")
        return self.created_customers

    def _generate_collections_from_products(self) -> List[Dict[str, Any]]:
        # Build two simple collections grouping created products
        product_ids = [p["id"] for p in self.created_products.values()]
        import time

        timestamp = int(time.time())
        collections = []
        collections.append(
            {
                "title": "Summer Essentials",
                "handle": f"summer-essentials-{timestamp}",
                "body_html": "Perfect for summer - clothing and accessories",
                "product_ids": product_ids[:10],
            }
        )
        collections.append(
            {
                "title": "Tech Gear",
                "handle": f"tech-gear-{timestamp}",
                "body_html": "Latest technology and electronics",
                "product_ids": product_ids[10:],
            }
        )
        return collections

    async def create_collections(self) -> Dict[str, Dict[str, Any]]:
        print("📚 Creating collections and linking products...")
        if not self.created_products:
            print("  ⚠️ No products available to add to collections")
            return {}

        collections = self._generate_collections_from_products()
        for i, c in enumerate(collections, 1):
            try:
                # Create custom collection
                res = self._request(
                    "POST",
                    "custom_collections.json",
                    {
                        "custom_collection": {
                            "title": c["title"],
                            "handle": c["handle"],
                            "body_html": c["body_html"],
                            "published": True,
                        }
                    },
                )
                collection = res["custom_collection"]
                self.created_collections[f"collection_{i}"] = {
                    "id": collection["id"],
                    "title": collection["title"],
                }
                print(f"  ✅ Collection: {collection['title']} ({collection['id']})")

                # Link products via collects
                for pid in c["product_ids"]:
                    try:
                        self._request(
                            "POST",
                            "collects.json",
                            {
                                "collect": {
                                    "product_id": pid,
                                    "collection_id": collection["id"],
                                }
                            },
                        )
                    except Exception as e:
                        print(
                            f"    ⚠️ Failed to link product {pid} -> collection {collection['id']}: {e}"
                        )
            except Exception as e:
                print(f"  ❌ Collection '{c['title']}' failed: {e}")
                # Add detailed error logging for collections too
                if hasattr(e, "response"):
                    print(f"    🔍 Collection error details: {e.response.text}")
        return self.created_collections

    async def create_orders(self) -> Dict[str, Dict[str, Any]]:
        print("📋 Creating orders...")
        if not self.created_products or not self.created_customers:
            print("  ⚠️ Need products and customers before creating orders")
            return {}

        customer_ids = [c["id"] for c in self.created_customers.values()]
        variant_ids: List[str] = []
        product_ids: List[str] = []
        for p in self.created_products.values():
            product_ids.append(p["id"])
            variant_ids.extend(p["variants"])

        # Generate fewer orders to avoid rate limits
        orders = self.order_generator.generate_orders(
            customer_ids, variant_ids, product_ids
        )

        # Limit to 2 orders to be extra safe with rate limits
        limited_orders = orders[:2]

        # Check if we should skip orders due to previous rate limit issues
        print(
            f"  📊 Creating {len(limited_orders)} orders (limited to avoid rate limits)"
        )

        rate_limit_failures = 0
        max_rate_limit_failures = 2

        for i, order_data in enumerate(limited_orders, 1):
            try:
                # Make customer email unique for orders
                if order_data.get("customer") and order_data["customer"].get("email"):
                    original_email = order_data["customer"]["email"]
                    unique_email = f"{original_email.split('@')[0]}+order{i}@{original_email.split('@')[1]}"
                    order_data["customer"]["email"] = unique_email

                # Extra delay for orders due to strict rate limits
                if i > 1:
                    print(f"    ⏳ Waiting 3s before creating order {i}...")
                    time.sleep(3)

                payload = self._convert_order(order_data)
                res = self._request("POST", "orders.json", {"order": payload})
                order = res["order"]
                self.created_orders[f"order_{i}"] = {
                    "id": order["id"],
                    "name": order["name"],
                }
                print(f"  ✅ Order: {order['name']} ({order['id']})")
            except Exception as e:
                print(f"  ❌ Order {i} failed: {e}")
                # If we hit rate limits, wait longer before next order
                if "429" in str(e) or "rate limit" in str(e).lower():
                    rate_limit_failures += 1
                    print(
                        f"    ⏳ Rate limit hit ({rate_limit_failures}/{max_rate_limit_failures}), waiting 10s before next order..."
                    )
                    time.sleep(10)

                    # If we've hit rate limits too many times, skip remaining orders
                    if rate_limit_failures >= max_rate_limit_failures:
                        print(
                            f"    ⚠️ Too many rate limit failures, skipping remaining orders"
                        )
                        break
        return self.created_orders

    def _convert_product(self, product_data: Dict) -> Dict[str, Any]:
        product = product_data
        variants = []
        for v_edge in product["variants"]["edges"]:
            v = v_edge["node"]
            variants.append(
                {
                    "title": v["title"],
                    "price": v["price"],
                    "sku": v["sku"],
                    "inventory_quantity": v["inventoryQuantity"],
                    "compare_at_price": v.get("compareAtPrice"),
                    "taxable": v["taxable"],
                    "inventory_policy": v["inventoryPolicy"].lower(),
                    "requires_shipping": True,
                    "fulfillment_service": "manual",
                }
            )
        images = []
        for m_edge in product["media"]["edges"]:
            node = m_edge["node"]
            if "image" in node:
                images.append(
                    {"src": node["image"]["url"], "alt": node["image"]["altText"]}
                )
        return {
            "title": product["title"],
            "body_html": product["description"],
            "vendor": product["vendor"],
            "product_type": product["productType"],
            "handle": product["handle"],
            "tags": ",".join(product.get("tags", [])),
            "variants": variants,
            "images": images,
            "status": "active",
            "published": True,
            "published_at": product["createdAt"],
        }

    def _convert_customer(self, customer_data: Dict) -> Dict[str, Any]:
        c = customer_data
        address = None
        if c.get("defaultAddress"):
            a = c["defaultAddress"]
            address = {
                "first_name": c["firstName"],
                "last_name": c["lastName"],
                "address1": a["address1"],
                "city": a["city"],
                "province": a["province"],
                "country": a["country"],
                "zip": a["zip"],
                "phone": a["phone"],
                "default": True,
            }
        return {
            "first_name": c["firstName"],
            "last_name": c["lastName"],
            "email": c["email"],
            "verified_email": c["verifiedEmail"],
            "state": c["state"].lower(),
            "tags": ",".join(c.get("tags", [])),
            "addresses": [address] if address else [],
        }

    def _convert_order(self, order_data: Dict) -> Dict[str, Any]:
        o = order_data
        line_items = []
        for li_edge in o["lineItems"]["edges"]:
            li = li_edge["node"]
            line_items.append(
                {
                    "variant_id": li["variant"]["id"],
                    "quantity": li["quantity"],
                    "price": li["originalUnitPriceSet"]["shopMoney"]["amount"],
                }
            )
        customer = {}
        if o.get("customer"):
            customer = {"id": o["customer"]["id"], "email": o["customer"].get("email")}
        return {
            "line_items": line_items,
            "customer": customer,
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "currency": o["currencyCode"],
            "total_price": o["totalPriceSet"]["shopMoney"]["amount"],
            "subtotal_price": o["subtotalPriceSet"]["shopMoney"]["amount"],
            "total_tax": o["totalTaxSet"]["shopMoney"]["amount"],
            "taxes_included": True,
            "order_number": o["name"],
            "note": o.get("note", ""),
            "tags": ",".join(o.get("tags", [])),
            "created_at": o["createdAt"],
        }

    async def run(self) -> bool:
        print(f"🚀 Seeding Shopify store: {self.shop_domain}")
        await self.create_products()
        await self.create_customers()
        await self.create_collections()
        await self.create_orders()

        print("\n🎯 Seeding Summary:")
        print(f"  ✅ Products:   {len(self.created_products)}")
        print(f"  ✅ Customers:  {len(self.created_customers)}")
        print(f"  ✅ Collections:{len(self.created_collections)}")
        print(f"  ✅ Orders:     {len(self.created_orders)}")
        print(f"  🔗 Admin URL: https://{self.shop_domain}/admin")
        return bool(self.created_products and self.created_customers)


async def main() -> bool:
    seeder = ShopifySeederWithCollections(
        "vnsaid.myshopify.com", "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"
    )
    return await seeder.run()


if __name__ == "__main__":
    asyncio.run(main())
