#!/usr/bin/env python3
"""
Shopify Product Deletion Script - Products Without Images

This script deletes products that do not have any images from a Shopify store.
Use with caution as this action is irreversible.

Requirements:
- Valid Shopify access token with write permissions
- Python 3.8+
- Required packages: httpx, asyncio

Usage:
    1. Set environment variables:
       export SHOP_DOMAIN=your-store.myshopify.com
       export SHOPIFY_ACCESS_TOKEN=shpat_...
    2. Run: python delete_products_without_images.py
    3. Type 'DELETE ALL' when prompted to confirm deletion
"""

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import sys
from typing import Dict, Any, List

import httpx
import requests

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

# Use app logger if available, otherwise fall back to standard logging without
# dragging in the full app config/database stack
try:
    from app.core.logging import get_logger  # noqa: E402
    logger = get_logger(__name__)
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

# Load environment variables from .env.local or .env if dotenv is installed
try:
    from dotenv import load_dotenv

    _pw_path = Path(python_worker_dir)
    for _env_file in [
        _pw_path / ".env.local",
        _pw_path / ".env",
        _pw_path.parent / ".env.local",
        _pw_path.parent / ".env",
    ]:
        if _env_file.exists():
            load_dotenv(_env_file, override=False)
except Exception:
    pass


