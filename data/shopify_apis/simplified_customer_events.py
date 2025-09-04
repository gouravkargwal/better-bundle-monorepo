#!/usr/bin/env python3
"""
Simplified Shopify Customer Events API

This script extracts customer behavioral data using only the working fields
to provide rich data for Gorse ML training.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SimplifiedCustomerEventsAPI:
    """Simplified Customer Events API focusing on working fields"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_customer_behavior_data(self, first: int = 250):
        """Get customer behavior data using working fields"""

        query = """
        query GetCustomerBehaviorData($first: Int!) {
            customers(first: $first) {
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
                        orders(first: 40) {
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
                                    lineItems(first: 15) {
                                        edges {
                                            node {
                                                id
                                                title
                                                quantity
                                                variant {
                                                    id
                                                    title
                                                    price
                                                    sku
                                                    barcode
                                                    product {
                                                        id
                                                        title
                                                        productType
                                                        vendor
                                                        tags
                                                        collections(first: 3) {
                                                            edges {
                                                                node {
                                                                    id
                                                                    title
                                                                    handle
                                                                    description
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    shippingAddress {
                                        address1
                                        city
                                        province
                                        country
                                        zip
                                        phone
                                        provinceCode
                                        countryCodeV2
                                    }
                                    billingAddress {
                                        address1
                                        city
                                        province
                                        country
                                        zip
                                        phone
                                        provinceCode
                                        countryCodeV2
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

    async def get_general_events(self, first: int = 250):
        """Get general events from the store"""

        query = """
        query GetGeneralEvents($first: Int!) {
            events(first: $first) {
                edges {
                    node {
                        id
                        __typename
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

    def analyze_customer_behavior(self, behavior_data: dict):
        """Analyze customer behavior data for Gorse ML features"""
        if not behavior_data or "data" not in behavior_data:
            print("❌ No customer behavior data to analyze")
            return

        customers = behavior_data["data"]["customers"]["edges"]
        print(f"\n📊 Customer Behavior Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(customers)} customers")

        if customers:
            # Analyze first customer
            customer = customers[0]["node"]
            print(f"\n🎯 Sample Customer Structure:")
            print(f"   Basic Info:")
            print(f"      - ID: {customer['id']}")
            print(
                f"      - Name: {customer.get('firstName', 'N/A')} {customer.get('lastName', 'N/A')}"
            )
            print(f"      - Email: {customer.get('email', 'N/A')}")
            print(f"      - Created: {customer.get('createdAt', 'N/A')}")
            print(f"      - Orders: {customer.get('numberOfOrders', 0)}")
            print(f"      - State: {customer.get('state', 'N/A')}")
            print(f"      - Verified: {customer.get('verifiedEmail', 'N/A')}")
            print(f"      - Tax Exempt: {customer.get('taxExempt', 'N/A')}")
            print(f"      - Tags: {customer.get('tags', [])}")

            # Financial information
            amount_spent = customer.get("amountSpent", {})
            if amount_spent:
                amount = amount_spent.get("amount", "0")
                currency = amount_spent.get("currencyCode", "USD")
                print(f"   Financial:")
                print(f"      - Amount Spent: {amount} {currency}")

            # Events
            events = customer.get("events", {}).get("edges", [])
            if events:
                print(f"   Events: {len(events)}")
                event_types = set()
                for event_edge in events:
                    event = event_edge["node"]
                    event_types.add(event.get("__typename", "Unknown"))
                print(f"      Event Types: {list(event_types)}")

            # Orders and behavior patterns
            orders = customer.get("orders", {}).get("edges", [])
            if orders:
                print(f"   Orders: {len(orders)}")

                # Analyze order patterns
                order_dates = []
                order_totals = []
                product_types = set()
                vendors = set()
                all_tags = []
                collections = set()

                for order_edge in orders:
                    order = order_edge["node"]
                    order_dates.append(order.get("createdAt", ""))

                    total = float(
                        order.get("totalPriceSet", {})
                        .get("shopMoney", {})
                        .get("amount", "0")
                    )
                    order_totals.append(total)

                    line_items = order.get("lineItems", {}).get("edges", [])
                    for item_edge in line_items:
                        item = item_edge["node"]
                        variant = item.get("variant", {})
                        product = variant.get("product", {})

                        product_types.add(product.get("productType", ""))
                        vendors.add(product.get("vendor", ""))
                        all_tags.extend(product.get("tags", []))

                        # Get collections
                        product_collections = product.get("collections", {}).get(
                            "edges", []
                        )
                        for collection_edge in product_collections:
                            collection = collection_edge["node"]
                            collections.add(collection.get("title", ""))

                unique_tags = list(set(all_tags))

                print(f"      Order Patterns:")
                print(
                    f"         - Date Range: {min(order_dates) if order_dates else 'N/A'} to {max(order_dates) if order_dates else 'N/A'}"
                )
                print(f"         - Total Spent: ${sum(order_totals):.2f}")
                print(
                    f"         - Avg Order Value: ${sum(order_totals)/len(order_totals):.2f if order_totals else 0}"
                )
                print(f"         - Product Types: {list(product_types)}")
                print(f"         - Vendors: {list(vendors)}")
                print(f"         - Collections: {list(collections)}")
                print(f"         - Product Tags: {unique_tags[:10]}")  # Show first 10

            # Metafields
            metafields = customer.get("metafields", {}).get("edges", [])
            if metafields:
                print(f"   Metafields: {len(metafields)}")
                for metafield_edge in metafields[:3]:
                    metafield = metafield_edge["node"]
                    print(
                        f"      - {metafield.get('namespace', 'N/A')}.{metafield.get('key', 'N/A')}: {metafield.get('value', 'N/A')}"
                    )

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   User Features:")
            print(f"      - user_id: '{customer['id']}'")
            print(
                f"      - user_name: '{customer.get('firstName', '')} {customer.get('lastName', '')}'"
            )
            print(f"      - user_email: '{customer.get('email', '')}'")
            print(f"      - user_created_at: '{customer.get('createdAt', '')}'")
            print(f"      - user_updated_at: '{customer.get('updatedAt', '')}'")
            print(f"      - user_state: '{customer.get('state', '')}'")
            print(
                f"      - user_verified_email: {customer.get('verifiedEmail', False)}"
            )
            print(f"      - user_tax_exempt: {customer.get('taxExempt', False)}")
            print(f"      - user_tags: {customer.get('tags', [])}")
            print(f"      - user_number_of_orders: {customer.get('numberOfOrders', 0)}")

            if amount_spent:
                print(f"      - user_amount_spent: {amount_spent.get('amount', 0)}")
                print(
                    f"      - user_currency: '{amount_spent.get('currencyCode', '')}'"
                )

            # Customer segmentation features
            if orders:
                order_count = len(orders)
                if order_count > 10:
                    customer_type = "High Value"
                elif order_count > 5:
                    customer_type = "Medium Value"
                elif order_count > 0:
                    customer_type = "Low Value"
                else:
                    customer_type = "No Purchase"

                print(f"      - user_customer_type: '{customer_type}'")

                # Spending tier
                total_spent = sum(order_totals)
                if total_spent > 1000:
                    spending_tier = "High Spender"
                elif total_spent > 500:
                    spending_tier = "Medium Spender"
                elif total_spent > 100:
                    spending_tier = "Low Spender"
                else:
                    spending_tier = "No Purchase"

                print(f"      - user_spending_tier: '{spending_tier}'")
                print(
                    f"      - user_avg_order_value: {total_spent/order_count:.2f if order_count > 0 else 0}"
                )
                print(f"      - user_total_spent: {total_spent:.2f}")

                # Product preference features
                if product_types:
                    print(
                        f"      - user_preferred_product_types: {list(product_types)}"
                    )
                if vendors:
                    print(f"      - user_preferred_vendors: {list(vendors)}")
                if collections:
                    print(f"      - user_preferred_collections: {list(collections)}")
                if unique_tags:
                    print(f"      - user_product_tag_preferences: {unique_tags[:10]}")

                # Temporal features
                if order_dates:
                    print(f"      - user_first_order_date: '{min(order_dates)}'")
                    print(f"      - user_last_order_date: '{max(order_dates)}'")
                    print(
                        f"      - user_order_frequency_days: {self._calculate_order_frequency(order_dates)}"
                    )

            # Event features
            if events:
                print(f"      - user_events_count: {len(events)}")
                event_type_counts = {}
                for event_edge in events:
                    event = event_edge["node"]
                    event_type = event.get("__typename", "Unknown")
                    event_type_counts[event_type] = (
                        event_type_counts.get(event_type, 0) + 1
                    )

                for event_type, count in event_type_counts.items():
                    print(f"      - user_{event_type.lower()}_count: {count}")

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
                    print(f"      - user_metafield_{key}: '{value}'")

            # Generate Gorse ML training data structure
            print(f"\n🚀 Gorse ML Training Data Structure:")
            print(f"   Interactions (from orders):")
            if orders:
                for i, order_edge in enumerate(orders[:3]):  # Show first 3 orders
                    order = order_edge["node"]
                    line_items = order.get("lineItems", {}).get("edges", [])

                    for item_edge in line_items:
                        item = item_edge["node"]
                        variant = item.get("variant", {})
                        product = variant.get("product", {})

                        print(f"      Interaction {i+1}:")
                        print(f"         - user_id: '{customer['id']}'")
                        print(f"         - item_id: '{product.get('id', '')}'")
                        print(f"         - rating: 5")  # Purchase = 5-star rating
                        print(f"         - timestamp: '{order.get('createdAt', '')}'")
                        print(f"         - quantity: {item.get('quantity', 1)}")
                        print(
                            f"         - order_total: {order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', '0')}"
                        )
                        print(f"         - order_id: '{order['name']}'")
                        print(
                            f"         - product_type: '{product.get('productType', '')}'"
                        )
                        print(
                            f"         - product_vendor: '{product.get('vendor', '')}'"
                        )
                        print(f"         - product_tags: {product.get('tags', [])}")

    def _calculate_order_frequency(self, order_dates):
        """Calculate average days between orders"""
        if len(order_dates) < 2:
            return 0

        # Convert ISO dates to datetime and calculate differences
        try:
            from datetime import datetime

            dates = [
                datetime.fromisoformat(date.replace("Z", "+00:00"))
                for date in order_dates
            ]
            dates.sort()

            total_days = 0
            for i in range(1, len(dates)):
                diff = (dates[i] - dates[i - 1]).days
                total_days += diff

            return total_days / (len(dates) - 1)
        except:
            return 0

    def analyze_general_events(self, events_data: dict):
        """Analyze general events data"""
        if not events_data or "data" not in events_data:
            print("❌ No general events data to analyze")
            return

        events = events_data["data"]["events"]["edges"]
        print(f"\n📊 General Events Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(events)} general events")

        if events:
            # Analyze event types
            event_types = {}
            for event_edge in events:
                event = event_edge["node"]
                event_type = event.get("__typename", "Unknown")
                event_types[event_type] = event_types.get(event_type, 0) + 1

            print(f"   Event Type Distribution:")
            for event_type, count in event_types.items():
                print(f"      - {event_type}: {count}")

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   Event Features:")
            print(f"      - total_events: {len(events)}")
            for event_type, count in event_types.items():
                print(f"      - {event_type.lower()}_count: {count}")


async def main():
    """Test the simplified customer events API"""
    api = SimplifiedCustomerEventsAPI()

    print("🚀 Testing Simplified Shopify Customer Events API")
    print("=" * 60)
    print("Extracting rich behavioral data for Gorse ML training")

    # Get customer behavior data
    print("\n1️⃣ Testing Customer Behavior Data...")
    behavior_data = await api.get_customer_behavior_data(first=5)
    if behavior_data:
        api.analyze_customer_behavior(behavior_data)
    else:
        print("❌ Failed to fetch customer behavior data")

    # Get general events
    print("\n2️⃣ Testing General Events...")
    general_events = await api.get_general_events(first=10)
    if general_events:
        api.analyze_general_events(general_events)
    else:
        print("❌ Failed to fetch general events")


if __name__ == "__main__":
    asyncio.run(main())
