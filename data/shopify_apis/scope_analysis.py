#!/usr/bin/env python3
"""
Shopify Scope Analysis

This script analyzes Shopify Admin API documentation to identify
additional meaningful scopes for recommendation systems.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyScopeAnalyzer:
    """Analyze available Shopify scopes and their data value"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def analyze_extended_scopes(self):
        """Analyze additional scopes beyond the basic ones"""
        print("🔍 Analyzing Extended Shopify Scopes")
        print("=" * 50)

        # Test additional scopes that might be valuable
        await self.test_collections_and_categories()
        await self.test_customer_groups()
        await self.test_price_rules()
        await self.test_abandoned_checkouts()
        await self.test_fulfillment_data()
        await self.test_metafields()
        await self.test_webhooks()
        await self.test_app_performance()

    async def test_collections_and_categories(self):
        """Test collection and category data"""
        print("\n📚 Testing Collections & Categories...")

        query = """
        query {
            collections(first: 5) {
                edges {
                    node {
                        id
                        title
                        handle
                        description
                        productsCount
                        ruleSet {
                            rules {
                                column
                                relation
                                condition
                            }
                        }
                        products(first: 3) {
                            edges {
                                node {
                                    id
                                    title
                                    productType
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            collections = response["data"]["collections"]["edges"]
            print(f"   Found {len(collections)} collections")

            if collections:
                for i, collection_edge in enumerate(collections[:3]):
                    collection = collection_edge["node"]
                    print(f"   Collection {i+1}: {collection['title']}")
                    print(f"      Products: {collection['productsCount']}")
                    if collection.get("ruleSet") and collection["ruleSet"].get("rules"):
                        rules = collection["ruleSet"]["rules"]
                        print(f"      Rules: {len(rules)} auto-collection rules")
            return response["data"]
        return {}

    async def test_customer_groups(self):
        """Test customer groups and segmentation"""
        print("\n👥 Testing Customer Groups...")

        # Note: Customer groups might be accessed through different endpoints
        query = """
        query {
            customers(first: 10) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        tags
                        note
                        orders(first: 3) {
                            edges {
                                node {
                                    id
                                    name
                                    totalPriceSet {
                                        shopMoney {
                                            amount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            customers = response["data"]["customers"]["edges"]
            print(f"   Found {len(customers)} customers for group analysis")

            # Analyze potential groups
            tag_groups = {}
            spending_groups = {}

            for customer_edge in customers:
                customer = customer_edge["node"]
                tags = customer.get("tags", [])
                orders = customer.get("orders", {}).get("edges", [])

                # Group by tags
                for tag in tags:
                    if tag not in tag_groups:
                        tag_groups[tag] = []
                    tag_groups[tag].append(customer["firstName"])

                # Group by spending
                total_spent = sum(
                    float(order["node"]["totalPriceSet"]["shopMoney"]["amount"])
                    for order in orders
                )

                if total_spent > 1000:
                    group = "High Spender"
                elif total_spent > 500:
                    group = "Medium Spender"
                elif total_spent > 100:
                    group = "Low Spender"
                else:
                    group = "No Purchase"

                if group not in spending_groups:
                    spending_groups[group] = []
                spending_groups[group].append(customer["firstName"])

            print("   Tag-based Groups:")
            for tag, customers_list in tag_groups.items():
                print(f"      {tag}: {len(customers_list)} customers")

            print("   Spending Groups:")
            for group, customers_list in spending_groups.items():
                print(f"      {group}: {len(customers_list)} customers")

            return response["data"]
        return {}

    async def test_price_rules(self):
        """Test price rules and dynamic pricing"""
        print("\n💰 Testing Price Rules & Dynamic Pricing...")

        query = """
        query {
            priceRules(first: 5) {
                edges {
                    node {
                        id
                        title
                        status
                        targetType
                        targetSelection
                        allocationMethod
                        value {
                            ... on MoneyV2 {
                                amount
                                currencyCode
                            }
                            ... on PricingPercentageValue {
                                percentage
                            }
                        }
                        customerSegments(first: 3) {
                            edges {
                                node {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            price_rules = response["data"]["priceRules"]["edges"]
            print(f"   Found {len(price_rules)} price rules")

            if price_rules:
                for i, rule_edge in enumerate(price_rules):
                    rule = rule_edge["node"]
                    print(f"   Rule {i+1}: {rule['title']}")
                    print(f"      Status: {rule['status']}")
                    print(f"      Target: {rule['targetType']}")
                    if (
                        rule.get("customerSegments")
                        and rule["customerSegments"]["edges"]
                    ):
                        segments = rule["customerSegments"]["edges"]
                        print(f"      Customer Segments: {len(segments)}")
            return response["data"]
        return {}

    async def test_abandoned_checkouts(self):
        """Test abandoned checkout data"""
        print("\n🛒 Testing Abandoned Checkouts...")

        query = """
        query {
            checkouts(first: 5) {
                edges {
                    node {
                        id
                        email
                        createdAt
                        updatedAt
                        totalPriceSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        lineItems(first: 3) {
                            edges {
                                node {
                                    title
                                    quantity
                                    variant {
                                        id
                                        title
                                        price
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            checkouts = response["data"]["checkouts"]["edges"]
            print(f"   Found {len(checkouts)} checkouts")

            if checkouts:
                for i, checkout_edge in enumerate(checkouts[:3]):
                    checkout = checkout_edge["node"]
                    print(f"   Checkout {i+1}: {checkout['email']}")
                    print(
                        f"      Total: {checkout['totalPriceSet']['shopMoney']['amount']} {checkout['totalPriceSet']['shopMoney']['currencyCode']}"
                    )
                    print(f"      Items: {len(checkout['lineItems']['edges'])}")
            return response["data"]
        return {}

    async def test_fulfillment_data(self):
        """Test fulfillment and shipping data"""
        print("\n📦 Testing Fulfillment & Shipping...")

        query = """
        query {
            fulfillments(first: 5) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        updatedAt
                        order {
                            id
                            name
                            customer {
                                firstName
                                lastName
                            }
                        }
                        trackingInfo {
                            company
                            number
                            url
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            fulfillments = response["data"]["fulfillments"]["edges"]
            print(f"   Found {len(fulfillments)} fulfillments")

            if fulfillments:
                for i, fulfillment_edge in enumerate(fulfillments[:3]):
                    fulfillment = fulfillment_edge["node"]
                    order = fulfillment.get("order", {})
                    customer = order.get("customer", {})
                    print(f"   Fulfillment {i+1}: {fulfillment['status']}")
                    print(f"      Order: {order.get('name', 'N/A')}")
                    print(
                        f"      Customer: {customer.get('firstName', 'N/A')} {customer.get('lastName', 'N/A')}"
                    )
            return response["data"]
        return {}

    async def test_metafields(self):
        """Test metafields for custom data"""
        print("\n🏷️ Testing Metafields & Custom Data...")

        query = """
        query {
            products(first: 3) {
                edges {
                    node {
                        id
                        title
                        metafields(first: 5) {
                            edges {
                                node {
                                    key
                                    namespace
                                    value
                                    type
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        response = await self._execute_query(query)
        if response and "data" in response:
            products = response["data"]["products"]["edges"]
            print(f"   Found {len(products)} products with metafields")

            if products:
                for i, product_edge in enumerate(products):
                    product = product_edge["node"]
                    metafields = product.get("metafields", {}).get("edges", [])
                    print(f"   Product {i+1}: {product['title']}")
                    print(f"      Metafields: {len(metafields)}")
                    for j, metafield_edge in enumerate(metafields[:3]):
                        metafield = metafield_edge["node"]
                        print(
                            f"         {metafield['namespace']}.{metafield['key']}: {metafield['value']}"
                        )
            return response["data"]
        return {}

    async def test_webhooks(self):
        """Test webhook capabilities"""
        print("\n🔗 Testing Webhook Capabilities...")

        # Note: Webhooks are typically configured through REST API, not GraphQL
        print("   Webhooks require REST API access")
        print("   Can be used for real-time data updates")
        return {}

    async def test_app_performance(self):
        """Test app performance and usage data"""
        print("\n📊 Testing App Performance Data...")

        # Note: App performance data might be available through different endpoints
        print("   App performance data may require special access")
        print("   Can include usage metrics and performance indicators")
        return {}

    async def _execute_query(self, query: str) -> dict:
        """Execute GraphQL query"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": query},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()

                    if "errors" in data:
                        print(f"   ❌ GraphQL Errors:")
                        for error in data["errors"]:
                            print(f"      - {error.get('message', 'Unknown error')}")
                        return {}

                    return data
                else:
                    print(f"   ❌ HTTP Error: {response.status_code}")
                    return {}

        except Exception as e:
            print(f"   ❌ Query execution failed: {e}")
            return {}

    async def run_scope_analysis(self):
        """Run comprehensive scope analysis"""
        print("🚀 Shopify Scope Analysis - Extended Data Sources")
        print("=" * 65)
        print("Analyzing additional scopes for recommendation system enhancement")
        print()

        await self.analyze_extended_scopes()

        print("\n✅ Scope analysis completed!")
        print("\n📋 Additional Valuable Scopes Identified:")
        print("   - Collections & Categories (product grouping)")
        print("   - Customer Groups (segmentation)")
        print("   - Price Rules (dynamic pricing)")
        print("   - Abandoned Checkouts (conversion optimization)")
        print("   - Fulfillment Data (shipping patterns)")
        print("   - Metafields (custom data)")
        print("   - Webhooks (real-time updates)")
        print("\n🎯 Next: Request these scopes and implement data collection")


async def main():
    """Main function"""
    analyzer = ShopifyScopeAnalyzer()
    await analyzer.run_scope_analysis()


if __name__ == "__main__":
    asyncio.run(main())
