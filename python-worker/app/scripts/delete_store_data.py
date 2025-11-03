#!/usr/bin/env python3
"""
Shopify Store Data Deletion Script

This script deletes all products, collections, orders, and customers from a Shopify store.
Use with extreme caution as this action is irreversible.

Requirements:
- Valid Shopify access token with write permissions
- Python 3.8+
- Required packages: httpx, asyncio

Usage:
    1. Set environment variables:
       export SHOP_DOMAIN=your-store.myshopify.com
       export SHOPIFY_ACCESS_TOKEN=shpat_...
    2. Run: python delete_store_data.py
    3. Type 'DELETE ALL' when prompted to confirm deletion
"""

import asyncio
import os
import sys
from typing import Dict, Any, List
from datetime import datetime


python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

import httpx
import requests
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShopifyStoreDeleter:
    """Handles deletion of all store data from Shopify"""

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
            "products_deleted": 0,
            "collections_deleted": 0,
            "orders_deleted": 0,
            "customers_deleted": 0,
            "media_deleted": 0,
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
                "User-Agent": "BetterBundle-StoreDeleter/1.0",
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
            "User-Agent": "BetterBundle-StoreDeleter/1.0",
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

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
            "User-Agent": "BetterBundle-StoreDeleter/1.0",
        }

        payload = {"query": mutation, "variables": variables}

        # Build curl command
        curl_cmd = [
            "curl",
            "-X",
            "POST",
            "-H",
            f"Content-Type: application/json",
            "-H",
            f"X-Shopify-Access-Token: {self.access_token}",
            "-H",
            f"User-Agent: BetterBundle-StoreDeleter/1.0",
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

    async def get_all_products(self) -> List[Dict[str, Any]]:
        """Get all products from the store"""
        logger.info("Fetching all products...")
        products = []
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
                products.append(edge["node"])

            page_info = products_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {len(products)} products")
        return products

    async def get_all_collections(self) -> List[Dict[str, Any]]:
        """Get all collections from the store"""
        logger.info("Fetching all collections...")
        collections = []
        cursor = None

        while True:
            query = """
            query($first: Int!, $after: String) {
                collections(first: $first, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            title
                        }
                    }
                }
            }
            """

            variables = {"first": 250, "after": cursor}

            result = await self.execute_mutation(query, variables)
            collections_data = result.get("collections", {})

            edges = collections_data.get("edges", [])
            for edge in edges:
                collections.append(edge["node"])

            page_info = collections_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {len(collections)} collections")
        return collections

    async def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders from the store"""
        logger.info("Fetching all orders...")
        orders = []
        cursor = None

        while True:
            query = """
            query($first: Int!, $after: String) {
                orders(first: $first, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
            """

            variables = {"first": 250, "after": cursor}

            result = await self.execute_mutation(query, variables)
            orders_data = result.get("orders", {})

            edges = orders_data.get("edges", [])
            for edge in edges:
                orders.append(edge["node"])

            page_info = orders_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {len(orders)} orders")
        return orders

    async def get_all_customers(self) -> List[Dict[str, Any]]:
        """Get all customers from the store"""
        logger.info("Fetching all customers...")
        customers = []
        cursor = None

        while True:
            query = """
            query($first: Int!, $after: String) {
                customers(first: $first, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            firstName
                            lastName
                        }
                    }
                }
            }
            """

            variables = {"first": 250, "after": cursor}

            result = await self.execute_mutation(query, variables)
            customers_data = result.get("customers", {})

            edges = customers_data.get("edges", [])
            for edge in edges:
                customers.append(edge["node"])

            page_info = customers_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {len(customers)} customers")
        return customers

    async def get_all_media(self) -> List[Dict[str, Any]]:
        """Get all media files from the store"""
        logger.info("Fetching all media files...")
        media_files = []
        cursor = None

        while True:
            query = """
            query($first: Int!, $after: String) {
                files(first: $first, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            id
                            ... on MediaImage {
                                id
                                image {
                                    url
                                    altText
                                }
                            }
                            ... on Video {
                                id
                                sources {
                                    url
                                }
                            }
                            ... on Model3d {
                                id
                                sources {
                                    url
                                }
                            }
                        }
                    }
                }
            }
            """

            variables = {"first": 250, "after": cursor}

            result = await self.execute_mutation(query, variables)
            files_data = result.get("files", {})

            edges = files_data.get("edges", [])
            for edge in edges:
                media_files.append(edge["node"])

            page_info = files_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        logger.info(f"Found {len(media_files)} media files")
        return media_files

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

    async def delete_collection(self, collection_id: str) -> bool:
        """Delete a single collection"""
        mutation = """
        mutation($input: CollectionDeleteInput!) {
            collectionDelete(input: $input) {
                deletedCollectionId
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {"input": {"id": collection_id}}

        try:
            result = await self.execute_mutation(mutation, variables)
            collection_delete = result.get("collectionDelete", {})

            if collection_delete.get("userErrors"):
                errors = [error["message"] for error in collection_delete["userErrors"]]
                logger.error(
                    f"Failed to delete collection {collection_id}: {', '.join(errors)}"
                )
                return False

            if collection_delete.get("deletedCollectionId"):
                self.stats["collections_deleted"] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting collection {collection_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def delete_order(self, order_id: str) -> bool:
        """Delete a single order"""
        mutation = """
        mutation($orderId: ID!) {
            orderDelete(orderId: $orderId) {
                deletedId
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """

        variables = {"orderId": order_id}

        try:
            result = await self.execute_mutation(mutation, variables)
            order_delete = result.get("orderDelete", {})

            if order_delete.get("userErrors"):
                errors = [error["message"] for error in order_delete["userErrors"]]
                logger.error(f"Failed to delete order {order_id}: {', '.join(errors)}")
                return False

            if order_delete.get("deletedId"):
                self.stats["orders_deleted"] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting order {order_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def delete_customer(self, customer_id: str) -> bool:
        """Delete a single customer"""
        mutation = """
        mutation($input: CustomerDeleteInput!) {
            customerDelete(input: $input) {
                deletedCustomerId
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {"input": {"id": customer_id}}

        try:
            result = await self.execute_mutation(mutation, variables)
            customer_delete = result.get("customerDelete", {})

            if customer_delete.get("userErrors"):
                errors = [error["message"] for error in customer_delete["userErrors"]]
                logger.error(
                    f"Failed to delete customer {customer_id}: {', '.join(errors)}"
                )
                return False

            if customer_delete.get("deletedCustomerId"):
                self.stats["customers_deleted"] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting customer {customer_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def delete_media(self, media_id: str) -> bool:
        """Delete a single media file"""
        mutation = """
        mutation($fileIds: [ID!]!) {
            fileDelete(fileIds: $fileIds) {
                deletedFileIds
                userErrors {
                    field
                    message
                }
            }
        }
        """

        variables = {"fileIds": [media_id]}

        try:
            result = await self.execute_mutation(mutation, variables)
            file_delete = result.get("fileDelete", {})

            if file_delete.get("userErrors"):
                errors = [error["message"] for error in file_delete["userErrors"]]
                logger.error(f"Failed to delete media {media_id}: {', '.join(errors)}")
                return False

            if file_delete.get("deletedFileIds"):
                self.stats["media_deleted"] += 1
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting media {media_id}: {e}")
            self.stats["errors"] += 1
            return False

    async def delete_all_products(self) -> None:
        """Delete all products from the store"""
        logger.info("🗑️ Starting product deletion...")
        products = await self.get_all_products()

        if not products:
            logger.info("No products found to delete")
            return

        logger.warning(
            f"⚠️  About to delete {len(products)} products. This action is irreversible!"
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

    async def _delete_product_with_logging(
        self, product_id: str, product_title: str
    ) -> bool:
        """Delete a single product with logging"""
        return await self.delete_product(product_id)

    async def delete_all_collections(self) -> None:
        """Delete all collections from the store"""
        logger.info("🗑️ Starting collection deletion...")
        collections = await self.get_all_collections()

        if not collections:
            logger.info("No collections found to delete")
            return

        logger.warning(
            f"⚠️  About to delete {len(collections)} collections. This action is irreversible!"
        )

        # Process collections in parallel batches
        batch_size = 10  # Process 10 collections at a time
        for i in range(0, len(collections), batch_size):
            batch = collections[i : i + batch_size]
            logger.info(
                f"Processing collections batch {i//batch_size + 1}/{(len(collections) + batch_size - 1)//batch_size}"
            )

            # Create tasks for parallel execution
            tasks = []
            for collection in batch:
                collection_id = collection["id"]
                collection_title = collection.get("title", "Unknown")
                task = self._delete_collection_with_logging(
                    collection_id, collection_title
                )
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for j, result in enumerate(results):
                collection = batch[j]
                collection_title = collection.get("title", "Unknown")
                if isinstance(result, Exception):
                    logger.error(
                        f"❌ Failed to delete collection: {collection_title} - {result}"
                    )
                elif result:
                    logger.info(f"✅ Deleted collection: {collection_title}")
                else:
                    logger.error(f"❌ Failed to delete collection: {collection_title}")

    async def _delete_collection_with_logging(
        self, collection_id: str, collection_title: str
    ) -> bool:
        """Delete a single collection with logging"""
        return await self.delete_collection(collection_id)

    async def delete_all_orders(self) -> None:
        """Delete all orders from the store"""
        logger.info("🗑️ Starting order deletion...")
        orders = await self.get_all_orders()

        if not orders:
            logger.info("No orders found to delete")
            return

        logger.warning(
            f"⚠️  About to delete {len(orders)} orders. This action is irreversible!"
        )

        # Process orders in parallel batches
        batch_size = 10  # Process 10 orders at a time
        for i in range(0, len(orders), batch_size):
            batch = orders[i : i + batch_size]
            logger.info(
                f"Processing orders batch {i//batch_size + 1}/{(len(orders) + batch_size - 1)//batch_size}"
            )

            # Create tasks for parallel execution
            tasks = []
            for order in batch:
                order_id = order["id"]
                order_name = order.get("name", "Unknown")
                task = self._delete_order_with_logging(order_id, order_name)
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for j, result in enumerate(results):
                order = batch[j]
                order_name = order.get("name", "Unknown")
                if isinstance(result, Exception):
                    logger.error(f"❌ Failed to delete order: {order_name} - {result}")
                elif result:
                    logger.info(f"✅ Deleted order: {order_name}")
                else:
                    logger.error(f"❌ Failed to delete order: {order_name}")

    async def _delete_order_with_logging(self, order_id: str, order_name: str) -> bool:
        """Delete a single order with logging"""
        return await self.delete_order(order_id)

    async def delete_all_customers(self) -> None:
        """Delete all customers from the store"""
        logger.info("🗑️ Starting customer deletion...")
        customers = await self.get_all_customers()

        if not customers:
            logger.info("No customers found to delete")
            return

        logger.warning(
            f"⚠️  About to delete {len(customers)} customers. This action is irreversible!"
        )

        # Process customers in parallel batches
        batch_size = 10  # Process 10 customers at a time
        for i in range(0, len(customers), batch_size):
            batch = customers[i : i + batch_size]
            logger.info(
                f"Processing customers batch {i//batch_size + 1}/{(len(customers) + batch_size - 1)//batch_size}"
            )

            # Create tasks for parallel execution
            tasks = []
            for customer in batch:
                customer_id = customer["id"]
                first_name = customer.get("firstName", "")
                last_name = customer.get("lastName", "")
                customer_name = f"{first_name} {last_name}".strip() or "Unknown"
                task = self._delete_customer_with_logging(customer_id, customer_name)
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for j, result in enumerate(results):
                customer = batch[j]
                first_name = customer.get("firstName", "")
                last_name = customer.get("lastName", "")
                customer_name = f"{first_name} {last_name}".strip() or "Unknown"
                if isinstance(result, Exception):
                    logger.error(
                        f"❌ Failed to delete customer: {customer_name} - {result}"
                    )
                elif result:
                    logger.info(f"✅ Deleted customer: {customer_name}")
                else:
                    logger.error(f"❌ Failed to delete customer: {customer_name}")

    async def _delete_customer_with_logging(
        self, customer_id: str, customer_name: str
    ) -> bool:
        """Delete a single customer with logging"""
        return await self.delete_customer(customer_id)

    async def delete_all_media(self) -> None:
        """Delete all media files from the store"""
        logger.info("🗑️ Starting media deletion...")
        media_files = await self.get_all_media()

        if not media_files:
            logger.info("No media files found to delete")
            return

        logger.warning(
            f"⚠️  About to delete {len(media_files)} media files. This action is irreversible!"
        )

        # Process media files in parallel batches
        batch_size = 10  # Process 10 media files at a time
        for i in range(0, len(media_files), batch_size):
            batch = media_files[i : i + batch_size]
            logger.info(
                f"Processing media batch {i//batch_size + 1}/{(len(media_files) + batch_size - 1)//batch_size}"
            )

            # Create tasks for parallel execution
            tasks = []
            for media_file in batch:
                media_id = media_file["id"]
                # Get media type and URL for logging
                media_type = "Unknown"
                media_url = "Unknown"
                if "image" in media_file and media_file["image"] is not None:
                    media_type = "Image"
                    media_url = media_file["image"].get("url", "Unknown")
                elif "sources" in media_file:
                    # Check if it's a video or 3D model based on the file structure
                    sources = media_file.get("sources", [])
                    if sources:
                        media_url = sources[0].get("url", "Unknown")
                        # Try to determine type from URL or assume it's a video
                        if any(
                            ext in media_url.lower()
                            for ext in [".mp4", ".mov", ".avi", ".webm"]
                        ):
                            media_type = "Video"
                        else:
                            media_type = "3D Model"
                else:
                    # Fallback for unknown media types
                    media_type = "File"
                    media_url = media_file.get("id", "Unknown")

                task = self._delete_media_with_logging(media_id, media_type, media_url)
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for j, result in enumerate(results):
                media_file = batch[j]
                media_id = media_file["id"]
                if isinstance(result, Exception):
                    logger.error(f"❌ Failed to delete media {media_id}: {result}")
                elif result:
                    logger.info(f"✅ Deleted media: {media_id}")
                else:
                    logger.error(f"❌ Failed to delete media: {media_id}")

    async def _delete_media_with_logging(
        self, media_id: str, media_type: str, media_url: str
    ) -> bool:
        """Delete a single media file with logging"""
        return await self.delete_media(media_id)

    async def delete_all_data(self) -> None:
        """Delete all store data (products, collections, orders, customers, media)"""
        logger.info("🚨 Starting complete store data deletion...")
        self.stats["start_time"] = datetime.now()

        try:
            # Delete in order: products first, then collections, then orders, then customers, then media
            await self.delete_all_products()
            await self.delete_all_collections()
            await self.delete_all_orders()
            await self.delete_all_customers()
            await self.delete_all_media()

            self.stats["end_time"] = datetime.now()
            self.print_summary()

        except Exception as e:
            logger.error(f"Error during bulk deletion: {e}")
            self.stats["errors"] += 1
            raise

    def print_summary(self) -> None:
        """Print deletion summary"""
        duration = None
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]

        logger.info("=" * 60)
        logger.info("📊 DELETION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Products deleted: {self.stats['products_deleted']}")
        logger.info(f"Collections deleted: {self.stats['collections_deleted']}")
        logger.info(f"Orders canceled: {self.stats['orders_deleted']}")
        logger.info(f"Customers deleted: {self.stats['customers_deleted']}")
        logger.info(f"Media files deleted: {self.stats['media_deleted']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        if duration:
            logger.info(f"Total duration: {duration}")
        logger.info("=" * 60)


async def main():
    """Main function to run the deletion script"""

    if not shop_domain or not access_token:
        logger.error(
            "Missing required environment variables: SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN"
        )
        return

    async with ShopifyStoreDeleter(shop_domain, access_token) as deleter:
        await deleter.delete_all_data()


if __name__ == "__main__":
    asyncio.run(main())
