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


def page_info_of(connection: Dict[str, Any]) -> tuple:
    """Read a GraphQL connection's pageInfo regardless of alias spelling.

    The queries alias pageInfo/hasNextPage/endCursor into snake_case, but
    several readers were written against the camelCase names. A reader that
    guesses the wrong spelling does not fail — it sees no pageInfo, defaults
    hasNextPage to False and silently truncates the collection at one page.
    That is how a 997-product catalog became 251 rows. Every reader goes
    through here so the two spellings can never drift apart again.

    Returns (has_next_page, end_cursor).
    """
    info = connection.get("page_info") or connection.get("pageInfo") or {}
    has_next = info.get("has_next_page", info.get("hasNextPage", False))
    cursor = info.get("end_cursor", info.get("endCursor"))
    return bool(has_next), cursor


class ShopifyThrottledError(Exception):
    """Shopify rejected the query for cost reasons and it should be retried."""


class BaseShopifyAPIClient:
    """Base Shopify API client with common functionality"""

    def __init__(self):
        self.base_url = "https://{shop}.myshopify.com"
        self.api_version = "2026-07"  # newest version Shopify still supports
        self.endpoint = "/admin/api/{version}/graphql.json"

        # Rate limiting based on Shopify's official limits.
        #
        # Shopify bills GraphQL in *cost points*, not requests. A products page
        # with variants, images, media and metafields costs far more than one
        # point, so counting requests against a 100 limit believes it has
        # roughly 100x the headroom it really has and walks straight into a
        # throttle. Every response carries extensions.cost.throttleStatus with
        # the real bucket state; that is what these track.
        self.rate_limit_buckets: Dict[str, Dict[str, Any]] = {}
        self.retry_after_header = "Retry-After"

        # Bucket capacity (points) by plan — only used until the first response
        # tells us the true values for this shop.
        self.rate_limits = {
            "standard": 100,  # Standard Shopify
            "advanced": 200,  # Advanced Shopify
            "plus": 1000,  # Shopify Plus
            "enterprise": 2000,  # Shopify for enterprise (Commerce Components)
        }

        # Default to standard plan if not specified
        self.default_plan = "standard"

        # Keep this much of the bucket in reserve. Shopify rejects a query
        # whose cost exceeds what is currently available, and it only knows the
        # actual cost after running it, so going in with a nearly empty bucket
        # is how a page fails rather than waits.
        self.min_available_points = 250.0

        # Enhanced rate limiting with exponential backoff
        self.max_retry_attempts = 5
        self.base_retry_delay = 1.0  # Base delay in seconds
        self.max_retry_delay = 300.0  # Maximum delay (5 minutes)
        self.backoff_multiplier = 2.0
        self.jitter_range = 0.1  # Add 10% jitter to prevent thundering herd

        # Query cost tracking (GraphQL uses calculated query cost)
        self.query_cost_tracking: Dict[str, Dict[str, Any]] = {}

        # HTTP client. A 250-product page with variants, images, media and
        # metafields regularly takes well over 30s to come back; the old
        # 30s read timeout turned those into a failed page mid-pagination.
        self.http_client: Optional[httpx.AsyncClient] = None
        self.timeout = httpx.Timeout(90.0, connect=10.0)

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
        """Execute a GraphQL query, waiting out and retrying cost throttles.

        Throttling is retried here rather than raised, because the callers
        paginate: an exception escaping mid-pagination loses every page after
        it, and a throttle is the one failure guaranteed to happen on a large
        catalog.
        """
        await self.connect()

        endpoint = self._get_graphql_endpoint(shop_domain)
        payload = {"query": query, "variables": variables}
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retry_attempts):
            # Wait until the cost bucket has enough points for this query.
            await self._await_cost_budget(shop_domain)

            try:
                response = await self.http_client.post(
                    endpoint, json=payload, headers=self._get_headers(shop_domain)
                )
                response.raise_for_status()
                data = response.json()

                # The cost extension rides along with successful *and*
                # throttled responses, so record it before anything else.
                self._record_throttle_status(shop_domain, data)

                if "errors" in data:
                    errors = data["errors"]
                    if self._is_throttled(errors):
                        last_error = ShopifyThrottledError(
                            f"Throttled by Shopify for {shop_domain}"
                        )
                        await self._sleep_backoff(attempt, shop_domain)
                        continue
                    messages = [
                        e.get("message", "Unknown error") for e in errors
                    ]
                    raise Exception(f"GraphQL errors: {', '.join(messages)}")

                return data.get("data", {})

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = e
                    retry_after = float(
                        e.response.headers.get(self.retry_after_header, 0) or 0
                    )
                    if retry_after > 0:
                        await asyncio.sleep(min(retry_after, self.max_retry_delay))
                    else:
                        await self._sleep_backoff(attempt, shop_domain)
                    continue
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
            except (httpx.TimeoutException, httpx.TransportError) as e:
                # Transient network trouble. Same reasoning as throttles: a
                # raise here truncates the rest of the catalog.
                last_error = e
                logger.warning(
                    f"Transport error on attempt {attempt + 1}/"
                    f"{self.max_retry_attempts} for {shop_domain}: {e}"
                )
                await self._sleep_backoff(attempt, shop_domain)
                continue
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise

        raise ShopifyThrottledError(
            f"Query failed after {self.max_retry_attempts} attempts for "
            f"{shop_domain}: {last_error}"
        )

    @staticmethod
    def _is_throttled(errors: List[Dict[str, Any]]) -> bool:
        """Shopify reports cost throttling as a GraphQL error with HTTP 200."""
        for error in errors:
            code = (error.get("extensions") or {}).get("code", "")
            if str(code).upper() == "THROTTLED":
                return True
            if "throttled" in str(error.get("message", "")).lower():
                return True
        return False

    async def _sleep_backoff(self, attempt: int, shop_domain: str) -> None:
        """Exponential backoff with jitter, capped at max_retry_delay."""
        delay = min(
            self.base_retry_delay * (self.backoff_multiplier**attempt),
            self.max_retry_delay,
        )
        delay += delay * random.uniform(-self.jitter_range, self.jitter_range)
        logger.warning(f"Backing off {delay:.1f}s before retrying {shop_domain}")
        await asyncio.sleep(max(delay, 0.0))

    def _record_throttle_status(
        self, shop_domain: str, body: Dict[str, Any]
    ) -> None:
        """Store the real cost bucket state reported by Shopify."""
        throttle = (
            ((body.get("extensions") or {}).get("cost") or {}).get("throttleStatus")
            or {}
        )
        if not throttle:
            return

        self.rate_limit_buckets[shop_domain] = {
            "available": float(throttle.get("currentlyAvailable", 0.0)),
            "maximum": float(
                throttle.get("maximumAvailable", self.rate_limits[self.default_plan])
            ),
            "restore_rate": float(throttle.get("restoreRate", 50.0)) or 50.0,
            "observed_at": time.monotonic(),
        }

    def _available_points(self, shop_domain: str) -> Optional[float]:
        """Points available now, extrapolating restore since the last response."""
        bucket = self.rate_limit_buckets.get(shop_domain)
        if not bucket:
            return None
        elapsed = time.monotonic() - bucket["observed_at"]
        restored = bucket["available"] + elapsed * bucket["restore_rate"]
        return min(restored, bucket["maximum"])

    async def _await_cost_budget(self, shop_domain: str) -> None:
        """Sleep until the cost bucket can plausibly afford another query."""
        available = self._available_points(shop_domain)
        if available is None:
            return  # No response seen yet; let the first one tell us.

        bucket = self.rate_limit_buckets[shop_domain]
        target = min(self.min_available_points, bucket["maximum"])
        if available >= target:
            return

        wait = (target - available) / bucket["restore_rate"]
        wait = min(wait, self.max_retry_delay)
        if wait > 0:
            logger.debug(
                f"Cost budget low for {shop_domain} "
                f"({available:.0f}/{bucket['maximum']:.0f}), waiting {wait:.1f}s"
            )
            await asyncio.sleep(wait)

    async def check_rate_limit(self, shop_domain: str) -> Dict[str, Any]:
        """Report the shop's cost budget.

        Kept for the callers that gate on it; `execute_query` enforces the
        budget itself, so this is advisory.
        """
        available = self._available_points(shop_domain)
        if available is None:
            return {"can_make_request": True, "available": None, "limit": None}

        bucket = self.rate_limit_buckets[shop_domain]
        return {
            "can_make_request": available
            >= min(self.min_available_points, bucket["maximum"]),
            "available": available,
            "limit": bucket["maximum"],
            "restore_rate": bucket["restore_rate"],
        }

    async def wait_for_rate_limit(self, shop_domain: str):
        """Wait until the cost bucket has recovered enough points."""
        await self._await_cost_budget(shop_domain)

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

        result = await self.execute_query(query, {}, shop_domain)
        return result.get("shop", {})

    async def get_catalog_counts(self, shop_domain: str) -> Dict[str, int]:
        """How many products/collections the shop actually has.

        This is the denominator for sync progress. Without it the UI can only
        compare what we ingested against what we ingested, which is 100% by
        construction and stays 100% while three quarters of the catalog is
        missing.
        """
        query = """
        query {
            productsCount { count }
            collectionsCount { count }
        }
        """
        try:
            result = await self.execute_query(query, {}, shop_domain)
            return {
                "products": (result.get("productsCount") or {}).get("count", 0),
                "collections": (result.get("collectionsCount") or {}).get("count", 0),
            }
        except Exception as e:
            logger.warning(f"Could not read catalog counts for {shop_domain}: {e}")
            return {}
