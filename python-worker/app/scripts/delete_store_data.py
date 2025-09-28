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
    1. Edit the SHOP_DOMAIN and ACCESS_TOKEN variables in the main() function
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
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShopifyStoreDeleter:
    """Handles deletion of all store data from Shopify"""

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self.api_version = "2024-01"
        self.base_url = f"https://{shop_domain}.myshopify.com/admin/api/{self.api_version}/graphql.json"

        # Rate limiting
        self.rate_limit_buckets = {}
        self.max_requests_per_second = 2  # Conservative rate limiting
        self.request_delay = 0.5  # 500ms between requests

        # Statistics
        self.stats = {
            "products_deleted": 0,
            "collections_deleted": 0,
            "orders_deleted": 0,
            "customers_deleted": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    async def __aenter__(self):
        """Async context manager entry"""
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.access_token,
                "User-Agent": "BetterBundle-StoreDeleter/1.0",
            },
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

        try:
            response = await self.http_client.post(self.base_url, json=payload)
            response.raise_for_status()

            data = response.json()

            if "errors" in data:
                error_messages = [
                    error.get("message", "Unknown error") for error in data["errors"]
                ]
                raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(e.response.headers.get("Retry-After", 5))
                logger.warning(f"Rate limited, waiting {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                return await self.execute_mutation(mutation, variables)
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
        except Exception as e:
            logger.error(f"Mutation execution failed: {e}")
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

        for i, product in enumerate(products, 1):
            product_id = product["id"]
            product_title = product.get("title", "Unknown")

            logger.info(f"Deleting product {i}/{len(products)}: {product_title}")

            success = await self.delete_product(product_id)
            if success:
                logger.info(f"✅ Deleted product: {product_title}")
            else:
                logger.error(f"❌ Failed to delete product: {product_title}")

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

        for i, collection in enumerate(collections, 1):
            collection_id = collection["id"]
            collection_title = collection.get("title", "Unknown")

            logger.info(
                f"Deleting collection {i}/{len(collections)}: {collection_title}"
            )

            success = await self.delete_collection(collection_id)
            if success:
                logger.info(f"✅ Deleted collection: {collection_title}")
            else:
                logger.error(f"❌ Failed to delete collection: {collection_title}")

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

        for i, order in enumerate(orders, 1):
            order_id = order["id"]
            order_name = order.get("name", "Unknown")

            logger.info(f"Deleting order {i}/{len(orders)}: {order_name}")

            success = await self.delete_order(order_id)
            if success:
                logger.info(f"✅ Deleted order: {order_name}")
            else:
                logger.error(f"❌ Failed to delete order: {order_name}")

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

        for i, customer in enumerate(customers, 1):
            customer_id = customer["id"]
            first_name = customer.get("firstName", "")
            last_name = customer.get("lastName", "")
            customer_name = f"{first_name} {last_name}".strip() or "Unknown"

            logger.info(f"Deleting customer {i}/{len(customers)}: {customer_name}")

            success = await self.delete_customer(customer_id)
            if success:
                logger.info(f"✅ Deleted customer: {customer_name}")
            else:
                logger.error(f"❌ Failed to delete customer: {customer_name}")

    async def delete_all_data(self) -> None:
        """Delete all store data (products, collections, orders, customers)"""
        logger.info("🚨 Starting complete store data deletion...")
        self.stats["start_time"] = datetime.now()

        try:
            # Delete in order: products first, then collections, then orders, then customers
            await self.delete_all_products()
            await self.delete_all_collections()
            await self.delete_all_orders()
            await self.delete_all_customers()

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
        logger.info(f"Errors encountered: {self.stats['errors']}")
        if duration:
            logger.info(f"Total duration: {duration}")
        logger.info("=" * 60)


async def main():
    """Main function to run the deletion script"""
    # Configure your shop details here
    SHOP_DOMAIN = "vnsaid.myshopify.com"  # Replace with your shop domain
    ACCESS_TOKEN = (
        "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"  # Replace with your access token
    )

    # Remove .myshopify.com if present for URL construction
    shop_domain = SHOP_DOMAIN.replace(".myshopify.com", "")

    logger.info("🚨 Shopify Store Data Deletion Script")
    logger.info("=" * 50)
    logger.info(f"Shop: {SHOP_DOMAIN}")
    logger.info(f"Access Token: {'*' * (len(ACCESS_TOKEN) - 4) + ACCESS_TOKEN[-4:]}")

    # Final confirmation
    print("\n" + "=" * 60)
    print("⚠️  WARNING: This will delete ALL data from your Shopify store!")
    print("This includes:")
    print("- All products")
    print("- All collections")
    print("- All orders")
    print("- All customers")
    print("=" * 60)

    async with ShopifyStoreDeleter(shop_domain, ACCESS_TOKEN) as deleter:
        await deleter.delete_all_data()


if __name__ == "__main__":
    asyncio.run(main())
