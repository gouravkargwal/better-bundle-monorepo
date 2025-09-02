"""
Shopify API client for data collection using GraphQL
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
from app.core.logging import get_logger, log_error, log_shopify_api

logger = get_logger(__name__)


class ShopifyAPIClient:
    """Async Shopify API client using GraphQL"""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.base_url = f"https://{shop_domain}/admin/api/2024-01"
        self.graphql_url = f"{self.base_url}/graphql.json"

        # Configure HTTP client with rate limiting
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers={
                "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRIES),
        wait=wait_exponential(multiplier=settings.RETRY_DELAY, max=60),
    )
    async def execute_graphql_query(
        self, query: str, variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query with retry logic and timeout protection"""

        start_time = asyncio.get_event_loop().time()

        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables

            # Add timeout protection to the HTTP request
            async with asyncio.timeout(45):  # 45 second timeout for GraphQL queries
                response = await self.client.post(self.graphql_url, json=payload)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            log_shopify_api(
                endpoint="graphql",
                method="POST",
                status_code=response.status_code,
                duration_ms=duration_ms,
                shop_domain=self.shop_domain,
            )

            response.raise_for_status()

            result = response.json()

            # Check for GraphQL errors
            if "errors" in result:
                error_msg = f"GraphQL errors: {json.dumps(result['errors'])}"
                log_error(
                    Exception(error_msg),
                    {
                        "shop_domain": self.shop_domain,
                        "query": query[:200] + "..." if len(query) > 200 else query,
                        "variables": variables,
                    },
                )
                raise Exception(error_msg)

            return result

        except asyncio.TimeoutError:
            log_error(
                Exception("GraphQL query timeout"),
                {
                    "shop_domain": self.shop_domain,
                    "query": query[:200] + "..." if len(query) > 200 else query,
                    "variables": variables,
                },
            )
            raise Exception("GraphQL query timed out after 45 seconds")
        except httpx.HTTPStatusError as e:
            log_error(
                e,
                {
                    "shop_domain": self.shop_domain,
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:500],
                },
            )

            # Handle specific Shopify API errors
            if e.response.status_code == 403:
                raise Exception(
                    "Shopify API access denied. Please ensure the app has the required permissions and the access token is valid."
                )
            elif e.response.status_code == 401:
                raise Exception(
                    "Shopify API authentication failed. The access token may be expired or invalid."
                )

            raise

        except Exception as e:
            log_error(e, {"shop_domain": self.shop_domain})
            raise

    async def fetch_orders(
        self, since_date: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch orders from Shopify GraphQL API with timeout protection"""

        query = """
        query getOrders($query: String, $after: String, $first: Int) {
            orders(query: $query, after: $after, first: $first) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        totalPriceSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        createdAt
                        displayFinancialStatus
                        # fulfillmentStatus - removed as it doesn't exist in current API version
                        currencyCode
                        customer {
                            id
                        }
                        lineItems(first: 50) {
                            edges {
                                node {
                                    product {
                                        id
                                    }
                                    variant {
                                        id
                                        price
                                        compareAtPrice
                                        selectedOptions {
                                            name
                                            value
                                        }
                                    }
                                    title
                                    quantity
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        all_orders = []
        has_next_page = True
        cursor = None
        total_fetched = 0
        max_iterations = 100  # Prevent infinite loops
        iteration_count = 0

        # Add overall timeout for entire pagination process
        overall_start_time = asyncio.get_event_loop().time()
        overall_timeout = 180  # 3 minutes total timeout for all orders

        while (
            has_next_page
            and (not limit or total_fetched < limit)
            and iteration_count < max_iterations
        ):
            # Check overall timeout
            if (asyncio.get_event_loop().time() - overall_start_time) > overall_timeout:
                logger.error(
                    "Orders fetch overall timeout reached",
                    shop_domain=self.shop_domain,
                    total_orders=len(all_orders),
                    iteration_count=iteration_count,
                    overall_timeout_seconds=overall_timeout,
                )
                break

            iteration_count += 1

            remaining_limit = limit - total_fetched if limit else None
            batch_size = min(
                remaining_limit or settings.SHOPIFY_API_BATCH_SIZE,
                settings.SHOPIFY_API_BATCH_SIZE,
            )

            variables = {"first": batch_size, "after": cursor}

            if since_date:
                variables["query"] = f"created_at:>='{since_date}'"

            try:
                # Add timeout protection for each batch
                async with asyncio.timeout(30):  # 30 second timeout per batch
                    result = await self.execute_graphql_query(query, variables)
            except asyncio.TimeoutError:
                logger.error(
                    "Order batch fetch timed out",
                    shop_domain=self.shop_domain,
                    batch_size=batch_size,
                    cursor=cursor,
                    iteration_count=iteration_count,
                )
                break

            orders_data = result.get("data", {}).get("orders", {})
            edges = orders_data.get("edges", [])

            # Process orders
            for edge in edges:
                node = edge["node"]
                # Transform to match the expected format
                order = {
                    "orderId": node["id"],
                    "totalAmount": {"shopMoney": node["totalPriceSet"]["shopMoney"]},
                    "orderDate": node["createdAt"],
                    "displayFinancialStatus": node.get("displayFinancialStatus"),
                    # "fulfillmentStatus": node.get("fulfillmentStatus"), # Removed - field doesn't exist
                    "currencyCode": node.get("currencyCode"),
                    "customerId": node.get("customer"),
                    "lineItems": {"edges": node["lineItems"]["edges"]},
                }
                all_orders.append(order)

            total_fetched += len(edges)

            # Update pagination
            page_info = orders_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            logger.info(
                "Orders pagination progress",
                orders_collected=len(all_orders),
                total_fetched=total_fetched,
                limit=limit,
                has_next_page=has_next_page,
                iteration_count=iteration_count,
            )

            # Rate limiting with timeout protection
            try:
                async with asyncio.timeout(5):  # 5 second timeout for rate limiting
                    await asyncio.sleep(1.0 / settings.SHOPIFY_API_RATE_LIMIT)
            except asyncio.TimeoutError:
                logger.warning("Rate limiting sleep interrupted, continuing...")

        if iteration_count >= max_iterations:
            logger.warning(
                "Maximum iterations reached for orders fetch",
                shop_domain=self.shop_domain,
                total_orders=len(all_orders),
                max_iterations=max_iterations,
            )

        return all_orders

    async def fetch_products(
        self, since_date: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch products from Shopify GraphQL API with timeout protection"""

        query = """
        query getProducts($query: String, $after: String, $first: Int) {
            products(query: $query, after: $after, first: $first) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        title
                        handle
                        productType
                        description
                        vendor
                        createdAt
                        tags
                        images(first: 1) {
                            edges {
                                node {
                                    url
                                    altText
                                }
                            }
                        }
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    price
                                    compareAtPrice
                                    inventoryQuantity
                                    selectedOptions {
                                        name
                                        value
                                    }
                                }
                            }
                        }
                        metafields(first: 10) {
                            edges {
                                node {
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
        }
        """

        all_products = []
        has_next_page = True
        cursor = None
        total_fetched = 0
        max_iterations = 100  # Prevent infinite loops
        iteration_count = 0

        while (
            has_next_page
            and (not limit or total_fetched < limit)
            and iteration_count < max_iterations
        ):
            iteration_count += 1

            remaining_limit = limit - total_fetched if limit else None
            batch_size = min(
                remaining_limit or settings.SHOPIFY_API_BATCH_SIZE,
                settings.SHOPIFY_API_BATCH_SIZE,
            )

            variables = {"first": batch_size, "after": cursor}

            if since_date:
                variables["query"] = f"updated_at:>='{since_date}'"

            try:
                # Add timeout protection for each batch
                async with asyncio.timeout(30):  # 30 second timeout per batch
                    result = await self.execute_graphql_query(query, variables)
            except asyncio.TimeoutError:
                logger.error(
                    "Product batch fetch timed out",
                    shop_domain=self.shop_domain,
                    batch_size=batch_size,
                    cursor=cursor,
                    iteration_count=iteration_count,
                )
                break

            products_data = result.get("data", {}).get("products", {})
            edges = products_data.get("edges", [])

            # Process products
            for edge in edges:
                node = edge["node"]
                # Transform to match the expected format
                product = {
                    "id": node["id"],
                    "title": node.get("title"),
                    "handle": node.get("handle"),
                    "productType": node.get("productType"),
                    "description": node.get("description"),
                    "vendor": node.get("vendor"),
                    "createdAt": node["createdAt"],
                    "tags": node.get("tags", []),
                    "images": [
                        e["node"] for e in node.get("images", {}).get("edges", [])
                    ],
                    "variants": [
                        e["node"] for e in node.get("variants", {}).get("edges", [])
                    ],
                    "metafields": [
                        e["node"] for e in node.get("metafields", {}).get("edges", [])
                    ],
                }
                all_products.append(product)

            total_fetched += len(edges)

            # Update pagination
            page_info = products_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            logger.info(
                "Products pagination progress",
                products_collected=len(all_products),
                total_fetched=total_fetched,
                limit=limit,
                has_next_page=has_next_page,
                iteration_count=iteration_count,
            )

            # Rate limiting with timeout protection
            try:
                async with asyncio.timeout(5):  # 5 second timeout for rate limiting
                    await asyncio.sleep(1.0 / settings.SHOPIFY_API_RATE_LIMIT)
            except asyncio.TimeoutError:
                logger.warning("Rate limiting sleep interrupted, continuing...")

        if iteration_count >= max_iterations:
            logger.warning(
                "Maximum iterations reached for products fetch",
                shop_domain=self.shop_domain,
                total_products=len(all_products),
                max_iterations=max_iterations,
            )

        return all_products

    async def fetch_customers(
        self, since_date: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch customers from Shopify GraphQL API"""

        query = """
        query getCustomers($query: String, $after: String, $first: Int) {
            customers(query: $query, after: $after, first: $first) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        email
                        firstName
                        lastName
                        createdAt
                        lastOrder {
                            id
                            processedAt
                        }
                        tags
                        addresses {
                            country
                            province
                            city
                            zip
                            address1
                            address2
                            latitude
                            longitude
                        }
                        metafields(first: 10) {
                            edges {
                                node {
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
        }
        """

        all_customers = []
        has_next_page = True
        cursor = None
        total_fetched = 0
        max_iterations = 100  # Prevent infinite loops
        iteration_count = 0

        # Add overall timeout for entire pagination process
        overall_start_time = asyncio.get_event_loop().time()
        overall_timeout = 180  # 3 minutes total timeout for all customers

        while (
            has_next_page
            and (not limit or total_fetched < limit)
            and iteration_count < max_iterations
        ):
            # Check overall timeout
            if (asyncio.get_event_loop().time() - overall_start_time) > overall_timeout:
                logger.error(
                    "Customers fetch overall timeout reached",
                    shop_domain=self.shop_domain,
                    total_customers=len(all_customers),
                    iteration_count=iteration_count,
                    overall_timeout_seconds=overall_timeout,
                )
                break

            iteration_count += 1

            remaining_limit = limit - total_fetched if limit else None
            batch_size = min(
                remaining_limit or settings.SHOPIFY_API_BATCH_SIZE,
                settings.SHOPIFY_API_BATCH_SIZE,
            )

            variables = {"first": batch_size, "after": cursor}

            if since_date:
                variables["query"] = f"created_at:>='{since_date}'"

            try:
                # Add timeout protection for each batch
                async with asyncio.timeout(30):  # 30 second timeout per batch
                    result = await self.execute_graphql_query(query, variables)

                customers_data = result.get("data", {}).get("customers", {})
                edges = customers_data.get("edges", [])

            except Exception as e:
                # Check if it's an access denied error
                if "ACCESS_DENIED" in str(
                    e
                ) or "not approved to access the Customer object" in str(e):
                    logger.warning(
                        "Customer data access denied by Shopify. Continuing without customer data.",
                        shop_domain=self.shop_domain,
                        error=str(e),
                    )
                    # Return empty list - we'll continue without customer data
                    return []
                else:
                    # Re-raise other errors
                    raise

            # Process customers
            for edge in edges:
                node = edge["node"]
                # Transform to match the expected format
                customer = {
                    "id": node["id"],
                    "email": node.get("email"),
                    "firstName": node.get("firstName"),
                    "lastName": node.get("lastName"),
                    "createdAt": node["createdAt"],
                    "lastOrder": node.get("lastOrder"),
                    "tags": node.get("tags", []),
                    "addresses": node.get("addresses", []),
                    "metafields": [
                        e["node"] for e in node.get("metafields", {}).get("edges", [])
                    ],
                }
                all_customers.append(customer)

            total_fetched += len(edges)

            # Update pagination
            page_info = customers_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            logger.info(
                "Customers pagination progress",
                customers_collected=len(all_customers),
                total_fetched=total_fetched,
                limit=limit,
                has_next_page=has_next_page,
                iteration_count=iteration_count,
            )

            # Rate limiting with timeout protection
            try:
                async with asyncio.timeout(5):  # 5 second timeout for rate limiting
                    await asyncio.sleep(1.0 / settings.SHOPIFY_API_RATE_LIMIT)
            except asyncio.TimeoutError:
                logger.warning("Rate limiting sleep interrupted, continuing...")

        if iteration_count >= max_iterations:
            logger.warning(
                "Maximum iterations reached for customers fetch",
                shop_domain=self.shop_domain,
                total_customers=len(all_customers),
                max_iterations=max_iterations,
            )

        return all_customers


def calculate_since_date(days_back: int = settings.MAX_INITIAL_DAYS) -> str:
    """Calculate date for data collection using ISO format"""
    date = datetime.now() - timedelta(days=days_back)
    return date.isoformat()
