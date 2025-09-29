"""
Shopify Order API client with full data traversal support
"""

from typing import Dict, Any, Optional, List
from app.core.logging import get_logger
from .base_client import BaseShopifyAPIClient

logger = get_logger(__name__)


class OrderAPIClient(BaseShopifyAPIClient):
    """Shopify Order API client with full data traversal"""

    async def get_orders(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        order_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get orders from shop - supports both pagination and specific IDs"""
        # Handle specific order IDs (for webhooks)
        if order_ids:
            return await self._get_orders_by_ids(shop_domain, order_ids)

        # Regular pagination logic
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }

        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
            orders(first: $first, after: $after, query: $query) {
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
                        name
                        created_at: createdAt
                        updated_at: updatedAt
                        processed_at: processedAt
                        cancelled_at: cancelledAt
                        closed_at: closedAt
                        total_price: totalPrice
                        subtotal_price: subtotalPrice
                        total_tax: totalTax
                        currency_code: currencyCode
                        financial_status: displayFinancialStatus
                        fulfillment_status: displayFulfillmentStatus
                        customer_locale: customerLocale
                        order_number: name
                        tags
                        note
                        test
                        confirmed
                        cancelled_at: cancelledAt
                        closed_at: closedAt
                        processed_at: processedAt
                        customer {
                            id
                            firstName
                            lastName
                        }
                        shipping_address: shippingAddress {
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
                        }
                        billing_address: billingAddress {
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
                        }
                        line_items: lineItems(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    quantity
                                    originalUnitPrice
                                    sku
                                    variant {
                                        id
                                    }
                                    product {
                                        id
                                    }
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
        orders_data = result.get("orders", {})

        # Process each order to fetch all line items if needed
        if orders_data.get("edges"):
            processed_orders = []

            for order_edge in orders_data["edges"]:
                order = order_edge["node"]

                # Check and fetch additional line items if needed
                line_items = order.get("line_items", {})
                line_items_page_info = line_items.get("page_info", {})
                if line_items_page_info.get("has_next_page"):
                    all_line_items = line_items.get("edges", []).copy()
                    line_items_cursor = line_items_page_info.get("end_cursor")

                    while line_items_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        line_items_batch = await self._fetch_order_line_items(
                            shop_domain, order["id"], line_items_cursor
                        )
                        if not line_items_batch:
                            break

                        new_line_items = line_items_batch.get("edges", [])
                        all_line_items.extend(new_line_items)

                        page_info = line_items_batch.get("page_info", {})
                        line_items_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    order["line_items"] = {
                        "edges": all_line_items,
                        "page_info": {"has_next_page": False},
                    }

                processed_orders.append(order)

            # Return in the same format as the original query
            return {
                "edges": [{"node": order} for order in processed_orders],
                "page_info": {"has_next_page": False},
            }

        return orders_data

    async def _get_orders_by_ids(
        self, shop_domain: str, order_ids: List[str]
    ) -> Dict[str, Any]:
        """Get specific orders by IDs - reuses existing logic for line items"""
        processed_orders = []

        for order_id in order_ids:
            try:
                # Get single order with full data (line items)
                order_data = await self._get_single_order_full_data(
                    shop_domain, order_id
                )
                if order_data:
                    processed_orders.append(order_data)
            except Exception as e:
                logger.error(f"Failed to fetch order {order_id}: {e}")

        # Return in the same format as the original query
        return {
            "edges": [{"node": order} for order in processed_orders],
            "page_info": {"has_next_page": False},
        }

    async def _get_single_order_full_data(
        self, shop_domain: str, order_id: str
    ) -> Dict[str, Any]:
        """Get a single order with all line items - reuses existing logic"""
        graphql_query = """
        query($id: ID!) {
            order(id: $id) {
                id
                name
                created_at: createdAt
                updated_at: updatedAt
                processed_at: processedAt
                cancelled_at: cancelledAt
                closed_at: closedAt
                total_price: totalPrice
                subtotal_price: subtotalPrice
                total_tax: totalTax
                currency_code: currencyCode
                financial_status: displayFinancialStatus
                fulfillment_status: displayFulfillmentStatus
                customer_locale: customerLocale
                order_number: name
                tags
                note
                test
                confirmed
                cancelled_at: cancelledAt
                closed_at: closedAt
                processed_at: processedAt
                customer {
                    id
                    first_name: firstName
                    last_name: lastName
                }
                shipping_address: shippingAddress {
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
                }
                billing_address: billingAddress {
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
                }
                line_items: lineItems(first: 10) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            price: originalUnitPrice
                            sku
                            variant_id: variant { id }
                            product_id: product { id }
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
        """

        variables = {"id": f"gid://shopify/Order/{order_id}"}
        result = await self.execute_query(graphql_query, variables, shop_domain)
        order = result.get("order", {})

        if not order:
            return None

        # Reuse the same logic for fetching additional line items
        # Check and fetch additional line items if needed
        line_items = order.get("lineItems", {})
        line_items_page_info = line_items.get("pageInfo", {})
        if line_items_page_info.get("hasNextPage"):
            all_line_items = line_items.get("edges", []).copy()
            line_items_cursor = line_items_page_info.get("endCursor")

            while line_items_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

                line_items_batch = await self._fetch_order_line_items(
                    shop_domain, order["id"], line_items_cursor
                )
                if not line_items_batch:
                    break

                new_line_items = line_items_batch.get("edges", [])
                all_line_items.extend(new_line_items)

                page_info = line_items_batch.get("page_info", {})
                line_items_cursor = (
                    page_info.get("end_cursor")
                    if page_info.get("has_next_page")
                    else None
                )

            order["line_items"] = {
                "edges": all_line_items,
                "page_info": {"has_next_page": False},
            }

        return order

    async def _fetch_order_line_items(
        self, shop_domain: str, order_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of line items for a specific order"""
        line_items_query = """
        query($orderId: ID!, $first: Int!, $after: String) {
            order(id: $orderId) {
                line_items: lineItems(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            price: originalUnitPrice
                            sku
                            variant_id: variant { id }
                            product_id: product { id }
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
            "orderId": order_id,
            "first": 250,  # Max batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(line_items_query, variables, shop_domain)
        order_data = result.get("order", {})
        return order_data.get("line_items", {})
