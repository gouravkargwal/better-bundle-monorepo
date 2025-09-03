#!/usr/bin/env python3
"""
Shopify Customer Events Introspection

This script performs GraphQL introspection to discover what customer events
and behavioral data is available for Gorse ML training.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class CustomerEventsIntrospection:
    """Introspect Shopify GraphQL schema for customer events"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def introspect_customer_events(self):
        """Introspect the customer events schema"""

        # Introspection query for customer events
        introspection_query = """
        query IntrospectCustomerEvents {
            __schema {
                types {
                    name
                    description
                    fields {
                        name
                        description
                        type {
                            name
                            kind
                            ofType {
                                name
                                kind
                                ofType {
                                    name
                                    kind
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": introspection_query},
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
            print(f"❌ Introspection failed: {e}")
            return {}

    async def search_for_customer_events(self):
        """Search for customer events related types in the schema"""

        # Search query for customer events
        search_query = """
        query SearchCustomerEvents {
            __schema {
                types {
                    name
                    description
                    fields {
                        name
                        description
                        type {
                            name
                            kind
                            ofType {
                                name
                                kind
                                ofType {
                                    name
                                    kind
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": search_query},
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
            print(f"❌ Search failed: {e}")
            return {}

    async def test_customer_events_query(self):
        """Test a basic customer events query to see what's available"""

        # Test query for customer events
        test_query = """
        query TestCustomerEvents {
            customerEvents(first: 5) {
                edges {
                    node {
                        id
                        eventType
                        occurredAt
                        customer {
                            id
                            firstName
                            lastName
                        }
                        product {
                            id
                            title
                        }
                        searchQuery
                        pageUrl
                        referrerUrl
                        userAgent
                        ipAddress
                        sessionId
                        cartToken
                        order {
                            id
                            name
                        }
                        lineItem {
                            id
                            title
                            quantity
                        }
                        collection {
                            id
                            title
                        }
                        page {
                            id
                            title
                        }
                        blog {
                            id
                            title
                        }
                        article {
                            id
                            title
                        }
                        discountCode
                        currencyCode
                        totalAmount {
                            amount
                            currencyCode
                        }
                        subtotalAmount {
                            amount
                            currencyCode
                        }
                        taxAmount {
                            amount
                            currencyCode
                        }
                        shippingAmount {
                            amount
                            currencyCode
                        }
                        discountAmount {
                            amount
                            currencyCode
                        }
                        tags
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
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
            }
        }
        """

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": test_query},
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
            print(f"❌ Test query failed: {e}")
            return {}

    async def test_customer_activity(self):
        """Test customer activity and behavior queries"""

        # Test query for customer activity
        activity_query = """
        query TestCustomerActivity {
            customers(first: 3) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        events(first: 5) {
                            edges {
                                node {
                                    id
                                    eventType
                                    occurredAt
                                    product {
                                        id
                                        title
                                    }
                                    searchQuery
                                    pageUrl
                                }
                            }
                        }
                        orders(first: 3) {
                            edges {
                                node {
                                    id
                                    name
                                    createdAt
                                    totalPriceSet {
                                        shopMoney {
                                            amount
                                            currencyCode
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

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": activity_query},
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
            print(f"❌ Activity query failed: {e}")
            return {}

    async def test_search_analytics(self):
        """Test search analytics and behavior"""

        # Test query for search analytics
        search_query = """
        query TestSearchAnalytics {
            shop {
                analytics {
                    searchAnalytics {
                        topSearches {
                            query
                            count
                            conversionRate
                            averageOrderValue {
                                amount
                                currencyCode
                            }
                        }
                        searchTerms(first: 10) {
                            edges {
                                node {
                                    term
                                    count
                                    conversionRate
                                    averageOrderValue {
                                        amount
                                        currencyCode
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": search_query},
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
            print(f"❌ Search analytics failed: {e}")
            return {}

    def analyze_customer_events_data(self, events_data: dict):
        """Analyze customer events data structure"""
        if not events_data or "data" not in events_data:
            print("❌ No customer events data to analyze")
            return

        if "customerEvents" in events_data["data"]:
            events = events_data["data"]["customerEvents"]["edges"]
            print(f"\n📊 Customer Events Data Analysis")
            print(f"=" * 40)
            print(f"Found {len(events)} customer events")

            if events:
                # Analyze first event
                event = events[0]["node"]
                print(f"\n🎯 Sample Event Structure:")
                print(f"   Basic Info:")
                print(f"      - ID: {event.get('id', 'N/A')}")
                print(f"      - Type: {event.get('eventType', 'N/A')}")
                print(f"      - Occurred: {event.get('occurredAt', 'N/A')}")

                # Customer info
                customer = event.get("customer", {})
                if customer:
                    print(f"   Customer:")
                    print(f"      - ID: {customer.get('id', 'N/A')}")
                    print(
                        f"      - Name: {customer.get('firstName', 'N/A')} {customer.get('lastName', 'N/A')}"
                    )

                # Product info
                product = event.get("product", {})
                if product:
                    print(f"   Product:")
                    print(f"      - ID: {product.get('id', 'N/A')}")
                    print(f"      - Title: {product.get('title', 'N/A')}")

                # Search info
                if event.get("searchQuery"):
                    print(f"   Search:")
                    print(f"      - Query: '{event.get('searchQuery')}'")

                # Page info
                if event.get("pageUrl"):
                    print(f"   Page:")
                    print(f"      - URL: {event.get('pageUrl')}")

                # Additional fields
                additional_fields = []
                for key, value in event.items():
                    if value and key not in [
                        "id",
                        "eventType",
                        "occurredAt",
                        "customer",
                        "product",
                        "searchQuery",
                        "pageUrl",
                    ]:
                        additional_fields.append(f"{key}: {value}")

                if additional_fields:
                    print(f"   Additional Fields:")
                    for field in additional_fields[:10]:  # Limit to first 10
                        print(f"      - {field}")

                print(f"\n🎯 Gorse ML Features Available:")
                print(f"   Event Features:")
                print(f"      - event_id: '{event.get('id', '')}'")
                print(f"      - event_type: '{event.get('eventType', '')}'")
                print(f"      - event_timestamp: '{event.get('occurredAt', '')}'")
                print(f"      - user_id: '{customer.get('id', '')}'")
                print(f"      - item_id: '{product.get('id', '')}'")

                if event.get("searchQuery"):
                    print(f"      - search_query: '{event.get('searchQuery')}'")
                if event.get("pageUrl"):
                    print(f"      - page_url: '{event.get('pageUrl')}'")
                if event.get("referrerUrl"):
                    print(f"      - referrer_url: '{event.get('referrerUrl')}'")
                if event.get("sessionId"):
                    print(f"      - session_id: '{event.get('sessionId')}'")
                if event.get("cartToken"):
                    print(f"      - cart_token: '{event.get('cartToken')}'")

        elif "customers" in events_data["data"]:
            customers = events_data["data"]["customers"]["edges"]
            print(f"\n📊 Customer Activity Data Analysis")
            print(f"=" * 40)
            print(f"Found {len(customers)} customers with activity")

            if customers:
                customer = customers[0]["node"]
                print(f"\n🎯 Sample Customer Activity:")
                print(
                    f"   Customer: {customer.get('firstName', 'N/A')} {customer.get('lastName', 'N/A')}"
                )

                events = customer.get("events", {}).get("edges", [])
                if events:
                    print(f"   Events: {len(events)}")
                    for i, event_edge in enumerate(events[:3]):
                        event = event_edge["node"]
                        print(
                            f"      Event {i+1}: {event.get('eventType', 'N/A')} - {event.get('occurredAt', 'N/A')}"
                        )
                        if event.get("product"):
                            print(f"         Product: {event['product']['title']}")
                        if event.get("searchQuery"):
                            print(f"         Search: '{event['searchQuery']}'")

                orders = customer.get("orders", {}).get("edges", [])
                if orders:
                    print(f"   Orders: {len(orders)}")
                    for i, order_edge in enumerate(orders[:2]):
                        order = order_edge["node"]
                        total = (
                            order.get("totalPriceSet", {})
                            .get("shopMoney", {})
                            .get("amount", "N/A")
                        )
                        print(f"      Order {i+1}: {order['name']} - ${total}")

        elif "shop" in events_data["data"]:
            shop = events_data["data"]["shop"]
            if "analytics" in shop and shop["analytics"]:
                analytics = shop["analytics"]
                print(f"\n📊 Shop Analytics Data Analysis")
                print(f"=" * 40)

                if "searchAnalytics" in analytics:
                    search_analytics = analytics["searchAnalytics"]
                    print(f"   Search Analytics Available:")

                    if "topSearches" in search_analytics:
                        top_searches = search_analytics["topSearches"]
                        print(f"      - Top Searches: {len(top_searches)}")

                    if "searchTerms" in search_analytics:
                        search_terms = search_analytics["searchTerms"]["edges"]
                        print(f"      - Search Terms: {len(search_terms)}")

                        if search_terms:
                            term = search_terms[0]["node"]
                            print(f"   Sample Search Term:")
                            print(f"      - Term: '{term.get('term', 'N/A')}'")
                            print(f"      - Count: {term.get('count', 'N/A')}")
                            print(
                                f"      - Conversion Rate: {term.get('conversionRate', 'N/A')}%"
                            )
                            print(
                                f"      - Avg Order Value: ${term.get('averageOrderValue', {}).get('amount', 'N/A')}"
                            )


async def main():
    """Run customer events introspection"""
    introspection = CustomerEventsIntrospection()

    print("🔍 Shopify Customer Events Introspection")
    print("=" * 50)

    # Test customer events query
    print("\n1️⃣ Testing Customer Events Query...")
    events_data = await introspection.test_customer_events_query()
    if events_data:
        introspection.analyze_customer_events_data(events_data)
    else:
        print("❌ Customer events query failed")

    # Test customer activity
    print("\n2️⃣ Testing Customer Activity...")
    activity_data = await introspection.test_customer_activity()
    if activity_data:
        introspection.analyze_customer_events_data(activity_data)
    else:
        print("❌ Customer activity query failed")

    # Test search analytics
    print("\n3️⃣ Testing Search Analytics...")
    search_data = await introspection.test_search_analytics()
    if search_data:
        introspection.analyze_customer_events_data(search_data)
    else:
        print("❌ Search analytics query failed")


if __name__ == "__main__":
    asyncio.run(main())
