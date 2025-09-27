"""
Shopify Collection API client with full data traversal support
"""

from typing import Dict, Any, Optional, List
from app.core.logging import get_logger
from .base_client import BaseShopifyAPIClient

logger = get_logger(__name__)


class CollectionAPIClient(BaseShopifyAPIClient):
    """Shopify Collection API client with full data traversal"""

    async def get_collections(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get collections from shop - supports both pagination and specific IDs"""
        # Handle specific collection IDs (for webhooks)
        if collection_ids:
            return await self._get_collections_by_ids(shop_domain, collection_ids)

        # Regular pagination logic
        variables = {
            "first": limit or 250,
            "after": cursor,
            "query": query,
        }

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
                        description
                        handle
                        created_at: createdAt
                        updated_at: updatedAt
                        published_at: publishedAt
                        seo {
                            title
                            description
                        }
                        template_suffix: templateSuffix
                        image {
                            id
                            url
                            alt_text: altText
                            width
                            height
                        }
                        products(first: 50) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
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
        collections_data = result.get("collections", {})

        # Process each collection to fetch all products if needed
        if collections_data.get("edges"):
            processed_collections = []

            for collection_edge in collections_data["edges"]:
                collection = collection_edge["node"]

                # Check and fetch additional products if needed
                products = collection.get("products", {})
                products_page_info = products.get("page_info", {})
                if products_page_info.get("has_next_page"):
                    all_products = products.get("edges", []).copy()
                    products_cursor = products_page_info.get("end_cursor")

                    while products_cursor:
                        rate_limit_info = await self.check_rate_limit(shop_domain)
                        if not rate_limit_info["can_make_request"]:
                            await self.wait_for_rate_limit(shop_domain)

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

                    collection["products"] = {
                        "edges": all_products,
                        "page_info": {"has_next_page": False},
                    }

                processed_collections.append(collection)

            # Return in the same format as the original query
            return {
                "edges": [{"node": collection} for collection in processed_collections],
                "page_info": {"has_next_page": False},
            }

        return collections_data

    async def _get_collections_by_ids(
        self, shop_domain: str, collection_ids: List[str]
    ) -> Dict[str, Any]:
        """Get specific collections by IDs - reuses existing logic for products"""
        processed_collections = []

        for collection_id in collection_ids:
            try:
                # Get single collection with full data (products)
                collection_data = await self._get_single_collection_full_data(
                    shop_domain, collection_id
                )
                if collection_data:
                    processed_collections.append(collection_data)
            except Exception as e:
                logger.error(f"Failed to fetch collection {collection_id}: {e}")

        # Return in the same format as the original query
        return {
            "edges": [{"node": collection} for collection in processed_collections],
            "page_info": {"has_next_page": False},
        }

    async def _get_single_collection_full_data(
        self, shop_domain: str, collection_id: str
    ) -> Dict[str, Any]:
        """Get a single collection with all products - reuses existing logic"""
        graphql_query = """
        query($id: ID!) {
            collection(id: $id) {
                id
                title
                description
                handle
                createdAt
                updatedAt
                publishedAt
                seo {
                    title
                    description
                }
                templateSuffix
                image {
                    id
                    url
                    altText
                    width
                    height
                }
                products(first: 50) {
                    edges {
                        node {
                            id
                            title
                            handle
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

        variables = {"id": f"gid://shopify/Collection/{collection_id}"}
        result = await self.execute_query(graphql_query, variables, shop_domain)
        collection = result.get("collection", {})

        if not collection:
            return None

        # Reuse the same logic for fetching additional products
        # Check and fetch additional products if needed
        products = collection.get("products", {})
        products_page_info = products.get("pageInfo", {})
        if products_page_info.get("hasNextPage"):
            all_products = products.get("edges", []).copy()
            products_cursor = products_page_info.get("endCursor")

            while products_cursor:
                rate_limit_info = await self.check_rate_limit(shop_domain)
                if not rate_limit_info["can_make_request"]:
                    await self.wait_for_rate_limit(shop_domain)

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

            collection["products"] = {
                "edges": all_products,
                "page_info": {"has_next_page": False},
            }

        return collection

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
