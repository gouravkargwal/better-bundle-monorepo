#!/usr/bin/env python3
"""
Shopify Customer API Query

This script contains the correct GraphQL query for customers based on
the actual Shopify GraphQL schema.
"""

import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ShopifyCustomerAPI:
    """Shopify Customer API with correct GraphQL query"""

    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01/graphql.json"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def get_customers(self, first: int = 50):
        """Get customers using the correct GraphQL query based on actual schema"""

        # GraphQL query matching the provided API format
        query = """
        query CustomerList($first: Int!) {
            customers(first: $first) {
                nodes {
                    id
                    firstName
                    lastName

                    createdAt
                    updatedAt
                    numberOfOrders
                    state
                    amountSpent {
                        amount
                        currencyCode
                    }
                    verifiedEmail
                    taxExempt
                    tags
                    addresses {
                        id
                        firstName
                        lastName
                        address1
                        city
                        province
                        country
                        zip
                        phone
                        name
                        provinceCode
                        countryCodeV2
                    }
                    defaultAddress {
                        id
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

    async def get_single_customer(self, customer_id: str):
        """Get a single customer by ID"""

        query = """
        query GetCustomer($id: ID!) {
            customer(id: $id) {
                id
                firstName
                lastName
                email

                createdAt
                updatedAt
                numberOfOrders
                state
                amountSpent {
                    amount
                    currencyCode
                }
                verifiedEmail
                taxExempt
                tags
                addresses {
                    id
                    firstName
                    lastName
                    address1
                    city
                    province
                    country
                    zip
                    phone
                    name
                    provinceCode
                    countryCodeV2
                }
                defaultAddress {
                    id
                    address1
                    city
                    province
                    country
                    zip
                    phone
                    provinceCode
                    countryCodeV2
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

        variables = {"id": customer_id}

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

    def analyze_customer_data(self, customer_data: dict):
        """Analyze the customer data structure for Gorse ML features"""
        if not customer_data or "data" not in customer_data:
            print("❌ No customer data to analyze")
            return

        customers = customer_data["data"]["customers"]["nodes"]
        print(f"\n📊 Customer Data Analysis")
        print(f"=" * 40)
        print(f"Found {len(customers)} customers")

        if customers:
            # Analyze first customer
            customer = customers[0]

            print(f"\n🎯 Sample Customer Structure:")
            print(f"   Basic Info:")
            print(f"      - ID: {customer['id']}")
            print(
                f"      - Name: {customer.get('firstName', 'N/A')} {customer.get('lastName', 'N/A')}"
            )
            print(f"      - Created: {customer.get('createdAt', 'N/A')}")
            print(f"      - Updated: {customer.get('updatedAt', 'N/A')}")
            print(f"      - State: {customer.get('state', 'N/A')}")
            print(f"      - Verified Email: {customer.get('verifiedEmail', 'N/A')}")
            print(f"      - Tax Exempt: {customer.get('taxExempt', 'N/A')}")
            print(f"      - Tags: {customer.get('tags', [])}")

            # Contact Information
            print(f"   Contact Info:")
            print(f"      - Email: {customer.get('email', 'N/A')}")
            print(f"      - Phone: {customer.get('phone', 'N/A')}")

            # Behavioral Data
            print(f"   Behavioral Data:")
            print(f"      - Number of Orders: {customer.get('numberOfOrders', 0)}")
            amount_spent = customer.get("amountSpent", {})
            print(
                f"      - Amount Spent: ${amount_spent.get('amount', '0')} {amount_spent.get('currencyCode', '')}"
            )

            # Addresses
            addresses = customer.get("addresses", [])
            default_address = customer.get("defaultAddress", {})
            print(f"   Addresses:")
            print(f"      - Total Addresses: {len(addresses)}")
            print(
                f"      - Default Address: {default_address.get('city', 'N/A')}, {default_address.get('province', 'N/A')}"
            )

            print(f"\n🎯 Gorse ML Features Available:")
            print(f"   User Features:")
            print(f"      - user_id: {customer['id']}")
            print(
                f"      - user_name: '{customer.get('firstName', '')} {customer.get('lastName', '')}'"
            )
            print(f"      - user_email: '{customer.get('email', '')}'")
            print(f"      - user_phone: '{customer.get('phone', '')}'")
            print(f"      - user_created_at: '{customer.get('createdAt', '')}'")
            print(f"      - user_updated_at: '{customer.get('updatedAt', '')}'")
            print(f"      - user_state: '{customer.get('state', '')}'")
            print(
                f"      - user_verified_email: {customer.get('verifiedEmail', False)}"
            )
            print(f"      - user_tax_exempt: {customer.get('taxExempt', False)}")
            print(f"      - user_tags: {customer.get('tags', [])}")
            print(f"      - user_number_of_orders: {customer.get('numberOfOrders', 0)}")
            print(f"      - user_amount_spent: {amount_spent.get('amount', 0)}")
            print(f"      - user_currency: '{amount_spent.get('currencyCode', '')}'")
            print(f"      - user_addresses_count: {len(addresses)}")
            print(f"      - user_has_default_address: {bool(default_address)}")

            # Marketing features
            print(f"      - user_email_marketing_state: 'N/A'")
            print(f"      - user_phone_marketing_state: 'N/A'")
            print(f"      - user_phone_marketing_collected_from: 'N/A'")

            # Location features
            if default_address:
                print(f"      - user_default_city: '{default_address.get('city', '')}'")
                print(
                    f"      - user_default_province: '{default_address.get('province', '')}'"
                )
                print(
                    f"      - user_default_country: '{default_address.get('country', '')}'"
                )
                print(
                    f"      - user_default_province_code: '{default_address.get('provinceCode', '')}'"
                )
                print(
                    f"      - user_default_country_code: '{default_address.get('countryCodeV2', '')}'"
                )

            # Customer segmentation features
            orders_count = int(customer.get("numberOfOrders", 0))
            if orders_count > 10:
                customer_type = "High Value"
            elif orders_count > 5:
                customer_type = "Medium Value"
            elif orders_count > 0:
                customer_type = "Low Value"
            else:
                customer_type = "No Purchase"

            print(f"      - user_customer_type: '{customer_type}'")

            # Spending tier
            amount = float(amount_spent.get("amount", 0))
            if amount > 1000:
                spending_tier = "High Spender"
            elif amount > 500:
                spending_tier = "Medium Spender"
            elif amount > 100:
                spending_tier = "Low Spender"
            else:
                spending_tier = "No Purchase"

            print(f"      - user_spending_tier: '{spending_tier}'")

            # Metafields analysis
            metafields = customer.get("metafields", {}).get("edges", [])
            if metafields:
                print(f"      - user_metafields_count: {len(metafields)}")
                metafield_dict = {}
                for mf in metafields:
                    namespace = mf["node"].get("namespace", "")
                    key = mf["node"].get("key", "")
                    value = mf["node"].get("value", "")
                    if namespace and key:
                        metafield_dict[f"{namespace}_{key}"] = value

                for key, value in list(metafield_dict.items())[:5]:  # Limit to first 5
                    print(f"      - user_metafield_{key}: '{value}'")


async def main():
    """Test the customer API"""
    api = ShopifyCustomerAPI()

    print("🚀 Testing Shopify Customer API")
    print("=" * 40)

    # Get customers
    customers = await api.get_customers(first=10)
    if customers:
        api.analyze_customer_data(customers)
    else:
        print("❌ Failed to fetch customers")


if __name__ == "__main__":
    asyncio.run(main())
