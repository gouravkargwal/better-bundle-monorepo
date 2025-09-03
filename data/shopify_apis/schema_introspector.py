#!/usr/bin/env python3
"""
Shopify GraphQL Schema Introspector
Checks what fields actually exist in the Shopify schema for our entities
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ShopifySchemaIntrospector:
    def __init__(self):
        self.shop_domain = os.getenv('SHOPIFY_SHOP_DOMAIN')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = '2024-01'
        
        if not self.shop_domain or not self.access_token:
            raise ValueError("Missing SHOPIFY_SHOP_DOMAIN or SHOPIFY_ACCESS_TOKEN in environment")
        
        self.url = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

    async def introspect_entity(self, entity_name: str, sample_query: str):
        """Introspect a specific entity to see what fields exist"""
        print(f"\n🔍 Introspecting {entity_name}...")
        print("=" * 50)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json={"query": sample_query}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "errors" in data:
                        print(f"❌ GraphQL Errors for {entity_name}:")
                        for error in data["errors"]:
                            print(f"   - {error.get('message', 'Unknown error')}")
                        
                        # Extract field names from error messages
                        field_errors = []
                        for error in data["errors"]:
                            message = error.get('message', '')
                            if "doesn't exist on type" in message:
                                field_name = message.split("'")[1] if "'" in message else "Unknown"
                                field_errors.append(field_name)
                        
                        if field_errors:
                            print(f"\n📋 Fields that don't exist: {field_errors}")
                        
                        return False, field_errors
                    else:
                        print(f"✅ {entity_name} query successful!")
                        return True, []
                else:
                    print(f"❌ HTTP Error: {response.status_code}")
                    return False, []
                    
        except Exception as e:
            print(f"❌ Error introspecting {entity_name}: {e}")
            return False, []

    async def introspect_all_entities(self):
        """Introspect all entities to identify field mismatches"""
        print("🚀 Shopify GraphQL Schema Introspection")
        print("=" * 60)
        print("Checking what fields actually exist in your Shopify schema...")
        
        # Test queries for each entity
        test_queries = {
            "Customer": """
            query TestCustomerFields {
                customers(first: 1) {
                    edges {
                        node {
                            id
                            firstName
                            lastName
                            email
                            createdAt
                            updatedAt
                            numberOfOrders
                            amountSpent {
                                amount
                                currencyCode
                            }
                            tags
                            state
                            verifiedEmail
                            taxExempt
                            defaultEmailAddress
                            defaultPhoneNumber
                            metafields(first: 5) {
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
                }
            }
            """,
            
            "Order": """
            query TestOrderFields {
                orders(first: 1) {
                    edges {
                        node {
                            id
                            name
                            createdAt
                            updatedAt
                            processedAt
                            cancelledAt
                            cancelReason
                            totalPriceSet {
                                shopMoney {
                                    amount
                                    currencyCode
                                }
                            }
                            subtotalPriceSet {
                                shopMoney {
                                    amount
                                    currencyCode
                                }
                            }
                            totalTaxSet {
                                shopMoney {
                                    amount
                                    currencyCode
                                }
                            }
                            totalShippingPriceSet {
                                shopMoney {
                                    amount
                                    currencyCode
                                }
                            }
                            confirmed
                            test
                            tags
                            note
                            customerLocale
                            currencyCode
                            fulfillmentStatus
                            financialStatus
                            metafields(first: 5) {
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
                }
            }
            """,
            
            "Collection": """
            query TestCollectionFields {
                collections(first: 1) {
                    edges {
                        node {
                            id
                            title
                            handle
                            description
                            publishedAt
                            updatedAt
                            sortOrder
                            templateSuffix
                            seo {
                                title
                                description
                            }
                            image {
                                url
                                altText
                                width
                                height
                            }
                            products(first: 5) {
                                edges {
                                    node {
                                        id
                                        title
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
                                        variants(first: 2) {
                                            edges {
                                                node {
                                                    id
                                                    title
                                                    price
                                                    sku
                                                    quantityAvailable
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            metafields(first: 5) {
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
                }
            }
            """,
            
            "Product": """
            query TestProductFields {
                products(first: 1) {
                    edges {
                        node {
                            id
                            title
                            productType
                            vendor
                            tags
                            status
                            totalInventory
                            metafields(first: 5) {
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
                                values
                            }
                            variants(first: 5) {
                                edges {
                                    node {
                                        id
                                        title
                                        price
                                        sku
                                        barcode
                                        inventoryQuantity
                                        weight
                                        weightUnit
                                    }
                                }
                            }
                            collections(first: 5) {
                                edges {
                                    node {
                                        id
                                        title
                                        handle
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
        }
        
        results = {}
        
        for entity_name, query in test_queries.items():
            success, field_errors = await self.introspect_entity(entity_name, query)
            results[entity_name] = {
                "success": success,
                "field_errors": field_errors
            }
        
        # Summary report
        print("\n" + "=" * 60)
        print("📊 SCHEMA INTROSPECTION SUMMARY")
        print("=" * 60)
        
        for entity_name, result in results.items():
            status = "✅ WORKING" if result["success"] else "❌ HAS ISSUES"
            print(f"{entity_name}: {status}")
            if not result["success"]:
                print(f"   Fields to remove: {result['field_errors']}")
        
        return results

async def main():
    """Run the schema introspection"""
    try:
        introspector = ShopifySchemaIntrospector()
        results = await introspector.introspect_all_entities()
        
        print(f"\n🎯 Next Steps:")
        print(f"1. Remove non-existent fields from APIs")
        print(f"2. Test fixed APIs")
        print(f"3. Create unified data pipeline")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
