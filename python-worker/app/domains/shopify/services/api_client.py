"""
Shopify API client implementation for BetterBundle Python Worker
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import ConfigurationError
from app.shared.decorators import retry, async_timing
from app.shared.helpers import now_utc

from ..interfaces.api_client import IShopifyAPIClient

logger = get_logger(__name__)


class ShopifyAPIClient(IShopifyAPIClient):
    """Shopify GraphQL API client with rate limiting and error handling"""

    def __init__(self):
        self.base_url = "https://{shop}.myshopify.com"
        self.api_version = "2024-01"  # Latest stable version
        self.endpoint = "/admin/api/{version}/graphql.json"

        # Rate limiting
        self.rate_limit_buckets: Dict[str, Dict[str, Any]] = {}
        self.max_requests_per_second = 2  # Shopify's default limit
        self.retry_after_header = "Retry-After"

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
        logger.info("Attempting to connect Shopify API client")
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "BetterBundle-PythonWorker/1.0",
                },
            )
            logger.info("Shopify API client initialized successfully")
        else:
            logger.info("Shopify API client already connected")

    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            logger.info("Shopify API client closed")

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
        logger.info(f"Access token set for shop: {shop_domain}")

    @retry(max_attempts=3, delay=1.0, backoff=2.0)
    @async_timing(threshold_ms=5000)
    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against Shopify API"""
        if not shop_domain:
            raise ValueError("shop_domain is required")

        # Check rate limits
        await self.wait_for_rate_limit(shop_domain)

        endpoint = self._get_graphql_endpoint(shop_domain)
        headers = self._get_headers(shop_domain)

        payload = {"query": query, "variables": variables or {}}

        try:
            response = await self.http_client.post(
                endpoint, headers=headers, json=payload
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get(self.retry_after_header, 60))
                logger.warning(
                    f"Rate limited, waiting {retry_after} seconds",
                    shop_domain=shop_domain,
                )
                await asyncio.sleep(retry_after)
                return await self.execute_query(query, variables, shop_domain)

            # Handle other errors
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                errors = data["errors"]
                logger.error(
                    f"GraphQL errors: {errors}",
                    shop_domain=shop_domain,
                    query=query[:100],
                )
                raise Exception(f"GraphQL errors: {errors}")

            # Update rate limit tracking
            self._update_rate_limit_tracking(shop_domain, response.headers)

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error: {e.response.status_code}",
                shop_domain=shop_domain,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                f"Query execution failed",
                shop_domain=shop_domain,
                error=str(e),
                query=query[:100],
            )
            raise

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
                myshopifyDomain
                plan {
                    displayName
                }
                currencyCode
                ianaTimezone
                createdAt
                updatedAt
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
    ) -> Dict[str, Any]:
        """Get products from shop"""
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }  # Increased from 50 to 250

        graphql_query = """
        query($first: Int!, $after: String, $query: String) {
            products(first: $first, after: $after, query: $query) {
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
                    node {
                        id
                        title
                        bodyHtml
                        vendor
                        productType
                        handle
                        status
                        publishedAt
                        tags
                        createdAt
                        updatedAt
                        images(first: 10) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                }
                            }
                        }
                        variants(first: 100) {
                            edges {
                                node {
                                    id
                                    title
                                    sku
                                    barcode
                                    price
                                    compareAtPrice
                                    inventoryQuantity
                                    inventoryPolicy
                                    taxable
                                    createdAt
                                    updatedAt
                                }
                            }
                        }
                        collections(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        return result.get("products", {})

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
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
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
                        totalDiscountsSet {
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
                            phone
                            createdAt
                            updatedAt
                        }
                        lineItems(first: 100) {
                            edges {
                                node {
                                    id
                                    quantity
                                    title
                                    variant {
                                        id
                                        title
                                        price
                                        sku
                                        product {
                                            id
                                            title
                                            vendor
                                            productType
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
        return result.get("orders", {})

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
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
                    node {
                        id
                        firstName
                        lastName
                        email
                        phone
                        createdAt
                        updatedAt
                        defaultAddress {
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
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
        """Get collections from shop"""
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
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
                    node {
                        id
                        title
                        handle
                        description
                        descriptionHtml
                        updatedAt
                        publishedAt
                        sortOrder
                        templateSuffix
                        productsCount
                        image {
                            id
                            url
                            altText
                        }
                        products(first: 10) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        return result.get("collections", {})

    async def get_customer_events(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        event_type: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get customer events from shop"""
        variables = {
            "first": limit or 250,  # Increased from 50 to 250
            "after": cursor,
            "eventType": event_type,
            "createdAtMin": created_at_min.isoformat() if created_at_min else None,
            "createdAtMax": created_at_max.isoformat() if created_at_max else None,
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        graphql_query = """
        query($first: Int!, $after: String, $eventType: MarketingEventType, $createdAtMin: DateTime, $createdAtMax: DateTime) {
            marketingEvents(first: $first, after: $after, eventType: $eventType, createdAtMin: $createdAtMin, createdAtMax: $createdAtMax) {
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
                edges {
                    cursor
                    node {
                        id
                        eventType
                        marketingChannel
                        paid
                        startedAt
                        endedAt
                        description
                        manageUrl
                        previewUrl
                        utmCampaign
                        utmSource
                        utmMedium
                        utmTerm
                        utmContent
                        budget
                        budgetType
                        currency
                        customerId
                        productId
                        collectionId
                    }
                }
            }
        }
        """

        result = await self.execute_query(graphql_query, variables, shop_domain)
        return result.get("marketingEvents", {})

    async def check_rate_limit(self, shop_domain: str) -> Dict[str, Any]:
        """Check current rate limit status"""
        bucket = self.rate_limit_buckets.get(shop_domain, {})

        current_time = time.time()
        requests_this_second = bucket.get("requests_this_second", 0)
        last_request_time = bucket.get("last_request_time", 0)

        # Reset counter if a second has passed
        if current_time - last_request_time >= 1.0:
            requests_this_second = 0

        return {
            "requests_this_second": requests_this_second,
            "max_requests_per_second": self.max_requests_per_second,
            "can_make_request": requests_this_second < self.max_requests_per_second,
            "time_until_reset": max(0, 1.0 - (current_time - last_request_time)),
        }

    async def wait_for_rate_limit(self, shop_domain: str) -> None:
        """Wait for rate limit to reset if needed"""
        rate_limit_info = await self.check_rate_limit(shop_domain)

        if not rate_limit_info["can_make_request"]:
            wait_time = rate_limit_info["time_until_reset"]
            logger.debug(
                f"Rate limit reached, waiting {wait_time:.2f}s", shop_domain=shop_domain
            )
            await asyncio.sleep(wait_time)

    def _update_rate_limit_tracking(self, shop_domain: str, headers: Dict[str, str]):
        """Update rate limit tracking from response headers"""
        current_time = time.time()

        if shop_domain not in self.rate_limit_buckets:
            self.rate_limit_buckets[shop_domain] = {}

        bucket = self.rate_limit_buckets[shop_domain]

        # Update request count
        if current_time - bucket.get("last_request_time", 0) >= 1.0:
            bucket["requests_this_second"] = 1
        else:
            bucket["requests_this_second"] = bucket.get("requests_this_second", 0) + 1

        bucket["last_request_time"] = current_time

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
          currentAppInstallation {
            id
            accessScopes {
              handle
              description
            }
          }
        }
        """

        try:
            result = await self.execute_query(query, shop_domain=shop_domain)

            if "currentAppInstallation" in result:
                installation = result["currentAppInstallation"]
                scopes = installation.get("accessScopes", [])

                # Extract scope handles
                scope_handles = [scope["handle"] for scope in scopes]
                logger.info(
                    f"Retrieved {len(scope_handles)} scopes for {shop_domain}: {scope_handles}"
                )

                return scope_handles
            else:
                logger.warning(f"No app installation data found for {shop_domain}")
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
