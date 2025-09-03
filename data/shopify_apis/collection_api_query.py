#!/usr/bin/env python3
"""
Shopify Collection API Query

This script contains GraphQL queries for collections to provide
category and grouping data for Gorse ML training.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyCollectionAPI:
    """Shopify Collection API with GraphQL queries"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_collections(self, first: int = 50):
        """Get collections with products and metadata"""

        query = """
        query GetCollections($first: Int!) {
            collections(first: $first) {
                edges {
                    node {
                        id
                        title
                        description
                        descriptionHtml
                        handle
                        updatedAt
                        sortOrder
                        templateSuffix
                        seo {
                            title
                            description
                        }
                        image {
                            id
                            url
                            altText
                            width
                            height
                        }
                        products(first: 20) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                    productType
                                    vendor
                                    tags
                                    priceRangeV2 {
                                        minVariantPrice {
                                            amount
                                            currencyCode
                                        }
                                        maxVariantPrice {
                                            amount
                                            currencyCode
                                        }
                                    }
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
                                    variants(first: 5) {
                                        edges {
                                            node {
                                                id
                                                title
                                                price
                                                sku
                                                barcode
                                                availableForSale
                                            }
                                        }
                                    }
                                }
                            }
                            pageInfo {
                                hasNextPage
                                hasPreviousPage
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
                        ruleSet {
                            rules {
                                column
                                relation
                                condition
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

    async def get_single_collection(self, collection_id: str):
        """Get a single collection by ID"""

        query = """
        query GetCollection($id: ID!) {
            collection(id: $id) {
                id
                title
                description
                descriptionHtml
                handle
                updatedAt
                sortOrder
                templateSuffix
                seo {
                    title
                    description
                }
                image {
                    id
                    url
                    altText
                    width
                    height
                }
                products(first: 50) {
                    edges {
                        node {
                            id
                            title
                            handle
                            productType
                            vendor
                            tags
                            priceRangeV2 {
                                minVariantPrice {
                                    amount
                                    currencyCode
                                }
                                maxVariantPrice {
                                    amount
                                    currencyCode
                                }
                            }
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
                            variants(first: 10) {
                                edges {
                                    node {
                                        id
                                        title
                                        price
                                        sku
                                        barcode
                                        availableForSale
                                    }
                                }
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
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
                ruleSet {
                    rules {
                        column
                        relation
                        condition
                    }
                }
            }
        }
        """

        variables = {"id": collection_id}

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

    def analyze_collection_data(self, collection_data: dict):
        """Analyze collection data for Gorse ML features"""
        if not collection_data or "data" not in collection_data:
            print("❌ No collection data to analyze")
            return

        collections = collection_data["data"]["collections"]["edges"]
        print(f"\n📊 Collection Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(collections)} collections")

        if collections:
            # Analyze first collection
            collection = collections[0]["node"]

            print(f"\n🎯 Sample Collection Structure:")
            print(f"   Basic Info:")
            print(f"      - ID: {collection['id']}")
            print(f"      - Title: {collection['title']}")
            print(f"      - Handle: {collection['handle']}")
            print(
                f"      - Description: {collection.get('description', 'N/A')[:100]}..."
            )
            print(f"      - Published: {collection.get('publishedAt', 'N/A')}")
            print(f"      - Updated: {collection.get('updatedAt', 'N/A')}")
            print(f"      - Sort Order: {collection.get('sortOrder', 'N/A')}")
            print(f"      - Template: {collection.get('templateSuffix', 'N/A')}")

            # SEO information
            seo = collection.get("seo", {})
            if seo:
                print(f"   SEO:")
                print(f"      - Title: {seo.get('title', 'N/A')}")
                description = seo.get('description', 'N/A')
                if description and description != 'N/A':
                    print(f"      - Description: {description[:100]}...")
                else:
                    print(f"      - Description: N/A")

            # Image information
            image = collection.get("image", {})
            if image:
                print(f"   Image:")
                print(f"      - URL: {image.get('url', 'N/A')}")
                print(f"      - Alt: {image.get('altText', 'N/A')}")
                print(
                    f"      - Dimensions: {image.get('width', 'N/A')}x{image.get('height', 'N/A')}"
                )

            # Products in collection
            products = collection.get("products", {}).get("edges", [])
            if products:
                print(f"   Products: {len(products)}")

                # Analyze first few products
                for i, product_edge in enumerate(products[:3]):
                    product = product_edge["node"]
                    print(f"      Product {i+1}: {product['title']}")
                    print(f"         - Type: {product.get('productType', 'N/A')}")
                    print(f"         - Vendor: {product.get('vendor', 'N/A')}")
                    print(f"         - Tags: {product.get('tags', [])}")

                    # Price range
                    price_range = product.get("priceRangeV2", {})
                    if price_range:
                        min_price = price_range.get("minVariantPrice", {}).get(
                            "amount", "N/A"
                        )
                        max_price = price_range.get("maxVariantPrice", {}).get(
                            "amount", "N/A"
                        )
                        print(f"         - Price Range: ${min_price} - ${max_price}")

                    # Variants
                    variants = product.get("variants", {}).get("edges", [])
                    if variants:
                        print(f"         - Variants: {len(variants)}")
                        for j, variant_edge in enumerate(variants[:2]):
                            variant = variant_edge["node"]
                            print(
                                f"            Variant {j+1}: {variant.get('title', 'N/A')} - ${variant.get('price', 'N/A')}"
                            )

            # Metafields
            metafields = collection.get("metafields", {}).get("edges", [])
            if metafields:
                print(f"   Metafields: {len(metafields)}")
                for metafield_edge in metafields[:3]:
                    metafield = metafield_edge["node"]
                    print(
                        f"      - {metafield.get('namespace', 'N/A')}.{metafield.get('key', 'N/A')}: {metafield.get('value', 'N/A')}"
                    )

            # Rules (for automated collections)
            rule_set = collection.get("ruleSet", {})
            if rule_set and rule_set.get("rules"):
                rules = rule_set["rules"]
                print(f"   Rules: {len(rules)}")
                for rule in rules[:3]:
                    print(
                        f"      - {rule.get('column', 'N/A')} {rule.get('relation', 'N/A')} {rule.get('condition', 'N/A')}"
                    )

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   Collection Features:")
            print(f"      - collection_id: '{collection['id']}'")
            print(f"      - collection_title: '{collection['title']}'")
            print(f"      - collection_handle: '{collection['handle']}'")
            print(
                f"      - collection_description: '{collection.get('description', '')}'"
            )
            print(f"      - collection_published: 'N/A'")
            print(f"      - collection_updated: '{collection.get('updatedAt', '')}'")
            print(f"      - collection_sort_order: '{collection.get('sortOrder', '')}'")
            print(
                f"      - collection_template: '{collection.get('templateSuffix', '')}'"
            )

            # SEO features
            if seo:
                print(f"      - collection_seo_title: '{seo.get('title', '')}'")
                print(
                    f"      - collection_seo_description: '{seo.get('description', '')}'"
                )

            # Image features
            if image:
                print(f"      - collection_image_url: '{image.get('url', '')}'")
                print(f"      - collection_image_alt: '{image.get('altText', '')}'")
                print(f"      - collection_image_width: {image.get('width', 0)}")
                print(f"      - collection_image_height: {image.get('height', 0)}")

            # Product aggregation features
            if products:
                product_types = list(
                    set(
                        p["node"].get("productType", "")
                        for p in products
                        if p["node"].get("productType")
                    )
                )
                vendors = list(
                    set(
                        p["node"].get("vendor", "")
                        for p in products
                        if p["node"].get("vendor")
                    )
                )
                all_tags = []
                for p in products:
                    all_tags.extend(p["node"].get("tags", []))
                unique_tags = list(set(all_tags))

                print(f"      - collection_product_count: {len(products)}")
                print(f"      - collection_product_types: {product_types}")
                print(f"      - collection_vendors: {vendors}")
                print(
                    f"      - collection_unique_tags: {unique_tags[:10]}"
                )  # Limit to first 10

                # Price analysis
                if products:
                    prices = []
                    for p in products:
                        price_range = p["node"].get("priceRangeV2", {})
                        if price_range and price_range.get("minVariantPrice", {}).get(
                            "amount"
                        ):
                            prices.append(
                                float(price_range["minVariantPrice"]["amount"])
                            )

                    if prices:
                        avg_price = sum(prices) / len(prices)
                        min_price = min(prices)
                        max_price = max(prices)
                        print(f"      - collection_avg_price: {avg_price:.2f}")
                        print(f"      - collection_min_price: {min_price:.2f}")
                        print(f"      - collection_max_price: {max_price:.2f}")

            # Metafield features
            if metafields:
                metafield_dict = {}
                for mf in metafields:
                    namespace = mf["node"].get("namespace", "")
                    key = mf["node"].get("key", "")
                    value = mf["node"].get("value", "")
                    if namespace and key:
                        metafield_dict[f"{namespace}_{key}"] = value

                for key, value in list(metafield_dict.items())[:5]:  # Limit to first 5
                    print(f"      - collection_metafield_{key}: '{value}'")

            # Rule features (for automated collections)
            if rule_set and rule_set.get("rules"):
                rules = rule_set["rules"]
                rule_types = list(set(r.get("column", "") for r in rules))
                print(f"      - collection_rule_count: {len(rules)}")
                print(f"      - collection_rule_types: {rule_types}")
                print(f"      - collection_is_automated: {len(rules) > 0}")

            # Collection classification
            if products:
                product_count = len(products)
                if product_count > 100:
                    size_category = "Large"
                elif product_count > 50:
                    size_category = "Medium"
                elif product_count > 20:
                    size_category = "Small"
                else:
                    size_category = "Tiny"

                print(f"      - collection_size_category: '{size_category}'")
                print(f"      - collection_is_active: true")


async def main():
    """Test the collection API"""
    api = ShopifyCollectionAPI()

    print("🚀 Testing Shopify Collection API")
    print("=" * 40)

    # Get collections
    collections = await api.get_collections(first=5)
    if collections:
        api.analyze_collection_data(collections)
    else:
        print("❌ Failed to fetch collections")


if __name__ == "__main__":
    asyncio.run(main())
