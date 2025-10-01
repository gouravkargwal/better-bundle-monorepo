"""
Base Shopify API client with common functionality
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
from app.core.config.settings import settings

logger = get_logger(__name__)


class BaseShopifyAPIClient:
    """Base Shopify API client with common functionality"""

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
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_tokens.get(shop_domain, ""),
        }
        return headers

    async def set_access_token(self, shop_domain: str, access_token: str):
        """Set access token for a shop"""
        self.access_tokens[shop_domain] = access_token

    async def get_app_installation_scopes(self, shop_domain: str) -> List[str]:
        """Get the actual scopes granted to the app from Shopify GraphQL API"""
        query = """
        query {
          currentAppInstallation {
            id
            app {
              id
              title
              handle
            }
            accessScopes {
              handle
              description
            }
          }
        }
        """

        try:
            result = await self.execute_query(query, {}, shop_domain)

            # Check for GraphQL errors first
            if "errors" in result:
                logger.error(f"GraphQL errors for {shop_domain}: {result['errors']}")
                return []

            # Check if currentAppInstallation exists and is not null
            if (
                "currentAppInstallation" in result
                and result["currentAppInstallation"] is not None
            ):
                installation = result["currentAppInstallation"]

                # Verify this is our app
                app_info = installation.get("app", {})
                app_title = app_info.get("title", "Unknown")
                app_handle = app_info.get("handle", "unknown")
                app_id = app_info.get("id", "unknown")

                # Verify this is our app using configured app ID
                expected_app_id = settings.shopify.SHOPIFY_APP_ID
                expected_app_title = settings.shopify.SHOPIFY_APP_TITLE

                if expected_app_id and app_id != expected_app_id:
                    logger.error(
                        f"❌ Wrong app detected! Expected app ID '{expected_app_id}', got '{app_id}'"
                    )
                    logger.error(
                        f"❌ This installation belongs to a different app: {app_title}"
                    )
                    return []

                if expected_app_title and app_title != expected_app_title:
                    logger.error(
                        f"❌ Wrong app detected! Expected '{expected_app_title}', got '{app_title}'"
                    )
                    logger.error(
                        f"❌ This installation belongs to a different app: {app_id}"
                    )
                    return []

                scopes = installation.get("accessScopes", [])

                if scopes:
                    # Extract scope handles
                    scope_handles = [scope["handle"] for scope in scopes]
                    return scope_handles
                else:
                    logger.warning(
                        f"No accessScopes found in installation for {shop_domain}"
                    )
                    return []
            else:
                logger.warning(
                    f"currentAppInstallation is null or missing for {shop_domain}: {result}"
                )
                return []

        except Exception as e:
            logger.error(
                f"Failed to get app installation scopes for {shop_domain}: {e}"
            )
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            return []

    async def execute_query(
        self, query: str, variables: Dict[str, Any], shop_domain: str
    ) -> Dict[str, Any]:
        """Execute GraphQL query with rate limiting and error handling"""
        await self.connect()

        # Check rate limits
        rate_limit_info = await self.check_rate_limit(shop_domain)
        if not rate_limit_info["can_make_request"]:
            await self.wait_for_rate_limit(shop_domain)

        endpoint = self._get_graphql_endpoint(shop_domain)
        headers = self._get_headers(shop_domain)

        payload = {"query": query, "variables": variables}

        try:
            response = await self.http_client.post(
                endpoint, json=payload, headers=headers
            )
            response.raise_for_status()

            data = response.json()

            # Handle GraphQL errors
            if "errors" in data:
                error_messages = [
                    error.get("message", "Unknown error") for error in data["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            # Update rate limit tracking
            await self._update_rate_limit_tracking(shop_domain, response.headers)

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited
                retry_after = int(e.response.headers.get("Retry-After", 1))
                await asyncio.sleep(retry_after)
                return await self.execute_query(query, variables, shop_domain)
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    async def check_rate_limit(self, shop_domain: str) -> Dict[str, Any]:
        """Check if we can make a request based on rate limits"""
        bucket_key = f"{shop_domain}_standard"  # Simplified for now

        if bucket_key not in self.rate_limit_buckets:
            self.rate_limit_buckets[bucket_key] = {
                "requests_made": 0,
                "window_start": time.time(),
                "limit": self.rate_limits["standard"],
            }

        bucket = self.rate_limit_buckets[bucket_key]
        current_time = time.time()

        # Reset window if needed (1 second windows)
        if current_time - bucket["window_start"] >= 1.0:
            bucket["requests_made"] = 0
            bucket["window_start"] = current_time

        can_make_request = bucket["requests_made"] < bucket["limit"]

        return {
            "can_make_request": can_make_request,
            "requests_made": bucket["requests_made"],
            "limit": bucket["limit"],
            "reset_time": bucket["window_start"] + 1.0,
        }

    async def wait_for_rate_limit(self, shop_domain: str):
        """Wait for rate limit to reset"""
        bucket_key = f"{shop_domain}_standard"
        bucket = self.rate_limit_buckets.get(bucket_key, {})

        if bucket:
            reset_time = bucket["window_start"] + 1.0
            current_time = time.time()
            wait_time = max(0, reset_time - current_time)

            if wait_time > 0:
                await asyncio.sleep(wait_time)

    async def _update_rate_limit_tracking(
        self, shop_domain: str, headers: Dict[str, str]
    ):
        """Update rate limit tracking from response headers"""
        bucket_key = f"{shop_domain}_standard"

        if bucket_key not in self.rate_limit_buckets:
            self.rate_limit_buckets[bucket_key] = {
                "requests_made": 0,
                "window_start": time.time(),
                "limit": self.rate_limits["standard"],
            }

        bucket = self.rate_limit_buckets[bucket_key]
        bucket["requests_made"] += 1

    async def get_shop_info(self, shop_domain: str) -> Dict[str, Any]:
        """Get shop information"""
        query = """
        query {
            shop {
                id
                name
                domain
                myshopifyDomain
                planName
                planDisplayName
                currencyCode
                timezone
                ianaTimezone
                weightUnit
                createdAt
                updatedAt
            }
        }
        """

        result = await self.execute_query(query, shop_domain=shop_domain)
        return result.get("shop", {})
