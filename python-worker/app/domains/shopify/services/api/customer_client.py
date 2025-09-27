"""
Shopify Customer API client with full data traversal support
"""

from typing import Dict, Any, Optional, List
from app.core.logging import get_logger
from .base_client import BaseShopifyAPIClient

logger = get_logger(__name__)


class CustomerAPIClient(BaseShopifyAPIClient):
    """Shopify Customer API client with full data traversal"""

    async def get_customers(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        customer_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get customers from shop - supports both pagination and specific IDs"""
        # Handle specific customer IDs (for webhooks)
        if customer_ids:
            return await self._get_customers_by_ids(shop_domain, customer_ids)

        # Regular pagination logic
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }

        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
            customers(first: $first, after: $after, query: $query) {
                page_info: pageInfo {
                    has_next_page: hasNextPage
                    has_previous_page: hasPreviousPage
                    start_cursor: startCursor
                    end_cursor: endCursor
                }
                edges {
                    cursor
                    node {
                        id
                        email
                        first_name: firstName
                        last_name: lastName
                        phone
                        created_at: createdAt
                        updated_at: updatedAt
                        accepts_marketing: acceptsMarketing
                        marketing_opt_in_level: marketingOptInLevel
                        state
                        note
                        tags
                        verified_email: verifiedEmail
                        multipass_identifier: multipassIdentifier
                        tax_exempt: taxExempt
                        tax_exemptions: taxExemptions
                        total_spent: totalSpent
                        orders_count: ordersCount
                        default_address: defaultAddress {
                            id
                            first_name: firstName
                            last_name: lastName
                            company
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
                        }
                        addresses(first: 10) {
                            edges {
                                node {
                                    id
                                    first_name: firstName
                                    last_name: lastName
                                    company
                                    address1
                                    address2
                                    city
                                    province
                                    country
                                    zip
                                    phone
                                }
                            }
                            page_info: pageInfo {
                                has_next_page: hasNextPage
                                has_previous_page: hasPreviousPage
                                start_cursor: startCursor
                                end_cursor: endCursor
                            }
                        }
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        customers_data = result.get("customers", {})

        # Process each customer to fetch all addresses if needed
        if customers_data.get("edges"):
            processed_customers = []

            for customer_edge in customers_data["edges"]:
                customer = customer_edge["node"]

                # Check and fetch additional addresses if needed
                addresses = customer.get("addresses", {})
                addresses_page_info = addresses.get("page_info", {})
                if addresses_page_info.get("has_next_page"):
                    all_addresses = addresses.get("edges", []).copy()
                    addresses_cursor = addresses_page_info.get("end_cursor")

                    while addresses_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        addresses_batch = await self._fetch_customer_addresses(
                            shop_domain, customer["id"], addresses_cursor
                        )
                        if not addresses_batch:
                            break

                        new_addresses = addresses_batch.get("edges", [])
                        all_addresses.extend(new_addresses)

                        page_info = addresses_batch.get("page_info", {})
                        addresses_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    customer["addresses"] = {
                        "edges": all_addresses,
                        "page_info": {"has_next_page": False},
                    }

                processed_customers.append(customer)

            # Return in the same format as the original query
            return {
                "edges": [{"node": customer} for customer in processed_customers],
                "page_info": {"has_next_page": False},
            }

        return customers_data

    async def _get_customers_by_ids(
        self, shop_domain: str, customer_ids: List[str]
    ) -> Dict[str, Any]:
        """Get specific customers by IDs - reuses existing logic for addresses"""
        processed_customers = []

        for customer_id in customer_ids:
            try:
                # Get single customer with full data (addresses)
                customer_data = await self._get_single_customer_full_data(
                    shop_domain, customer_id
                )
                if customer_data:
                    processed_customers.append(customer_data)
            except Exception as e:
                logger.error(f"Failed to fetch customer {customer_id}: {e}")

        # Return in the same format as the original query
        return {
            "edges": [{"node": customer} for customer in processed_customers],
            "page_info": {"has_next_page": False},
        }

    async def _get_single_customer_full_data(
        self, shop_domain: str, customer_id: str
    ) -> Dict[str, Any]:
        """Get a single customer with all addresses - reuses existing logic"""
        graphql_query = """
        query($id: ID!) {
            customer(id: $id) {
                id
                email
                firstName
                lastName
                phone
                createdAt
                updatedAt
                acceptsMarketing
                marketingOptInLevel
                state
                note
                tags
                verifiedEmail
                multipassIdentifier
                taxExempt
                taxExemptions
                totalSpent
                ordersCount
                defaultAddress {
                    id
                    firstName
                    lastName
                    company
                    address1
                    address2
                    city
                    province
                    country
                    zip
                    phone
                }
                addresses(first: 10) {
                    edges {
                        node {
                            id
                            firstName
                            lastName
                            company
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
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
        }
        """

        variables = {"id": f"gid://shopify/Customer/{customer_id}"}
        result = await self.execute_query(graphql_query, variables, shop_domain)
        customer = result.get("customer", {})

        if not customer:
            return None

        # Reuse the same logic for fetching additional addresses
        # Check and fetch additional addresses if needed
        addresses = customer.get("addresses", {})
        addresses_page_info = addresses.get("pageInfo", {})
        if addresses_page_info.get("hasNextPage"):
            all_addresses = addresses.get("edges", []).copy()
            addresses_cursor = addresses_page_info.get("endCursor")

            while addresses_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

                addresses_batch = await self._fetch_customer_addresses(
                    shop_domain, customer["id"], addresses_cursor
                )
                if not addresses_batch:
                    break

                new_addresses = addresses_batch.get("edges", [])
                all_addresses.extend(new_addresses)

                page_info = addresses_batch.get("page_info", {})
                addresses_cursor = (
                    page_info.get("end_cursor")
                    if page_info.get("has_next_page")
                    else None
                )

            customer["addresses"] = {
                "edges": all_addresses,
                "page_info": {"has_next_page": False},
            }

        return customer

    async def _fetch_customer_addresses(
        self, shop_domain: str, customer_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of addresses for a specific customer"""
        addresses_query = """
        query($customerId: ID!, $first: Int!, $after: String) {
            customer(id: $customerId) {
                addresses(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            firstName
                            lastName
                            company
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
                        }
                    }
                    page_info: pageInfo {
                        has_next_page: hasNextPage
                        end_cursor: endCursor
                    }
                }
            }
        }
        """

        variables = {
            "customerId": customer_id,
            "first": 250,  # Max batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(addresses_query, variables, shop_domain)
        customer_data = result.get("customer", {})
        return customer_data.get("addresses", {})
