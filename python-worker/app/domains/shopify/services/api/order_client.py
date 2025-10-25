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
                            city
                            province
                            country
                        }
                        billing_address: billingAddress {
                            id
                            firstName
                            lastName
                            company
                            city
                            province
                            country
                        }
                        line_items: lineItems(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    quantity
                                    original_unit_original_unit_price: originalUnitPrice
                                    sku
                                    customAttributes {
                                        key
                                        value
                                    }
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
                        metafields(first: 50) {
                            edges {
                                node {
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                    description
                                    created_at: createdAt
                                    updated_at: updatedAt
                                }
                            }
                            page_info: pageInfo {
                                has_next_page: hasNextPage
                                end_cursor: endCursor
                            }
                        }
                        refunds {
                            id
                            created_at: createdAt
                            note
                            total_refunded: totalRefunded {
                                amount
                                currency_code: currencyCode
                            }
                            refund_line_items: refundLineItems(first: 10) {
                                edges {
                                    node {
                                        id
                                        quantity
                                        subtotal
                                        line_item: lineItem {
                                            id
                                            product {
                                                id
                                            }
                                            variant {
                                                id
                                            }
                                            title
                                            sku
                                            customAttributes {
                                                key
                                                value
                                            }
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

                # Check and fetch additional refund line items if needed
                refunds = order.get("refunds", [])
                if refunds:
                    processed_refunds = []
                    for refund in refunds:
                        # Process refund line items with pagination
                        refund_line_items = refund.get("refund_line_items", {})
                        if refund_line_items:
                            line_items_page_info = refund_line_items.get(
                                "page_info", {}
                            )
                            if line_items_page_info.get("has_next_page"):
                                # Fetch additional refund line items
                                all_line_items = refund_line_items.get(
                                    "edges", []
                                ).copy()
                                line_items_cursor = line_items_page_info.get(
                                    "end_cursor"
                                )

                                while line_items_cursor:
                                    rate_limit_info = await self.check_rate_limit(
                                        shop_domain
                                    )
                                    if not rate_limit_info["can_make_request"]:
                                        await self.wait_for_rate_limit(shop_domain)

                                    line_items_batch = (
                                        await self._fetch_refund_line_items(
                                            shop_domain, refund["id"], line_items_cursor
                                        )
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

                                refund["refund_line_items"] = {
                                    "edges": all_line_items,
                                    "page_info": {"has_next_page": False},
                                }
                        processed_refunds.append(refund)
                    order["refunds"] = processed_refunds

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
                    city
                    province
                    country
                }
                billing_address: billingAddress {
                    id
                    first_name: firstName
                    last_name: lastName
                    company
                    city
                    province
                    country
                }
                line_items: lineItems(first: 10) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            original_unit_price: originalUnitPrice
                            sku
                            custom_attributes: customAttributes {
                                key
                                value
                            }
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
                metafields(first: 50) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
                            description
                            created_at: createdAt
                            updated_at: updatedAt
                        }
                    }
                    page_info: pageInfo {
                        has_next_page: hasNextPage
                        end_cursor: endCursor
                    }
                }
                refunds {
                    id
                    created_at: createdAt
                    note
                    total_refunded: totalRefunded {
                        amount
                        currency_code: currencyCode
                    }
                    refund_line_items: refundLineItems(first: 10) {
                        edges {
                            node {
                                id
                                quantity
                                subtotal
                                line_item: lineItem {
                                    id
                                    product {
                                        id
                                    }
                                    variant {
                                        id
                                    }
                                    title
                                    sku
                                    customAttributes {
                                        key
                                        value
                                    }
                                }
                            }
                        }
                    }
                    transactions(first: 10) {
                        edges {
                            node {
                                id
                                kind
                                amount
                                gateway
                                status
                                created_at: createdAt
                            }
                        }
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

        # Process refunds with pagination for refund line items
        refunds = order.get("refunds", [])
        if refunds:
            processed_refunds = []
            for refund in refunds:
                # Process refund line items with pagination (similar to order line items)
                refund_line_items = refund.get("refund_line_items", {})
                if refund_line_items:
                    line_items_page_info = refund_line_items.get("pageInfo", {})
                    if line_items_page_info.get("hasNextPage"):
                        # Fetch additional refund line items
                        all_line_items = refund_line_items.get("edges", []).copy()
                        line_items_cursor = line_items_page_info.get("endCursor")

                        while line_items_cursor:
                            rate_limit_info = await self.check_rate_limit(shop_domain)
                            if not rate_limit_info["can_make_request"]:
                                await self.wait_for_rate_limit(shop_domain)

                            line_items_batch = await self._fetch_refund_line_items(
                                shop_domain, refund["id"], line_items_cursor
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

                        refund["refund_line_items"] = {
                            "edges": all_line_items,
                            "page_info": {"has_next_page": False},
                        }
                    else:
                        # No pagination needed, just format the data
                        line_item_edges = refund_line_items.get("edges", [])
                        refund["refund_line_items"] = {
                            "edges": line_item_edges,
                            "page_info": {"has_next_page": False},
                        }

                # Process transactions (connection format)
                transactions = refund.get("transactions", {})
                if transactions:
                    transaction_edges = transactions.get("edges", [])
                    refund["transactions"] = {
                        "edges": transaction_edges,
                        "page_info": {"has_next_page": False},
                    }

                processed_refunds.append(refund)

            # Convert to the expected format for consistency
            order["refunds"] = {
                "edges": [{"node": refund} for refund in processed_refunds],
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
                            original_unit_price: originalUnitPrice
                            sku
                            custom_attributes: customAttributes {
                                key
                                value
                            }
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

    async def _fetch_order_refunds(
        self, shop_domain: str, order_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of refunds for a specific order"""
        refunds_query = """
        query($orderId: ID!, $first: Int!, $after: String) {
            order(id: $orderId) {
                refunds(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            created_at: createdAt
                            note
                            total_refunded: totalRefunded {
                                amount
                                currency_code: currencyCode
                            }
                            refund_line_items: refundLineItems(first: 10) {
                                edges {
                                    node {
                                        id
                                        quantity
                                        subtotal
                                        line_item: lineItem {
                                            id
                                            product_id: productId
                                            variant_id: variantId
                                            title
                                            sku
                                            properties {
                                                key
                                                value
                                            }
                                        }
                                    }
                                }
                                page_info: pageInfo {
                                    has_next_page: hasNextPage
                                    end_cursor: endCursor
                                }
                            }
                            transactions {
                                id
                                kind
                                amount
                                currency
                                gateway
                                status
                                created_at: createdAt
                            }
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
            "first": 50,  # Smaller batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(refunds_query, variables, shop_domain)
        order_data = result.get("order", {})
        return order_data.get("refunds", {})

    async def _fetch_refund_line_items(
        self, shop_domain: str, refund_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of refund line items for a specific refund"""
        refund_line_items_query = """
        query($refundId: ID!, $first: Int!, $after: String) {
            refund(id: $refundId) {
                refund_line_items: refundLineItems(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            quantity
                            subtotal
                            line_item: lineItem {
                                id
                                product {
                                    id
                                }
                                variant {
                                    id
                                }
                                title
                                sku
                                customAttributes {
                                    key
                                    value
                                }
                            }
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
            "refundId": refund_id,
            "first": 250,  # Max batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(
            refund_line_items_query, variables, shop_domain
        )
        refund_data = result.get("refund", {})
        return refund_data.get("refund_line_items", {})
