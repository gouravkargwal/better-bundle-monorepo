#!/usr/bin/env python3
"""
Shopify Product API Query

This script contains the correct GraphQL query for products based on
the actual Shopify GraphQL schema.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyProductAPI:
    """Shopify Product API with correct GraphQL query"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_products(self, first: int = 10):
        """Get products using the correct GraphQL query based on actual schema"""

        # GraphQL query matching the actual Shopify GraphQL schema
        query = """
        query GetProducts($first: Int!) {
            products(first: $first) {
                edges {
                    node {
                        id
                        title
                        description
                        handle
                        createdAt
                        updatedAt
                        publishedAt
                        status
                        tags
                        productType
                        vendor
                        totalInventory
                        images(first: 5) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                    width
                                    height
                                }
                            }
                        }
                        options(first: 5) {
                            id
                            name
                            position
                            values
                        }
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    compareAtPrice
                                    inventoryQuantity
                                    sku
                                    barcode
                                    selectedOptions {
                                        name
                                        value
                                    }
                                }
                            }
                        }
                        collections(first: 5) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                    description
                                }
                            }
                        }
                        metafields(first: 10) {
                            edges {
                                node {
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
            }
        }
        """

        variables = {"first": first}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": query, "variables": variables},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()

                    if "errors" in data:
                        print(f"❌ GraphQL Errors:")
                        for error in data["errors"]:
                            print(f"   - {error.get('message', 'Unknown error')}")
                        return {}

                    return data
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    return {}

        except Exception as e:
            print(f"❌ Query execution failed: {e}")
            return {}

    async def get_single_product(self, product_id: str):
        """Get a single product by ID"""

        query = """
        query GetProduct($id: ID!) {
            product(id: $id) {
                id
                title
                description
                handle
                createdAt
                updatedAt
                publishedAt
                status
                tags
                productType
                vendor
                totalInventory
                images(first: 10) {
                    edges {
                        node {
                            id
                            url
                            altText
                            width
                            height
                        }
                    }
                }
                options(first: 10) {
                    id
                    name
                    position
                    values
                }
                variants(first: 20) {
                    edges {
                        node {
                            id
                            title
                            price
                            compareAtPrice
                            inventoryQuantity
                            sku
                            barcode
                            selectedOptions {
                                name
                                value
                            }
                        }
                    }
                }
                collections(first: 10) {
                    edges {
                        node {
                            id
                            title
                            handle
                            description
                        }
                    }
                }
                metafields(first: 20) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
                        }
                    }
                }
            }
        }
        """

        variables = {"id": product_id}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": query, "variables": variables},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()

                    if "errors" in data:
                        print(f"❌ GraphQL Errors:")
                        for error in data["errors"]:
                            print(f"   - {error.get('message', 'Unknown error')}")
                        return {}

                    return data
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    return {}

        except Exception as e:
            print(f"❌ Query execution failed: {e}")
            return {}

    def analyze_product_data(self, product_data: dict):
        """Analyze the product data structure for Gorse ML features"""
        if not product_data or "data" not in product_data:
            print("❌ No product data to analyze")
            return

        products = product_data["data"]["products"]["edges"]
        print(f"\n📊 Product Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(products)} products")

        if products:
            # Analyze first product
            product = products[0]["node"]

            print(f"\n🎯 Sample Product Structure:")
            print(f"   Basic Info:")
            print(f"      - ID: {product['id']}")
            print(f"      - Title: {product['title']}")
            print(f"      - Type: {product.get('productType', 'N/A')}")
            print(f"      - Vendor: {product.get('vendor', 'N/A')}")
            print(f"      - Status: {product.get('status', 'N/A')}")
            print(f"      - Tags: {product.get('tags', 'N/A')}")
            print(f"      - Inventory: {product.get('totalInventory', 0)}")

            # Images
            images = product.get("images", {}).get("edges", [])
            print(f"   Images: {len(images)}")

            # Options
            options = product.get("options", [])
            print(f"   Options: {len(options)}")
            for option in options[:3]:
                print(
                    f"      - {option.get('name', 'N/A')}: {option.get('values', [])}"
                )

            # Variants
            variants = product.get("variants", {}).get("edges", [])
            print(f"   Variants: {len(variants)}")
            if variants:
                variant = variants[0]["node"]
                print(f"      Sample Variant:")
                print(f"         - Title: {variant.get('title', 'N/A')}")
                print(f"         - Price: ${variant.get('price', 'N/A')}")
                print(f"         - SKU: {variant.get('sku', 'N/A')}")
                print(
                    f"         - Inventory: {variant.get('inventoryQuantity', 'N/A')}"
                )

                # Show selected options
                selected_options = variant.get("selectedOptions", [])
                if selected_options:
                    print(f"         - Options:")
                    for option in selected_options:
                        print(
                            f"            {option.get('name', 'N/A')}: {option.get('value', 'N/A')}"
                        )

            # Collections
            collections = product.get("collections", {}).get("edges", [])
            print(f"   Collections: {len(collections)}")
            for collection in collections[:3]:
                print(f"      - {collection['node']['title']}")

            # Metafields
            metafields = product.get("metafields", {}).get("edges", [])
            print(f"   Metafields: {len(metafields)}")

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   Item Features:")
            print(f"      - item_id: {product['id']}")
            print(f"      - item_title: '{product['title']}'")
            print(f"      - item_type: '{product.get('productType', '')}'")
            print(f"      - item_vendor: '{product.get('vendor', '')}'")
            print(f"      - item_tags: '{product.get('tags', '')}'")
            print(f"      - item_status: '{product.get('status', '')}'")
            print(f"      - item_inventory: {product.get('totalInventory', 0)}")
            print(f"      - item_variants_count: {len(variants)}")
            print(f"      - item_options_count: {len(options)}")
            print(f"      - item_images_count: {len(images)}")
            print(
                f"      - item_collections: {[c['node']['title'] for c in collections]}"
            )

            if variants:
                variant = variants[0]["node"]
                print(f"      - item_price: {variant.get('price', 0)}")
                print(f"      - item_sku: '{variant.get('sku', '')}'")

                # Show option values for ML features
                selected_options = variant.get("selectedOptions", [])
                for option in selected_options:
                    option_name = option.get("name", "").lower().replace(" ", "_")
                    option_value = option.get("value", "")
                    print(f"      - item_{option_name}: '{option_value}'")


async def main():
    """Test the product API"""
    api = ShopifyProductAPI()

    print("🚀 Testing Shopify Product API")
    print("=" * 40)

    # Get products
    products = await api.get_products(first=5)
    if products:
        api.analyze_product_data(products)
    else:
        print("❌ Failed to fetch products")


if __name__ == "__main__":
    asyncio.run(main())
