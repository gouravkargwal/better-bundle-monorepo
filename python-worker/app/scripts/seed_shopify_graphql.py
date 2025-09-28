"""
Shopify Development Store Seeder using GraphQL API
Creates products, customers, collections, and orders in a Shopify development store using GraphQL.

Usage:
  - Env vars: export SHOP_DOMAIN=your-store.myshopify.com SHOPIFY_ACCESS_TOKEN=shpat_...
  - Or CLI:   python seed_shopify_graphql.py --shop your-store.myshopify.com --token shpat_...
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


class ShopifyGraphQLSeeder:
    """Seeds products, customers, collections, and orders into a Shopify store using GraphQL."""

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

    def _graphql_request(
        self,
        query: str,
        variables: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

        # Add delay to respect rate limits
        if retry_count > 0:
            delay = min(
                2**retry_count + random.uniform(0, 1), 10
            )  # Exponential backoff with jitter
            print(f"    ⏳ Rate limited, waiting {delay:.1f}s...")
            time.sleep(delay)
        else:
            # Small delay between requests to avoid hitting rate limits
            time.sleep(0.5)

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = requests.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [
                    error.get("message", "Unknown error") for error in result["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and retry_count < 3:  # Rate limited
                return self._graphql_request(query, variables, retry_count + 1)
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
                # Convert product data to GraphQL format
                variants = []
                for v_edge in product_data["variants"]["edges"]:
                    v = v_edge["node"]
                    variants.append(
                        {
                            "title": v["title"],
                            "price": v["price"],
                            "sku": v["sku"],
                            "inventoryQuantity": v["inventoryQuantity"],
                            "compareAtPrice": v.get("compareAtPrice"),
                            "taxable": v["taxable"],
                            "inventoryPolicy": v["inventoryPolicy"],
                            "requiresShipping": True,
                            "fulfillmentService": "manual",
                        }
                    )

                # Create product with variants using productSet mutation
                mutation = """
                mutation productSet($input: ProductSetInput!) {
                    productSet(input: $input) {
                        product {
                            id
                            title
                            handle
                            variants(first: 10) {
                                nodes {
                                    id
                                    title
                                    price
                                    sku
                                }
                            }
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                # Create product options and variants
                product_options = [
                    {
                        "name": "Size",
                        "position": 1,
                        "values": [
                            {"name": "Small"},
                            {"name": "Medium"},
                            {"name": "Large"},
                        ],
                    }
                ]

                # Convert variants to productSet format with proper option values
                product_variants = []
                sizes = ["Small", "Medium", "Large"]
                for i, variant_data in enumerate(variants):
                    size = sizes[i % len(sizes)]  # Cycle through sizes
                    product_variants.append(
                        {
                            "price": variant_data["price"],
                            "sku": f"{variant_data['sku']}-{size[:1]}",  # Add size to SKU
                            "compareAtPrice": variant_data.get("compareAtPrice"),
                            "taxable": variant_data["taxable"],
                            "inventoryPolicy": variant_data["inventoryPolicy"],
                            "optionValues": [{"optionName": "Size", "name": size}],
                        }
                    )

                variables = {
                    "input": {
                        "title": product_data["title"],
                        "vendor": product_data["vendor"],
                        "productType": product_data["productType"],
                        "handle": product_data["handle"],
                        "tags": product_data.get("tags", []),
                        "status": "ACTIVE",
                        "productOptions": product_options,
                        "variants": product_variants,
                    }
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["productSet"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["productSet"]["userErrors"]
                    ]
                    raise Exception(f"Product creation errors: {', '.join(errors)}")

                product = result["data"]["productSet"]["product"]

                # Extract variant IDs for order creation
                variant_ids = []
                for variant_node in product["variants"]["nodes"]:
                    variant_ids.append(variant_node["id"])

                self.created_products[f"product_{i}"] = {
                    "id": product["id"],
                    "handle": product["handle"],
                    "title": product["title"],
                    "variants": variant_ids,
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

                # Prepare addresses
                addresses = []
                if customer_data.get("defaultAddress"):
                    addr = customer_data["defaultAddress"]
                    addresses.append(
                        {
                            "address1": addr["address1"],
                            "city": addr["city"],
                            "province": addr["province"],
                            "country": addr["country"],
                            "zip": addr["zip"],
                            "phone": addr["phone"],
                            "firstName": customer_data["firstName"],
                            "lastName": customer_data["lastName"],
                        }
                    )

                # Create customer mutation
                mutation = """
                mutation customerCreate($input: CustomerInput!) {
                    customerCreate(input: $input) {
                        customer {
                            id
                            email
                            displayName
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                variables = {
                    "input": {
                        "firstName": customer_data["firstName"],
                        "lastName": customer_data["lastName"],
                        "email": customer_data["email"],
                        "tags": customer_data.get("tags", []),
                        "addresses": addresses,
                    }
                }

                result = self._graphql_request(mutation, variables)

                if result["data"]["customerCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["customerCreate"]["userErrors"]
                    ]
                    raise Exception(f"Customer creation errors: {', '.join(errors)}")

                customer = result["data"]["customerCreate"]["customer"]
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
        collections = []
        collections.append(
            {
                "title": "Summer Essentials",
                "handle": "summer-essentials",
                "descriptionHtml": "Perfect for summer - clothing and accessories",
                "productIds": product_ids[:10],
            }
        )
        collections.append(
            {
                "title": "Tech Gear",
                "handle": "tech-gear",
                "descriptionHtml": "Latest technology and electronics",
                "productIds": product_ids[10:],
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
                # Create collection mutation
                create_mutation = """
                mutation collectionCreate($input: CollectionInput!) {
                    collectionCreate(input: $input) {
                        collection {
                            id
                            title
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                create_variables = {
                    "input": {
                        "title": c["title"],
                        "descriptionHtml": c["descriptionHtml"],
                        "handle": c["handle"],
                    }
                }

                result = self._graphql_request(create_mutation, create_variables)

                if result["data"]["collectionCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["collectionCreate"]["userErrors"]
                    ]
                    raise Exception(f"Collection creation errors: {', '.join(errors)}")

                collection = result["data"]["collectionCreate"]["collection"]
                self.created_collections[f"collection_{i}"] = {
                    "id": collection["id"],
                    "title": collection["title"],
                }
                print(f"  ✅ Collection: {collection['title']} ({collection['id']})")

                # Add products to collection
                if c["productIds"]:
                    add_products_mutation = """
                    mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
                        collectionAddProducts(id: $id, productIds: $productIds) {
                            collection {
                                id
                                title
                            }
                            userErrors {
                                field
                                message
                            }
                        }
                    }
                    """

                    add_variables = {
                        "id": collection["id"],
                        "productIds": c["productIds"],
                    }

                    add_result = self._graphql_request(
                        add_products_mutation, add_variables
                    )

                    if add_result["data"]["collectionAddProducts"]["userErrors"]:
                        errors = [
                            error["message"]
                            for error in add_result["data"]["collectionAddProducts"][
                                "userErrors"
                            ]
                        ]
                        print(
                            f"    ⚠️ Failed to add products to collection: {', '.join(errors)}"
                        )
                    else:
                        print(
                            f"    ✅ Added {len(c['productIds'])} products to collection"
                        )

            except Exception as e:
                print(f"  ❌ Collection '{c['title']}' failed: {e}")
        return self.created_collections

    async def create_orders(self) -> Dict[str, Dict[str, Any]]:
        print("📋 Creating orders...")
        if not self.created_products or not self.created_customers:
            print("  ⚠️ Need products and customers before creating orders")
            return {}

        # Get some products and customers for orders
        customer_ids = [c["id"] for c in self.created_customers.values()]

        # Create a few orders
        for i in range(1, 4):  # Create 3 orders
            try:
                # Pick random customer and products
                customer_id = random.choice(customer_ids)
                product_ids = list(self.created_products.values())
                selected_products = random.sample(product_ids, min(2, len(product_ids)))

                # Create draft order
                draft_mutation = """
                mutation draftOrderCreate($input: DraftOrderInput!) {
                    draftOrderCreate(input: $input) {
                        draftOrder {
                            id
                            name
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                line_items = []
                # Create line items using product variants
                for product in selected_products:
                    if product.get("variants"):
                        variant_id = product["variants"][0]  # Use first variant
                        quantity = random.randint(1, 3)
                        line_items.append(
                            {
                                "variantId": variant_id,
                                "quantity": quantity,
                            }
                        )

                if not line_items:
                    print(f"  ⚠️ Skipping order {i} - no variants available")
                    continue

                draft_variables = {
                    "input": {
                        "lineItems": line_items,
                        "customerId": customer_id,
                        "email": f"order{i}@example.com",
                        "tags": ["Test Order", f"Order-{i}"],
                    }
                }

                result = self._graphql_request(draft_mutation, draft_variables)

                if result["data"]["draftOrderCreate"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in result["data"]["draftOrderCreate"]["userErrors"]
                    ]
                    print(f"  ⚠️ Draft order {i} creation errors: {', '.join(errors)}")
                    continue

                draft_order = result["data"]["draftOrderCreate"]["draftOrder"]

                # Complete the draft order
                complete_mutation = """
                mutation draftOrderComplete($id: ID!) {
                    draftOrderComplete(id: $id) {
                        draftOrder {
                            id
                            status
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
                """

                complete_variables = {"id": draft_order["id"]}
                complete_result = self._graphql_request(
                    complete_mutation, complete_variables
                )

                if complete_result["data"]["draftOrderComplete"]["userErrors"]:
                    errors = [
                        error["message"]
                        for error in complete_result["data"]["draftOrderComplete"][
                            "userErrors"
                        ]
                    ]
                    print(f"  ⚠️ Order completion errors: {', '.join(errors)}")
                else:
                    self.created_orders[f"order_{i}"] = {
                        "id": draft_order["id"],
                        "name": draft_order["name"],
                    }
                    print(f"  ✅ Order: {draft_order['name']} ({draft_order['id']})")

            except Exception as e:
                print(f"  ❌ Order {i} failed: {e}")
        return self.created_orders

    async def run(self) -> bool:
        print(f"🚀 Seeding Shopify store with GraphQL: {self.shop_domain}")

        # Create products and customers in parallel since they're independent
        print("📦 Creating products and customers in parallel...")
        products_task = asyncio.create_task(self.create_products())
        customers_task = asyncio.create_task(self.create_customers())

        # Wait for both to complete
        await asyncio.gather(products_task, customers_task)

        # Create collections after products are ready
        print("📚 Creating collections...")
        await self.create_collections()

        # Create orders after products and customers are ready
        print("📋 Creating orders...")
        await self.create_orders()

        print("\n🎯 Seeding Summary:")
        print(f"  ✅ Products:   {len(self.created_products)}")
        print(f"  ✅ Customers:  {len(self.created_customers)}")
        print(f"  ✅ Collections:{len(self.created_collections)}")
        print(f"  ✅ Orders:     {len(self.created_orders)}")
        print(f"  🔗 Admin URL: https://{self.shop_domain}/admin")
        return bool(self.created_products and self.created_customers)


async def main() -> bool:
    seeder = ShopifyGraphQLSeeder(
        "vnsaid.myshopify.com", "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"
    )
    return await seeder.run()


if __name__ == "__main__":
    asyncio.run(main())
