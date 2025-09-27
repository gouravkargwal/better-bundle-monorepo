"""
Shopify API client implementation for BetterBundle Python Worker
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import httpx

from app.core.logging import get_logger
from app.core.exceptions import ConfigurationError
from app.shared.decorators import retry, async_timing

from ..interfaces.api_client import IShopifyAPIClient

logger = get_logger(__name__)


class ShopifyAPIClient(IShopifyAPIClient):
    """Shopify GraphQL API client with rate limiting and error handling"""

    def __init__(self):
        self.base_url = "https://{shop}.myshopify.com"
        self.api_version = "2024-01"  # Latest stable version
        self.endpoint = "/admin/api/{version}/graphql.json"

        # Rate limiting based on Shopify's official limits
        self.rate_limit_buckets: Dict[str, Dict[str, Any]] = {}
        self.retry_after_header = "Retry-After"

        # Shopify GraphQL Admin API rate limits by plan (points per second)
        self.rate_limits = {
            "standard": 100,  # Standard Shopify
            "advanced": 200,  # Advanced Shopify
            "plus": 1000,  # Shopify Plus
            "enterprise": 2000,  # Shopify for enterprise (Commerce Components)
        }

        # Default to standard plan if not specified
        self.default_plan = "standard"

        # Enhanced rate limiting with exponential backoff
        self.max_retry_attempts = 5
        self.base_retry_delay = 1.0  # Base delay in seconds
        self.max_retry_delay = 300.0  # Maximum delay (5 minutes)
        self.backoff_multiplier = 2.0
        self.jitter_range = 0.1  # Add 10% jitter to prevent thundering herd

        # Query cost tracking (GraphQL uses calculated query cost)
        self.query_cost_tracking: Dict[str, Dict[str, Any]] = {}

        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = httpx.Timeout(30.0, connect=10.0)

        # Access tokens cache
        self.access_tokens: Dict[str, str] = {}

        # Required scopes for data collection
        self.required_scopes = [
            "read_products",
            "read_orders",
            "read_customers",
            "read_collections",
            "read_marketing_events",
        ]

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Initialize HTTP client"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "BetterBundle-PythonWorker/1.0",
                },
            )

    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def _get_shop_url(self, shop_domain: str) -> str:
        """Get full shop URL"""
        shop_name = (
            shop_domain.replace(".myshopify.com", "")
            .replace("https://", "")
            .replace("http://", "")
        )
        return self.base_url.format(shop=shop_name)

    def _get_graphql_endpoint(self, shop_domain: str) -> str:
        """Get GraphQL endpoint URL"""
        shop_url = self._get_shop_url(shop_domain)
        return urljoin(shop_url, self.endpoint.format(version=self.api_version))

    def _get_headers(self, shop_domain: str) -> Dict[str, str]:
        """Get request headers with access token"""
        access_token = self.access_tokens.get(shop_domain)
        if not access_token:
            raise ConfigurationError(
                f"No access token found for shop: {shop_domain}",
                config_key=shop_domain,
                details={"error_code": "SHOPIFY_NO_ACCESS_TOKEN"},
            )

        return {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    async def set_access_token(self, shop_domain: str, access_token: str):
        """Set access token for a shop"""
        self.access_tokens[shop_domain] = access_token

    def set_shop_plan(self, shop_domain: str, plan: str):
        """Set the Shopify plan for a shop to determine rate limits"""
        if plan not in self.rate_limits:
            logger.warning(
                f"Unknown Shopify plan '{plan}', using default plan '{self.default_plan}'",
                shop_domain=shop_domain,
                plan=plan,
            )
            plan = self.default_plan

        if shop_domain not in self.rate_limit_buckets:
            self.rate_limit_buckets[shop_domain] = {}

        self.rate_limit_buckets[shop_domain]["plan"] = plan
        logger.info(
            f"Set shop plan to '{plan}' with {self.rate_limits[plan]} points/second limit",
            shop_domain=shop_domain,
            plan=plan,
            rate_limit=self.rate_limits[plan],
        )

    def get_shop_plan(self, shop_domain: str) -> str:
        """Get the Shopify plan for a shop"""
        return self.rate_limit_buckets.get(shop_domain, {}).get(
            "plan", self.default_plan
        )

    def get_rate_limit_for_shop(self, shop_domain: str) -> int:
        """Get the rate limit (points per second) for a shop based on its plan"""
        plan = self.get_shop_plan(shop_domain)
        return self.rate_limits[plan]

    def _calculate_retry_delay(
        self, attempt: int, response_headers: Optional[Dict[str, str]] = None
    ) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        # If we have a Retry-After header, use that as the base delay
        if response_headers and self.retry_after_header in response_headers:
            base_delay = float(response_headers[self.retry_after_header])
        else:
            # Use exponential backoff: base_delay * (backoff_multiplier ^ attempt)
            base_delay = self.base_retry_delay * (self.backoff_multiplier**attempt)

        # Cap the delay at max_retry_delay
        delay = min(base_delay, self.max_retry_delay)

        # Add jitter to prevent thundering herd (random variation of ±jitter_range%)
        jitter = random.uniform(-self.jitter_range, self.jitter_range)
        jittered_delay = delay * (1 + jitter)

        # Ensure delay is at least 0.1 seconds
        return max(0.1, jittered_delay)

    def _extract_query_cost(self, headers: Dict[str, str]) -> int:
        """Extract query cost from Shopify response headers"""
        # Shopify GraphQL API returns query cost in X-GraphQL-Cost-Include-Fields header
        # or similar headers. For now, we'll use a default cost of 1 point per query
        # In a production system, you'd want to parse the actual cost from headers

        # Check for common Shopify rate limit headers
        cost_headers = [
            "X-GraphQL-Cost-Include-Fields",
            "X-GraphQL-Query-Cost",
            "X-Shopify-Shop-Api-Call-Limit",
        ]

        for header in cost_headers:
            if header in headers:
                try:
                    # Parse the cost value (format may vary)
                    cost_value = headers[header]
                    if "/" in cost_value:
                        # Format like "1/100" - extract the first number
                        return int(cost_value.split("/")[0])
                    else:
                        return int(cost_value)
                except (ValueError, IndexError):
                    continue

        # Default cost if no cost header is found
        return 1

    @async_timing(threshold_ms=5000)
    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against Shopify API with robust rate limiting and exponential backoff"""
        if not shop_domain:
            raise ValueError("shop_domain is required")

        last_exception = None

        for attempt in range(self.max_retry_attempts):
            try:
                # Check rate limits before each attempt
                await self.wait_for_rate_limit(shop_domain)

                endpoint = self._get_graphql_endpoint(shop_domain)
                headers = self._get_headers(shop_domain)

                payload = {"query": query, "variables": variables or {}}

                response = await self.http_client.post(
                    endpoint, headers=headers, json=payload
                )

                # Handle rate limiting with exponential backoff
                if response.status_code == 429:
                    retry_after = self._calculate_retry_delay(attempt, response.headers)
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}/{self.max_retry_attempts}), waiting {retry_after:.2f} seconds",
                        shop_domain=shop_domain,
                        attempt=attempt + 1,
                        retry_after=retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue  # Retry the request

                # Handle other HTTP errors
                if response.status_code != 200:
                    logger.error(
                        f"HTTP error: {response.status_code}",
                        shop_domain=shop_domain,
                        response_text=response.text,
                        attempt=attempt + 1,
                    )
                    raise Exception(f"HTTP error: {response.status_code}")

                # Parse response
                data = response.json()

                # Check for GraphQL errors
                if "errors" in data:
                    errors = data["errors"]
                    logger.error(
                        f"GraphQL errors: {errors}",
                        shop_domain=shop_domain,
                        query=query[:100],
                        attempt=attempt + 1,
                    )
                    raise Exception(f"GraphQL errors: {errors}")

                # Extract query cost from response headers (if available)
                query_cost = self._extract_query_cost(response.headers)

                # Update rate limit tracking on successful request
                self._update_rate_limit_tracking(
                    shop_domain, response.headers, query_cost
                )

                # Log successful request
                logger.debug(
                    f"Query executed successfully",
                    shop_domain=shop_domain,
                    attempt=attempt + 1,
                    query_cost=query_cost,
                )

                return data.get("data", {})

            except Exception as e:
                last_exception = e

                # If this is the last attempt, don't retry
                if attempt == self.max_retry_attempts - 1:
                    logger.error(
                        f"Query execution failed after {self.max_retry_attempts} attempts",
                        shop_domain=shop_domain,
                        error=str(e),
                        query=query[:100],
                    )
                    raise e

                # Calculate delay for next attempt (exponential backoff)
                delay = self._calculate_retry_delay(attempt)
                logger.warning(
                    f"Query execution failed (attempt {attempt + 1}/{self.max_retry_attempts}), retrying in {delay:.2f} seconds",
                    shop_domain=shop_domain,
                    error=str(e),
                    attempt=attempt + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise Exception("Query execution failed for unknown reason")

    async def execute_mutation(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL mutation against Shopify API"""
        # Mutations use the same execution logic as queries
        return await self.execute_query(mutation, variables, shop_domain)

    async def get_shop_info(self, shop_domain: str) -> Dict[str, Any]:
        """Get basic shop information"""
        query = """
        query {
            shop {
                id
                name
                email
                myshopify_domain: myshopifyDomain
                plan {
                    display_name: displayName
                }
                currency_code: currencyCode
                iana_timezone: ianaTimezone
                created_at: createdAt
                updated_at: updatedAt
            }
        }
        """

        result = await self.execute_query(query, shop_domain=shop_domain)
        return result.get("shop", {})

    async def get_products(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get products from shop - supports both pagination and specific IDs"""
        # Handle specific product IDs (for webhooks)
        if product_ids:
            return await self._get_products_by_ids(shop_domain, product_ids)

        # Regular pagination logic
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }  # Increased from 50 to 250

        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
            products(first: $first, after: $after, query: $query) {
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
                        title
                        description
                        handle
                        created_at: createdAt
                        updated_at: updatedAt
                        published_at: publishedAt
                        status
                        tags
                        product_type: productType
                        vendor
                        total_inventory: totalInventory
                        online_store_url: onlineStoreUrl
                        online_store_preview_url: onlineStorePreviewUrl
                        seo {
                            title
                            description
                        }
                        template_suffix: templateSuffix
                        images(first: 5) {
                            edges {
                                node {
                                    id
                                    url
                                    alt_text: altText
                                    width
                                    height
                                }
                            }
                            page_info: pageInfo {
                                has_next_page: hasNextPage
                                has_previous_page: hasPreviousPage
                                start_cursor: startCursor
                                end_cursor: endCursor
                            }
                        }
                        media(first: 10) {
                            edges {
                                node {
                                    ... on MediaImage {
                                        id
                                        image {
                                            url
                                            alt_text: altText
                                            width
                                            height
                                        }
                                    }
                                    ... on Video {
                                        id
                                        sources {
                                            url
                                            mime_type: mimeType
                                        }
                                    }
                                    ... on Model3d {
                                        id
                                        sources {
                                            url
                                            mime_type: mimeType
                                        }
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
                        options(first: 5) {
                            id
                            name
                            position
                            values
                        }
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    compare_at_price: compareAtPrice
                                    inventory_quantity: inventoryQuantity
                                    sku
                                    barcode
                                    taxable
                                    inventory_policy: inventoryPolicy
                                    position
                                    created_at: createdAt
                                    updated_at: updatedAt
                                    selected_options: selectedOptions {
                                        name
                                        value
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
        products_data = result.get("products", {})

        # Process each product to fetch all variants, images, and metafields if needed
        if products_data.get("edges"):
            processed_products = []

            for product_edge in products_data["edges"]:
                product = product_edge["node"]

                # Check and fetch additional variants if needed
                variants = product.get("variants", {})
                variants_page_info = variants.get("page_info", {})
                if variants_page_info.get("has_next_page"):
                    all_variants = variants.get("edges", []).copy()
                    variants_cursor = variants_page_info.get("end_cursor")

                    while variants_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        variants_batch = await self._fetch_product_variants(
                            shop_domain, product["id"], variants_cursor
                        )
                        if not variants_batch:
                            break

                        new_variants = variants_batch.get("edges", [])
                        all_variants.extend(new_variants)

                        page_info = variants_batch.get("page_info", {})
                        variants_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    product["variants"] = {
                        "edges": all_variants,
                        "page_info": {"has_next_page": False},
                    }

                # Check and fetch additional images if needed
                images = product.get("images", {})
                images_page_info = images.get("page_info", {})
                if images_page_info.get("has_next_page"):
                    all_images = images.get("edges", []).copy()
                    images_cursor = images_page_info.get("end_cursor")

                    while images_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        images_batch = await self._fetch_product_images(
                            shop_domain, product["id"], images_cursor
                        )
                        if not images_batch:
                            break

                        new_images = images_batch.get("edges", [])
                        all_images.extend(new_images)

                        page_info = images_batch.get("page_info", {})
                        images_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    product["images"] = {
                        "edges": all_images,
                        "page_info": {"has_next_page": False},
                    }

                # Check and fetch additional metafields if needed
                metafields = product.get("metafields", {})
                metafields_page_info = metafields.get("page_info", {})
                if metafields_page_info.get("has_next_page"):
                    all_metafields = metafields.get("edges", []).copy()
                    metafields_cursor = metafields_page_info.get("end_cursor")

                    while metafields_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        metafields_batch = await self._fetch_product_metafields(
                            shop_domain, product["id"], metafields_cursor
                        )
                        if not metafields_batch:
                            break

                        new_metafields = metafields_batch.get("edges", [])
                        all_metafields.extend(new_metafields)

                        page_info = metafields_batch.get("page_info", {})
                        metafields_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    product["metafields"] = {
                        "edges": all_metafields,
                        "page_info": {"has_next_page": False},
                    }

                processed_products.append(product_edge)

            # Update the products data with processed products
            products_data["edges"] = processed_products

        return products_data

    async def get_orders(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get orders from shop"""
        # Build query string for filtering
        query_parts = []
        if query:
            query_parts.append(query)
        if created_at_min:
            query_parts.append(f"created_at:>={created_at_min.isoformat()}")
        if created_at_max:
            query_parts.append(f"created_at:<={created_at_max.isoformat()}")
        if status:
            query_parts.append(f"status:{status}")

        query_string = " AND ".join(query_parts) if query_parts else None

        variables = {
            "first": limit or 250,  # Increased from 50 to 250
            "after": cursor,
            "query": query_string,
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

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
                        cancel_reason: cancelReason
                        total_price_set: totalPriceSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        subtotal_price_set: subtotalPriceSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        total_tax_set: totalTaxSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        total_shipping_price_set: totalShippingPriceSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        total_refunded_set: totalRefundedSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        total_outstanding_set: totalOutstandingSet {
                            shop_money: shopMoney {
                                amount
                                currency_code: currencyCode
                            }
                        }
                        customer {
                            id
                            first_name: firstName
                            last_name: lastName
                            display_name: displayName
                            tags
                            created_at: createdAt
                            updated_at: updatedAt
                            state
                            verified_email: verifiedEmail
                            default_address: defaultAddress {
                                id
                                city
                                province
                                country
                                province_code: provinceCode
                                country_code_v2: countryCodeV2
                            }
                        }
                        line_items: lineItems(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    quantity
                                    original_unit_price_set: originalUnitPriceSet {
                                        shop_money: shopMoney {
                                            amount
                                            currency_code: currencyCode
                                        }
                                    }
                                    discounted_unit_price_set: discountedUnitPriceSet {
                                        shop_money: shopMoney {
                                            amount
                                            currency_code: currencyCode
                                        }
                                    }
                                    variant {
                                        id
                                        title
                                        price
                                        sku
                                        barcode
                                        taxable
                                        inventory_policy: inventoryPolicy
                                        position
                                        created_at: createdAt
                                        updated_at: updatedAt
                                        product {
                                            id
                                            title
                                            product_type: productType
                                            vendor
                                            tags
                                        }
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
                        fulfillments {
                            id
                            status
                            created_at: createdAt
                            updated_at: updatedAt
                            display_status: displayStatus
                        }
                        transactions {
                            id
                            kind
                            status
                            amount
                            gateway
                            created_at: createdAt
                            processed_at: processedAt
                        }
                        shipping_address: shippingAddress {
                            city
                            province
                            country
                            province_code: provinceCode
                            country_code_v2: countryCodeV2
                        }
                        billing_address: billingAddress {
                            city
                            province
                            country
                            province_code: provinceCode
                            country_code_v2: countryCodeV2
                        }
                        tags
                        note
                        confirmed
                        test
                        customer_locale: customerLocale
                        currency_code: currencyCode
                        presentment_currency_code: presentmentCurrencyCode
                        discount_applications: discountApplications(first: 5) {
                            edges {
                                node {
                                    value {
                                        ... on MoneyV2 {
                                            amount
                                            currency_code: currencyCode
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
                        custom_attributes: customAttributes {
                            key
                            value
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

                # Check if order has more line items to fetch
                line_items = order.get("line_items", {})
                line_items_page_info = line_items.get("page_info", {})

                if line_items_page_info.get("has_next_page"):
                    # Fetch all remaining line items for this order
                    all_line_items = line_items.get("edges", []).copy()
                    line_items_cursor = line_items_page_info.get("end_cursor")

                    while line_items_cursor:
                        # Check rate limit before each request
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        # Fetch next batch of line items
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

                    # Replace the line items in the order
                    order["line_items"] = {
                        "edges": all_line_items,
                        "page_info": {"has_next_page": False},
                    }

                processed_orders.append(order_edge)

            # Update the orders data with processed orders
            orders_data["edges"] = processed_orders

        return orders_data

    async def get_customers(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get customers from shop"""
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }  # Increased from 50 to 250

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

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
                        total_spent: amountSpent {
                            amount
                            currency_code: currencyCode
                        }
                        orders_count: numberOfOrders
                        last_order: lastOrder {
                            id
                            created_at: createdAt
                        }
                        verified_email: verifiedEmail
                        tax_exempt: taxExempt
                        customer_locale: locale
                        default_address: defaultAddress {
                            city
                            province
                            country
                        }
                        tags
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        return result.get("customers", {})

    async def get_collections(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get collections from shop with complete product data"""
        variables = {
            "first": limit or 250,  # Increased from 50 to 250
            "after": cursor,
            "query": query,
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
            collections(first: $first, after: $after, query: $query) {
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
                        title
                        handle
                        description
                        description_html: descriptionHtml
                        updated_at: updatedAt
                        template_suffix: templateSuffix
                        seo {
                            title
                            description
                        }
                        image {
                            id
                            url
                            altText
                            width
                            height
                        }
                        products(first: 250) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                    product_type: productType
                                    vendor
                                    tags
                                    price_range: priceRangeV2 {
                                        min_variant_price: minVariantPrice {
                                            amount
                                            currency_code: currencyCode
                                        }
                                        max_variant_price: maxVariantPrice {
                                            amount
                                            currency_code: currencyCode
                                        }
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
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        collections_data = result.get("collections", {})

        # Process each collection to fetch all products if needed
        if collections_data.get("edges"):
            processed_collections = []

            for collection_edge in collections_data["edges"]:
                collection = collection_edge["node"]

                # Check if collection has more products to fetch
                products = collection.get("products", {})
                products_page_info = products.get("page_info", {})

                if products_page_info.get("has_next_page"):
                    # Fetch all remaining products for this collection
                    all_products = products.get("edges", []).copy()
                    products_cursor = products_page_info.get("end_cursor")

                    while products_cursor:
                        # Check rate limit before each request
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

                        # Fetch next batch of products
                        products_batch = await self._fetch_collection_products(
                            shop_domain, collection["id"], products_cursor
                        )

                        if not products_batch:
                            break

                        new_products = products_batch.get("edges", [])
                        all_products.extend(new_products)

                        page_info = products_batch.get("page_info", {})
                        products_cursor = (
                            page_info.get("end_cursor")
                            if page_info.get("has_next_page")
                            else None
                        )

                    # Replace the products in the collection
                    collection["products"] = {
                        "edges": all_products,
                        "page_info": {"has_next_page": False},
                    }

                processed_collections.append(collection_edge)

            # Update the collections data with processed collections
            collections_data["edges"] = processed_collections

        return collections_data

    async def _fetch_collection_products(
        self, shop_domain: str, collection_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of products for a specific collection"""

        products_query = """
        query($collectionId: ID!, $first: Int!, $after: String) {
            collection(id: $collectionId) {
                products(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            title
                            handle
                            product_type: productType
                            vendor
                            tags
                            price_range: priceRangeV2 {
                                min_variant_price: minVariantPrice {
                                    amount
                                    currency_code: currencyCode
                                }
                                max_variant_price: maxVariantPrice {
                                    amount
                                    currency_code: currencyCode
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
            "collectionId": collection_id,
            "first": 250,  # Max batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(products_query, variables, shop_domain)
        collection_data = result.get("collection", {})
        return collection_data.get("products", {})

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
                            original_unit_price_set: originalUnitPriceSet {
                                shop_money: shopMoney {
                                    amount
                                    currency_code: currencyCode
                                }
                            }
                            discounted_unit_price_set: discountedUnitPriceSet {
                                shop_money: shopMoney {
                                    amount
                                    currency_code: currencyCode
                                }
                            }
                            variant {
                                id
                                title
                                price
                                sku
                                barcode
                                taxable
                                inventory_policy: inventoryPolicy
                                position
                                created_at: createdAt
                                updated_at: updatedAt
                                product {
                                    id
                                    title
                                    product_type: productType
                                    vendor
                                    tags
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
            "orderId": order_id,
            "first": 10,  # Keep small to manage GraphQL cost
            "after": cursor,
        }

        result = await self.execute_query(line_items_query, variables, shop_domain)
        order_data = result.get("order", {})
        return order_data.get("line_items", {})

    async def _get_products_by_ids(
        self, shop_domain: str, product_ids: List[str]
    ) -> Dict[str, Any]:
        """Get specific products by IDs - reuses existing logic for variants, images, metafields"""
        processed_products = []

        for product_id in product_ids:
            try:
                # Get single product with full data (variants, images, metafields)
                product_data = await self._get_single_product_full_data(
                    shop_domain, product_id
                )
                if product_data:
                    processed_products.append(product_data)
            except Exception as e:
                logger.error(f"Failed to fetch product {product_id}: {e}")

        # Return in the same format as the original query
        return {
            "edges": [{"node": product} for product in processed_products],
            "page_info": {"has_next_page": False},
        }

    async def _get_single_product_full_data(
        self, shop_domain: str, product_id: str
    ) -> Dict[str, Any]:
        """Get a single product with all variants, images, and metafields - reuses existing logic"""
        # Use the same GraphQL query as the original get_products method
        graphql_query = """
        query($id: ID!) {
            product(id: $id) {
                id
                title
                description
                handle
                createdAt
                updatedAt
                publishedAt
                status
                tags
                productType
                vendor
                totalInventory
                onlineStoreUrl
                onlineStorePreviewUrl
                seo {
                    title
                    description
                }
                templateSuffix
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
                    pageInfo {
                        hasNextPage
                        hasPreviousPage
                        startCursor
                        endCursor
                    }
                }
                media(first: 10) {
                    edges {
                        node {
                            ... on MediaImage {
                                id
                                image {
                                    url
                                    altText
                                    width
                                    height
                                }
                            }
                            ... on Video {
                                id
                                sources {
                                    url
                                    mimeType
                                }
                            }
                            ... on Model3d {
                                id
                                sources {
                                    url
                                    mimeType
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
                options(first: 5) {
                    id
                    name
                    position
                    values
                }
                variants(first: 10) {
                    edges {
                        node {
                            id
                            title
                            price
                            compareAtPrice
                            inventoryQuantity
                            sku
                            barcode
                            taxable
                            inventoryPolicy
                            position
                            createdAt
                            updatedAt
                            selectedOptions {
                                name
                                value
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

        variables = {"id": f"gid://shopify/Product/{product_id}"}
        result = await self.execute_query(graphql_query, variables, shop_domain)
        product = result.get("product", {})

        if not product:
            return None

        # Reuse the same logic for fetching additional variants, images, metafields
        # Check and fetch additional variants if needed
        variants = product.get("variants", {})
        variants_page_info = variants.get("pageInfo", {})
        if variants_page_info.get("hasNextPage"):
            all_variants = variants.get("edges", []).copy()
            variants_cursor = variants_page_info.get("endCursor")

            while variants_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

                variants_batch = await self._fetch_product_variants(
                    shop_domain, product["id"], variants_cursor
                )
                if not variants_batch:
                    break

                new_variants = variants_batch.get("edges", [])
                all_variants.extend(new_variants)

                page_info = variants_batch.get("page_info", {})
                variants_cursor = (
                    page_info.get("end_cursor")
                    if page_info.get("has_next_page")
                    else None
                )

            product["variants"] = {
                "edges": all_variants,
                "page_info": {"has_next_page": False},
            }

        # Check and fetch additional images if needed
        images = product.get("images", {})
        images_page_info = images.get("pageInfo", {})
        if images_page_info.get("hasNextPage"):
            all_images = images.get("edges", []).copy()
            images_cursor = images_page_info.get("endCursor")

            while images_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

                images_batch = await self._fetch_product_images(
                    shop_domain, product["id"], images_cursor
                )
                if not images_batch:
                    break

                new_images = images_batch.get("edges", [])
                all_images.extend(new_images)

                page_info = images_batch.get("page_info", {})
                images_cursor = (
                    page_info.get("end_cursor")
                    if page_info.get("has_next_page")
                    else None
                )

            product["images"] = {
                "edges": all_images,
                "page_info": {"has_next_page": False},
            }

        # Check and fetch additional metafields if needed
        metafields = product.get("metafields", {})
        metafields_page_info = metafields.get("pageInfo", {})
        if metafields_page_info.get("hasNextPage"):
            all_metafields = metafields.get("edges", []).copy()
            metafields_cursor = metafields_page_info.get("endCursor")

            while metafields_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

                metafields_batch = await self._fetch_product_metafields(
                    shop_domain, product["id"], metafields_cursor
                )
                if not metafields_batch:
                    break

                new_metafields = metafields_batch.get("edges", [])
                all_metafields.extend(new_metafields)

                page_info = metafields_batch.get("page_info", {})
                metafields_cursor = (
                    page_info.get("end_cursor")
                    if page_info.get("has_next_page")
                    else None
                )

            product["metafields"] = {
                "edges": all_metafields,
                "page_info": {"has_next_page": False},
            }

        return product

    async def _fetch_product_variants(
        self, shop_domain: str, product_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of variants for a specific product"""

        variants_query = """
        query($productId: ID!, $first: Int!, $after: String) {
            product(id: $productId) {
                variants(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            title
                            price
                            compare_at_price: compareAtPrice
                            inventory_quantity: inventoryQuantity
                            sku
                            barcode
                            taxable
                            inventory_policy: inventoryPolicy
                            position
                            created_at: createdAt
                            updated_at: updatedAt
                            selected_options: selectedOptions {
                                name
                                value
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
            "productId": product_id,
            "first": 10,  # Keep small to manage GraphQL cost
            "after": cursor,
        }

        result = await self.execute_query(variants_query, variables, shop_domain)
        product_data = result.get("product", {})
        return product_data.get("variants", {})

    async def _fetch_product_images(
        self, shop_domain: str, product_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of images for a specific product"""

        images_query = """
        query($productId: ID!, $first: Int!, $after: String) {
            product(id: $productId) {
                images(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            url
                            alt_text: altText
                            width
                            height
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
            "productId": product_id,
            "first": 5,  # Keep small to manage GraphQL cost
            "after": cursor,
        }

        result = await self.execute_query(images_query, variables, shop_domain)
        product_data = result.get("product", {})
        return product_data.get("images", {})

    async def _fetch_product_metafields(
        self, shop_domain: str, product_id: str, cursor: str
    ) -> Dict[str, Any]:
        """Fetch a batch of metafields for a specific product"""

        metafields_query = """
        query($productId: ID!, $first: Int!, $after: String) {
            product(id: $productId) {
                metafields(first: $first, after: $after) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
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
            "productId": product_id,
            "first": 10,  # Keep small to manage GraphQL cost
            "after": cursor,
        }

        result = await self.execute_query(metafields_query, variables, shop_domain)
        product_data = result.get("product", {})
        return product_data.get("metafields", {})

    async def check_rate_limit(self, shop_domain: str) -> Dict[str, Any]:
        """Check current rate limit status based on GraphQL cost"""
        bucket = self.rate_limit_buckets.get(shop_domain, {})
        cost_tracking = self.query_cost_tracking.get(shop_domain, {})

        current_time = time.time()
        points_this_second = cost_tracking.get("points_this_second", 0)
        last_request_time = cost_tracking.get("last_request_time", 0)
        max_points_per_second = self.get_rate_limit_for_shop(shop_domain)

        # Reset counter if a second has passed
        if current_time - last_request_time >= 1.0:
            points_this_second = 0

        return {
            "points_this_second": points_this_second,
            "max_points_per_second": max_points_per_second,
            "can_make_request": points_this_second < max_points_per_second,
            "time_until_reset": max(0, 1.0 - (current_time - last_request_time)),
            "plan": self.get_shop_plan(shop_domain),
        }

    async def wait_for_rate_limit(self, shop_domain: str) -> None:
        """Wait for rate limit to reset if needed"""
        rate_limit_info = await self.check_rate_limit(shop_domain)

        if not rate_limit_info["can_make_request"]:
            wait_time = rate_limit_info["time_until_reset"]
            await asyncio.sleep(wait_time)

    def _update_rate_limit_tracking(
        self, shop_domain: str, headers: Dict[str, str], query_cost: int = 1
    ):
        """Update rate limit tracking from response headers and query cost"""
        current_time = time.time()

        # Initialize tracking structures
        if shop_domain not in self.rate_limit_buckets:
            self.rate_limit_buckets[shop_domain] = {}
        if shop_domain not in self.query_cost_tracking:
            self.query_cost_tracking[shop_domain] = {}

        bucket = self.rate_limit_buckets[shop_domain]
        cost_tracking = self.query_cost_tracking[shop_domain]

        # Update cost tracking (GraphQL uses calculated query cost)
        if current_time - cost_tracking.get("last_request_time", 0) >= 1.0:
            cost_tracking["points_this_second"] = query_cost
        else:
            cost_tracking["points_this_second"] = (
                cost_tracking.get("points_this_second", 0) + query_cost
            )

        cost_tracking["last_request_time"] = current_time

        # Update legacy request count for backward compatibility
        if current_time - bucket.get("last_request_time", 0) >= 1.0:
            bucket["requests_this_second"] = 1
        else:
            bucket["requests_this_second"] = bucket.get("requests_this_second", 0) + 1

        bucket["last_request_time"] = current_time

        # Log rate limit status
        max_points = self.get_rate_limit_for_shop(shop_domain)
        current_points = cost_tracking["points_this_second"]
        plan = self.get_shop_plan(shop_domain)

        logger.debug(
            f"Rate limit tracking updated",
            shop_domain=shop_domain,
            plan=plan,
            current_points=current_points,
            max_points=max_points,
            query_cost=query_cost,
            utilization_percent=(current_points / max_points) * 100,
        )

    async def validate_access_token(self, shop_domain: str) -> bool:
        """Validate access token for shop"""
        try:
            # Try to get shop info as a validation test
            await self.get_shop_info(shop_domain)
            return True
        except Exception as e:
            logger.warning(
                f"Access token validation failed", shop_domain=shop_domain, error=str(e)
            )
            return False

    async def refresh_access_token(self, shop_domain: str) -> bool:
        """Refresh access token for shop"""
        # This would need to be implemented based on your OAuth flow
        # For now, we'll just return False as it's not implemented
        logger.warning("Access token refresh not implemented", shop_domain=shop_domain)
        return False

    async def get_app_installation_scopes(self, shop_domain: str) -> List[str]:
        """Get the actual scopes granted to the app from Shopify GraphQL API"""
        query = """
        query {
          current_app_installation: currentAppInstallation {
            id
            access_scopes: accessScopes {
              handle
              description
            }
          }
        }
        """

        try:
            result = await self.execute_query(query, shop_domain=shop_domain)

            if "current_app_installation" in result:
                installation = result["current_app_installation"]
                scopes = installation.get("access_scopes", [])

                # Extract scope handles
                scope_handles = [scope["handle"] for scope in scopes]
                return scope_handles
            else:
                return []

        except Exception as e:
            logger.error(
                f"Failed to get app installation scopes for {shop_domain}: {e}"
            )
            return []

    async def get_api_limits(self, shop_domain: str) -> Dict[str, Any]:
        """Get API usage limits and quotas"""
        # This would need to be implemented based on Shopify's API limits
        # For now, we'll return basic information
        return {
            "max_requests_per_second": self.max_requests_per_second,
            "current_usage": self.rate_limit_buckets.get(shop_domain, {}),
            "api_version": self.api_version,
            "endpoint": self.endpoint.format(version=self.api_version),
        }