class ProductImageDeleter:
    """Handles deletion of products without images from Shopify"""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2025-10"  # Use latest API version

        self.base_url = (
            f"https://{shop_domain}/admin/api/{self.api_version}/graphql.json"
        )

        logger.info(f"Using API URL: {self.base_url}")

        # Rate limiting
        self.rate_limit_buckets = {}
        self.max_requests_per_second = 10  # Increased for parallel processing
        self.request_delay = 0.1  # 100ms between requests (reduced for speed)

        # Statistics
        self.stats = {
            "products_found": 0,
            "products_without_images": 0,
            "products_deleted": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    async def __aenter__(self):
        """Async context manager entry"""
        import ssl

        # Create a custom SSL context with modern TLS settings
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # Set minimum TLS version to 1.2 and maximum to 1.3
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
        # Use more compatible cipher suites
        ssl_context.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        )

        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.access_token,
                "User-Agent": "BetterBundle-ProductImageDeleter/1.0",
            },
            # Use custom SSL context
            verify=ssl_context,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if hasattr(self, "http_client"):
            await self.http_client.aclose()

    async def execute_mutation(
        self, mutation: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute GraphQL mutation with rate limiting"""
        # Rate limiting
        await asyncio.sleep(self.request_delay)

        payload = {"query": mutation, "variables": variables}

        # Retry logic for SSL and network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.http_client.post(self.base_url, json=payload)
                response.raise_for_status()

                data = response.json()

                if "errors" in data:
                    error_messages = [
                        error.get("message", "Unknown error")
                        for error in data["errors"]
                    ]
                    raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

                return data.get("data", {})

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"Network error on attempt {attempt + 1}: {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Fallback to requests library
                    logger.warning(
                        "httpx failed, trying requests library as fallback..."
                    )
                    return await self._execute_mutation_with_requests(
                        mutation, variables
                    )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(e.response.headers.get("Retry-After", 5))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    return await self.execute_mutation(mutation, variables)
                else:
                    logger.error(
                        f"HTTP error {e.response.status_code}: {e.response.text}"
                    )
                    raise
            except Exception as e:
                logger.error(f"Mutation execution failed: {e}")
                raise

    async def _execute_mutation_with_requests(
        self, mutation: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback method using requests library with custom SSL configuration"""
        import ssl
        import urllib3

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
            "User-Agent": "BetterBundle-ProductImageDeleter/1.0",
        }

        payload = {"query": mutation, "variables": variables}

        try:
            # Create a custom SSL context with more permissive settings
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")  # Lower security level

            # Use requests with custom SSL context
            session = requests.Session()
            session.verify = False

            response = session.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=30,
                verify=False,
            )
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                error_messages = [
                    error.get("message", "Unknown error") for error in data["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            return data.get("data", {})

        except Exception as e:
            logger.error(f"Requests fallback also failed: {e}")
            # Try one more approach with even more relaxed SSL settings
            try:
                logger.warning("Trying with completely disabled SSL...")
                return await self._execute_mutation_with_curl(mutation, variables)
            except Exception as curl_e:
                logger.error(f"All SSL approaches failed: {curl_e}")
                raise

    async def _execute_mutation_with_curl(
        self, mutation: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Final fallback using curl command with SSL disabled"""
        import subprocess
        import json

        payload = {"query": mutation, "variables": variables}

        # Build curl command
        curl_cmd = [
            "curl",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-H",
            f"X-Shopify-Access-Token: {self.access_token}",
            "-H",
            "User-Agent: BetterBundle-ProductImageDeleter/1.0",
            "--data",
            json.dumps(payload),
            "--insecure",  # Disable SSL verification
            "--connect-timeout",
            "30",
            "--max-time",
            "60",
            self.base_url,
        ]

        try:
            result = subprocess.run(
                curl_cmd, capture_output=True, text=True, timeout=60
            )

            if result.returncode != 0:
                raise Exception(
                    f"Curl failed with return code {result.returncode}: {result.stderr}"
                )

            data = json.loads(result.stdout)

            if "errors" in data:
                error_messages = [
                    error.get("message", "Unknown error") for error in data["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            return data.get("data", {})

        except Exception as e:
            logger.error(f"Curl fallback also failed: {e}")
            raise

    async def get_all_products_without_images(self) -> List[Dict[str, Any]]:
        """Get all products that don't have any images"""
        logger.info("Fetching all products...")
        products_without_images = []
        cursor = None

        while True:
            query = """
            query($first: Int!, $after: String) {
                products(first: $first, after: $after) {
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
                            vendor
                            images(first: 1) {
                                edges {
                                    node {
                                        id
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            variables = {"first": 250, "after": cursor}

            result = await self.execute_mutation(query, variables)
            products_data = result.get("products", {})

            edges = products_data.get("edges", [])
            for edge in edges:
                node = edge["node"]
                self.stats["products_found"] += 1
                
                # Check if product has any images
                images = node.get("images", {})
                image_edges = images.get("edges", [])
                
                if not image_edges:
                    products_without_images.append({
                        "id": node["id"],
                        "title": node.get("title", "Unknown"),
                        "handle": node.get("handle", ""),
                        "product_type": node.get("productType", ""),
                        "vendor": node.get("vendor", ""),
                    })
                    self.stats["products_without_images"] += 1

            page_info = products_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {self.stats['products_found']} total products")
        logger.info(f"Found {len(products_without_images)} products without images")
        return products_without_images

    def print_dry_run_report(self, products: List[Dict[str, Any]]) -> None:
        """Print a formatted report of products that would be deleted in dry-run mode"""
        print("\n" + "=" * 80)
        print("🔍 DRY RUN REPORT - Products Without Images")
        print("=" * 80)
        print(f"Store: {self.shop_domain}")
        print(f"Total products scanned: {self.stats['products_found']}")
        print(f"Products without images: {len(products)}")
        print("=" * 80)

        if not products:
            print("\nNo products without images found. Nothing to delete.")
            print("=" * 80)
            return

        print(f"\n{'#':<5} {'Title':<40} {'Type':<20} {'Vendor':<15}")
        print("-" * 80)

        for idx, product in enumerate(products, 1):
            title = product["title"][:37] + "..." if len(product["title"]) > 40 else product["title"]
            ptype = product["product_type"][:17] + "..." if len(product["product_type"]) > 20 else product["product_type"]
            vendor = product["vendor"][:12] + "..." if len(product["vendor"]) > 15 else product["vendor"]
            print(f"{idx:<5} {title:<40} {ptype:<20} {vendor:<15}")

        print("-" * 80)
        print(f"\nTotal: {len(products)} product(s) would be deleted")
        print("=" * 80)
        print("\nRun without --dry-run to actually delete these products.")
        print("=" * 80)

    async def delete_product(self, product_id: str) -> bool:
        """Delete a single product"""
        mutation = """
        mutation($input: ProductDeleteInput!) {
            productDelete(input: $input) {
                deletedProductId
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {"input": {"id": product_id}}

        try:
            result = await self.execute_mutation(mutation, variables)
            product_delete = result.get("productDelete", {})

            if product_delete.get("userErrors"):
                errors = [error["message"] for error in product_delete["userErrors"]]
                logger.error(
                    f"Failed to delete product {product_id}: {', '.join(errors)}"
                )
                return False

            if product_delete.get("deletedProductId"):
                self.stats["products_deleted"] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting product {product_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def delete_all_products_without_images(self) -> None:
        """Delete all products that don't have any images"""
        logger.info("🗑️ Starting deletion of products without images...")
        self.stats["start_time"] = datetime.now()

        products = await self.get_all_products_without_images()

        if not products:
            logger.info("No products without images found to delete")
            self.stats["end_time"] = datetime.now()
            self.print_summary()
            return

        logger.warning(
            f"⚠️  About to delete {len(products)} products without images. This action is irreversible!"
        )

        # Process products in parallel batches
        batch_size = 10  # Process 10 products at a time
        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]
            logger.info(
                f"Processing products batch {i//batch_size + 1}/{(len(products) + batch_size - 1)//batch_size}"
            )

            # Create tasks for parallel execution
            tasks = []
            for product in batch:
                product_id = product["id"]
                product_title = product.get("title", "Unknown")
                task = self._delete_product_with_logging(product_id, product_title)
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for j, result in enumerate(results):
                product = batch[j]
                product_title = product.get("title", "Unknown")
                if isinstance(result, Exception):
                    logger.error(
                        f"❌ Failed to delete product: {product_title} - {result}"
                    )
                elif result:
                    logger.info(f"✅ Deleted product: {product_title}")
                else:
                    logger.error(f"❌ Failed to delete product: {product_title}")

        self.stats["end_time"] = datetime.now()
        self.print_summary()

    async def _delete_product_with_logging(
        self, product_id: str, product_title: str
    ) -> bool:
        """Delete a single product with logging"""
        return await self.delete_product(product_id)

    def print_summary(self) -> None:
        """Print deletion summary"""
        duration = None
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]

        logger.info("=" * 60)
        logger.info("📊 DELETION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total products found: {self.stats['products_found']}")
        logger.info(f"Products without images: {self.stats['products_without_images']}")
        logger.info(f"Products deleted: {self.stats['products_deleted']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        if duration:
            logger.info(f"Total duration: {duration}")
        logger.info("=" * 60)


async def main():
    """Main function to run the deletion script"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Shopify Product Deletion Script (deletes products without images)"
    )
    parser.add_argument(
        "--shop",
        default=os.environ.get("SHOP_DOMAIN") or os.environ.get("SHOPIFY_SHOP_DOMAIN"),
        help="Shop domain (or set SHOP_DOMAIN env var)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("ACCESS_TOKEN") or os.environ.get("SHOPIFY_ACCESS_TOKEN"),
        help="Shopify Admin API token (or set ACCESS_TOKEN env var)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the 'DELETE ALL' confirmation prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List products without images without deleting them",
    )
    args = parser.parse_args()

    shop_domain = args.shop
    access_token = args.token

    if not shop_domain or not access_token:
        logger.error(
            "Missing required credentials: provide --shop and --token flags, or set SHOP_DOMAIN and ACCESS_TOKEN env vars"
        )
        return 1

    async with ProductImageDeleter(shop_domain, access_token) as deleter:
        if args.dry_run:
            # Dry-run mode: only list products without images
            products = await deleter.get_all_products_without_images()
            deleter.print_dry_run_report(products)
        else:
            # Actual deletion mode
            if not args.yes:
                print("=" * 60)
                print("⚠️  DANGER: PERMANENT SHOPIFY PRODUCT DELETION")
                print(f"Store: {shop_domain}")
                print("This will delete all products without images on Shopify.")
                print("=" * 60)
                confirm = input("Type 'DELETE ALL' to confirm: ")
                if confirm != "DELETE ALL":
                    print("Aborted.")
                    return 0

            await deleter.delete_all_products_without_images()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
