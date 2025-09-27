"""
Shopify Product API client with full data traversal support
"""

from typing import Dict, Any, Optional, List
from app.core.logging import get_logger
from .base_client import BaseShopifyAPIClient

logger = get_logger(__name__)


class ProductAPIClient(BaseShopifyAPIClient):
    """Shopify Product API client with full data traversal"""

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
        }

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

                processed_products.append(product)

            # Return in the same format as the original query
            return {
                "edges": [{"node": product} for product in processed_products],
                "page_info": {"has_next_page": False},
            }

        return products_data

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
            "first": 250,  # Max batch size for cost efficiency
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
                            altText
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
            "first": 250,  # Max batch size for cost efficiency
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
            "first": 250,  # Max batch size for cost efficiency
            "after": cursor,
        }

        result = await self.execute_query(metafields_query, variables, shop_domain)
        product_data = result.get("product", {})
        return product_data.get("metafields", {})
