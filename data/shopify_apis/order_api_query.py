#!/usr/bin/env python3
"""
Shopify Order API Query

This script contains the correct GraphQL query for orders based on
the actual Shopify GraphQL schema discovered through introspection.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyOrderAPI:
    """Shopify Order API with correct GraphQL query"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_orders(self, first: int = 50):
        """Get orders using the correct GraphQL query based on actual schema"""

        # GraphQL query based on schema introspection - orders is available
        query = """
        query GetOrders($first: Int!) {
            orders(first: $first) {
                edges {
                    node {
                        id
                        name
                        email
                        phone
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
                        customer {
                            id
                            firstName
                            lastName
                            email
                            tags
                        }
                        lineItems(first: 10) {
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
                        tags
                        note
                        confirmed
                        test
                        totalRefundedSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        totalOutstandingSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        customerLocale
                        currencyCode
                        presentmentCurrencyCode

                        discountApplications(first: 5) {
                            edges {
                                node {
                                    value {
                                        ... on MoneyV2 {
                                            amount
                                            currencyCode
                                        }
                                        ... on PricingPercentageValue {
                                            percentage
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

    async def get_single_order(self, order_id: str):
        """Get a single order by ID"""

        query = """
        query GetOrder($id: ID!) {
            order(id: $id) {
                id
                name
                email
                phone
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
                customer {
                    id
                    firstName
                    lastName
                    email
                    tags
                }
                lineItems(first: 20) {
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
                tags
                note
                confirmed
                test
                totalRefundedSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                totalOutstandingSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                customerLocale
                currencyCode
                presentmentCurrencyCode

                discountApplications(first: 10) {
                    edges {
                        node {
                            value {
                                ... on MoneyV2 {
                                    amount
                                    currencyCode
                                }
                                ... on PricingPercentageValue {
                                    percentage
                                }
                            }
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

        variables = {"id": order_id}

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

    def analyze_order_data(self, order_data: dict):
        """Analyze the order data structure for Gorse ML features"""
        if not order_data or "data" not in order_data:
            print("❌ No order data to analyze")
            return

        orders = order_data["data"]["orders"]["edges"]
        print(f"\n📊 Order Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(orders)} orders")

        if orders:
            # Analyze first order
            order = orders[0]["node"]

            print(f"\n🎯 Sample Order Structure:")
            print(f"   Basic Info:")
            print(f"      - ID: {order['name']}")
            print(
                f"      - Customer: {order.get('customer', {}).get('firstName', 'N/A')} {order.get('customer', {}).get('lastName', 'N/A')}"
            )
            print(f"      - Email: {order.get('email', 'N/A')}")
            print(f"      - Created: {order.get('createdAt', 'N/A')}")
            print(
                f"      - Status: {'Cancelled' if order.get('cancelledAt') else 'Active'}"
            )
            print(f"      - Fulfillment: {order.get('fulfillmentStatus', 'N/A')}")
            print(f"      - Financial: {order.get('financialStatus', 'N/A')}")
            print(f"      - Test Order: {order.get('test', False)}")

            # Financial information
            total_price = float(order["totalPriceSet"]["shopMoney"]["amount"])
            subtotal = float(order["subtotalPriceSet"]["shopMoney"]["amount"])
            tax = float(order["totalTaxSet"]["shopMoney"]["amount"])
            shipping = float(order["totalShippingPriceSet"]["shopMoney"]["amount"])

            print(f"   Financial:")
            print(f"      - Total: ${total_price}")
            print(f"      - Subtotal: ${subtotal}")
            print(f"      - Tax: ${tax}")
            print(f"      - Shipping: ${shipping}")

            # Line items
            line_items = order.get("lineItems", {}).get("edges", [])
            if line_items:
                print(f"   Line Items: {len(line_items)}")
                for i, item_edge in enumerate(line_items[:3]):
                    item = item_edge["node"]
                    variant = item.get("variant", {})
                    product = variant.get("product", {})
                    print(f"      Item {i+1}: {item['title']} x{item['quantity']}")
                    print(f"         - Variant: {variant.get('title', 'N/A')}")
                    print(f"         - Product: {product.get('title', 'N/A')}")
                    print(f"         - Type: {product.get('productType', 'N/A')}")
                    print(f"         - Vendor: {product.get('vendor', 'N/A')}")

            # Addresses
            shipping_address = order.get("shippingAddress")
            billing_address = order.get("billingAddress")
            print(f"   Addresses:")
            if shipping_address:
                print(
                    f"      - Shipping: {shipping_address.get('city', 'N/A')}, {shipping_address.get('province', 'N/A')}"
                )
            else:
                print(f"      - Shipping: N/A")
            if billing_address:
                print(
                    f"      - Billing: {billing_address.get('city', 'N/A')}, {billing_address.get('province', 'N/A')}"
                )
            else:
                print(f"      - Billing: N/A")

            # Discounts
            discounts = order.get("discountApplications", {}).get("edges", [])
            if discounts:
                print(f"   Discounts: {len(discounts)}")
                for discount_edge in discounts[:2]:
                    discount = discount_edge["node"]
                    print(f"      - Type: {discount.get('type', 'N/A')}")

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   Interaction Features:")
            print(f"      - user_id: {order.get('customer', {}).get('id', '')}")
            print(
                f"      - item_id: {line_items[0]['node']['variant']['product']['id'] if line_items else ''}"
            )
            print(f"      - rating: 5")  # Purchase = 5-star rating
            print(f"      - timestamp: '{order.get('createdAt', '')}'")
            print(
                f"      - quantity: {line_items[0]['node']['quantity'] if line_items else 1}"
            )
            print(f"      - order_total: {total_price}")
            print(f"      - order_id: {order['name']}")
            print(f"      - order_status: '{order.get('fulfillmentStatus', '')}'")
            print(
                f"      - order_financial_status: '{order.get('financialStatus', '')}'"
            )
            print(f"      - order_test: {order.get('test', False)}")

            if line_items:
                product = line_items[0]["node"]["variant"]["product"]
                print(f"      - product_type: '{product.get('productType', '')}'")
                print(f"      - product_vendor: '{product.get('vendor', '')}'")
                print(f"      - product_tags: {product.get('tags', [])}")

            # Customer features
            customer = order.get("customer", {})
            if customer:
                print(f"      - customer_tags: {customer.get('tags', [])}")
                print(f"      - customer_email: '{customer.get('email', '')}'")

            # Location features
            if shipping_address:
                print(f"      - shipping_city: '{shipping_address.get('city', '')}'")
                print(
                    f"      - shipping_province: '{shipping_address.get('province', '')}'"
                )
                print(
                    f"      - shipping_country: '{shipping_address.get('country', '')}'"
                )
                print(
                    f"      - shipping_province_code: '{shipping_address.get('provinceCode', '')}'"
                )
                print(
                    f"      - shipping_country_code: '{shipping_address.get('countryCodeV2', '')}'"
                )

            # Order metadata
            print(f"      - order_tags: {order.get('tags', [])}")
            print(f"      - order_note: '{order.get('note', '')}'")
            print(f"      - order_currency: '{order.get('currencyCode', '')}'")
            print(f"      - order_customer_locale: '{order.get('customerLocale', '')}'")

            # App information
            app = order.get("app", {})
            if app:
                print(f"      - order_app_id: '{app.get('id', '')}'")
                print(f"      - order_app_title: '{app.get('title', '')}'")

            # Discount information
            if discounts:
                total_discount = 0
                for discount_edge in discounts:
                    discount = discount_edge["node"]
                    value = discount.get("value", {})
                    if "amount" in value:
                        total_discount += float(value["amount"])
                    elif "percentage" in value:
                        total_discount += (float(value["percentage"]) / 100) * subtotal

                print(f"      - order_total_discount: {total_discount:.2f}")
                print(f"      - order_discount_count: {len(discounts)}")

                # Order classification
            if total_price > 1000:
                order_value_tier = "High Value"
            elif total_price > 500:
                order_value_tier = "Medium Value"
            elif total_price > 100:
                order_value_tier = "Low Value"
            else:
                order_value_tier = "Minimal Value"

            print(f"      - order_value_tier: '{order_value_tier}'")

            # Metafields analysis
            metafields = order.get("metafields", {}).get("edges", [])
            if metafields:
                print(f"      - order_metafields_count: {len(metafields)}")
                metafield_dict = {}
                for mf in metafields:
                    namespace = mf["node"].get("namespace", "")
                    key = mf["node"].get("key", "")
                    value = mf["node"].get("value", "")
                    if namespace and key:
                        metafield_dict[f"{namespace}_{key}"] = value

                for key, value in list(metafield_dict.items())[:5]:  # Limit to first 5
                    print(f"      - order_metafield_{key}: '{value}'")

            # Line item analysis
            if line_items:
                total_items = sum(item["node"]["quantity"] for item in line_items)
                unique_products = len(
                    set(item["node"]["variant"]["product"]["id"] for item in line_items)
                )
                print(f"      - order_total_items: {total_items}")
                print(f"      - order_unique_products: {unique_products}")
                print(f"      - order_avg_item_value: {total_price / total_items:.2f}")


async def main():
    """Test the order API"""
    api = ShopifyOrderAPI()

    print("🚀 Testing Shopify Order API")
    print("=" * 40)

    # Get orders
    orders = await api.get_orders(first=5)
    if orders:
        api.analyze_order_data(orders)
    else:
        print("❌ Failed to fetch orders")


if __name__ == "__main__":
    asyncio.run(main())
