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
                        first_name: firstName
                        last_name: lastName
                        created_at: createdAt
                        updated_at: updatedAt
                        state
                        note
                        tags
                        verified_email: verifiedEmail
                        multipass_identifier: multipassIdentifier
                        tax_exempt: taxExempt
                        tax_exemptions: taxExemptions
                        total_spent: amountSpent {
                            amount
                            currency_code: currencyCode
                        }
                        orders_count: numberOfOrders
                        default_address: defaultAddress {
                            id
                            first_name: firstName
                            last_name: lastName
                            company
                            city
                            province
                            country
                        }
                        addresses {
                            id
                            first_name: firstName
                            last_name: lastName
                            company
                            city
                            province
                            country
                        }
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        customers_data = result.get("customers", {})

        # Process each customer - addresses are now directly available
        if customers_data.get("edges"):
            processed_customers = []

            for customer_edge in customers_data["edges"]:
                customer = customer_edge["node"]
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
                first_name: firstName
                last_name: lastName
                created_at: createdAt
                updated_at: updatedAt
                state
                note
                tags
                verified_email: verifiedEmail
                multipass_identifier: multipassIdentifier
                tax_exempt: taxExempt
                tax_exemptions: taxExemptions
                total_spent: amountSpent {
                    amount
                    currency_code: currencyCode
                }
                orders_count: numberOfOrders
                default_address: defaultAddress {
                    id
                    first_name: firstName
                    last_name: lastName
                    company
                    city
                    province
                    country
                }
                addresses {
                    id
                    first_name: firstName
                    last_name: lastName
                    company
                    city
                    province
                    country
                }
            }
        }
        """

        variables = {"id": f"gid://shopify/Customer/{customer_id}"}
        result = await self.execute_query(graphql_query, variables, shop_domain)
        customer = result.get("customer", {})

        if not customer:
            return None

        # Addresses are now directly available as an array
        # No need for pagination logic

        return customer
