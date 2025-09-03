from ast import Tuple
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class ShopifyEnhancedAPIClient:
    """Enhanced Shopify API client using our working GraphQL queries"""

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
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            },
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def execute_graphql_query(
        self, query: str, variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query with error handling"""
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables

            async with asyncio.timeout(45):
                response = await self.client.post(self.graphql_url, json=payload)

            response.raise_for_status()
            result = response.json()

            # Check for GraphQL errors
            if "errors" in result:
                error_msg = f"GraphQL errors: {result['errors']}"
                logger.warning(f"GraphQL query had errors: {error_msg}")
                return {"data": None, "errors": result["errors"]}

            return result

        except Exception as e:
            logger.error(f"GraphQL query failed: {str(e)}")
            return {"data": None, "errors": [{"message": str(e)}]}

    async def fetch_products(
        self, since_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """Fetch products using our working GraphQL query"""
        query = """
        query GetProducts($first: Int!) {
            products(first: $first) {
                edges {
                    node {
                        id
                        title
                        productType
                        vendor
                        tags
                        status
                        totalInventory
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
                        images(first: 10) {
                            edges {
                                node {
                                    id
                                    url
                                    altText
                                    width
                                    height
                                }
                            }
                        }
                        options(first: 10) {
                            id
                            name
                            values
                        }
                        variants(first: 20) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    sku
                                    barcode
                                    inventoryQuantity
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
                pageInfo {
                    hasNextPage
                    hasPreviousPage
                    startCursor
                    endCursor
                }
            }
        }
        """

        try:
            result = await self.execute_graphql_query(query, {"first": 250})

            if result.get("errors"):
                logger.warning("Products API has permission issues, skipping")
                return [], False

            if result.get("data") and result["data"].get("products"):
                products = [
                    edge["node"] for edge in result["data"]["products"]["edges"]
                ]
                logger.info(f"Successfully fetched {len(products)} products")
                return products, True
            else:
                logger.warning("No products data returned")
                return [], False

        except Exception as e:
            logger.error(f"Failed to fetch products: {str(e)}")
            return [], False

    async def fetch_customers(
        self, since_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """Fetch customers using our working GraphQL query"""
        query = """
        query GetCustomers($first: Int!) {
            customers(first: $first) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        email
                        createdAt
                        updatedAt
                        numberOfOrders
                        state
                        amountSpent {
                            amount
                            currencyCode
                        }
                        verifiedEmail
                        taxExempt
                        tags
                        addresses {
                            id
                            firstName
                            lastName
                            address1
                            city
                            province
                            country
                            zip
                            phone
                            name
                            provinceCode
                            countryCodeV2
                        }
                        defaultAddress {
                            id
                            address1
                            city
                            province
                            country
                            zip
                            phone
                            provinceCode
                            countryCodeV2
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
        """

        try:
            result = await self.execute_graphql_query(query, {"first": 250})

            if result.get("errors"):
                logger.warning("Customers API has permission issues, skipping")
                return [], False

            if result.get("data") and result["data"].get("customers"):
                customers = [
                    edge["node"] for edge in result["data"]["customers"]["edges"]
                ]
                logger.info(f"Successfully fetched {len(customers)} customers")
                return customers, True
            else:
                logger.warning("No customers data returned")
                return [], False

        except Exception as e:
            logger.error(f"Failed to fetch customers: {str(e)}")
            return [], False

    async def fetch_orders(
        self, since_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """Fetch orders using our working GraphQL query"""
        query = """
        query GetOrders($first: Int!) {
            orders(first: $first) {
                edges {
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
                        customer {
                            id
                            firstName
                            lastName
                            email
                            tags
                        }
                        lineItems(first: 20) {
                            edges {
                                node {
                                    id
                                    title
                                    quantity
                                    variant {
                                        id
                                        title
                                        price
                                        sku
                                        barcode
                                        product {
                                            id
                                            title
                                            productType
                                            vendor
                                            tags
                                        }
                                    }
                                }
                            }
                        }
                        shippingAddress {
                            address1
                            city
                            province
                            country
                            zip
                            phone
                            provinceCode
                            countryCodeV2
                        }
                        billingAddress {
                            address1
                            city
                            province
                            country
                            zip
                            phone
                            provinceCode
                            countryCodeV2
                        }
                        tags
                        note
                        confirmed
                        test
                        totalRefundedSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        totalOutstandingSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        customerLocale
                        currencyCode
                        presentmentCurrencyCode
                        discountApplications(first: 10) {
                            edges {
                                node {
                                    value {
                                        ... on MoneyV2 {
                                            amount
                                            currencyCode
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
        """

        try:
            result = await self.execute_graphql_query(query, {"first": 250})

            if result.get("errors"):
                logger.warning("Orders API has permission issues, skipping")
                return [], False

            if result.get("data") and result["data"].get("orders"):
                orders = [edge["node"] for edge in result["data"]["orders"]["edges"]]
                logger.info(f"Successfully fetched {len(orders)} orders")
                return orders, True
            else:
                logger.warning("No orders data returned")
                return [], False

        except Exception as e:
            logger.error(f"Failed to fetch orders: {str(e)}")
            return [], False

    async def fetch_collections(
        self, since_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """Fetch collections using our working GraphQL query"""
        query = """
        query GetCollections($first: Int!) {
            collections(first: $first) {
                edges {
                    node {
                        id
                        title
                        description
                        descriptionHtml
                        handle
                        updatedAt
                        sortOrder
                        templateSuffix
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
                        products(first: 20) {
                            edges {
                                node {
                                    id
                                    title
                                    handle
                                    productType
                                    vendor
                                    tags
                                    priceRangeV2 {
                                        minVariantPrice {
                                            amount
                                            currencyCode
                                        }
                                        maxVariantPrice {
                                            amount
                                            currencyCode
                                        }
                                    }
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
                                    }
                                    variants(first: 5) {
                                        edges {
                                            node {
                                                id
                                                title
                                                price
                                                sku
                                                barcode
                                                availableForSale
                                            }
                                        }
                                    }
                                }
                            }
                            pageInfo {
                                hasNextPage
                                hasPreviousPage
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
                                condition
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
        }
        """

        try:
            result = await self.execute_graphql_query(query, {"first": 250})

            if result.get("errors"):
                logger.warning("Collections API has permission issues, skipping")
                return [], False

            if result.get("data") and result["data"].get("collections"):
                collections = [
                    edge["node"] for edge in result["data"]["collections"]["edges"]
                ]
                logger.info(f"Successfully fetched {len(collections)} collections")
                return collections, True
            else:
                logger.warning("No collections data returned")
                return [], False

        except Exception as e:
            logger.error(f"Failed to fetch collections: {str(e)}")
            return [], False

    async def fetch_customer_events(
        self, since_date: Optional[str] = None
    ) -> Tuple[List[Dict], bool]:
        """Fetch customer events using our working GraphQL query"""
        query = """
        query GetCustomerBehaviorData($first: Int!) {
            customers(first: $first) {
                edges {
                    node {
                        id
                        firstName
                        lastName
                        email
                        createdAt
                        updatedAt
                        numberOfOrders
                        amountSpent {
                            amount
                            currencyCode
                        }
                        tags
                        state
                        verifiedEmail
                        taxExempt
                        events(first: 20) {
                            edges {
                                node {
                                    id
                                    __typename
                                }
                            }
                        }
                        orders(first: 20) {
                            edges {
                                node {
                                    id
                                    name
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
                                    confirmed
                                    test
                                    tags
                                    note
                                    customerLocale
                                    currencyCode
                                    lineItems(first: 15) {
                                        edges {
                                            node {
                                                id
                                                title
                                                quantity
                                                variant {
                                                    id
                                                    title
                                                    price
                                                    sku
                                                    barcode
                                                    product {
                                                        id
                                                        title
                                                        productType
                                                        vendor
                                                        tags
                                                        collections(first: 5) {
                                                            edges {
                                                                node {
                                                                    id
                                                                    title
                                                                    handle
                                                                    description
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    shippingAddress {
                                        address1
                                        city
                                        province
                                        country
                                        zip
                                        phone
                                        provinceCode
                                        countryCodeV2
                                    }
                                    billingAddress {
                                        address1
                                        city
                                        province
                                        country
                                        zip
                                        phone
                                        provinceCode
                                        countryCodeV2
                                        countryCodeV2
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
        """

        try:
            result = await self.execute_graphql_query(query, {"first": 250})

            if result.get("errors"):
                logger.warning("Customer Events API has permission issues, skipping")
                return [], False

            if result.get("data") and result["data"].get("customers"):
                customers_with_events = [
                    edge["node"] for edge in result["data"]["customers"]["edges"]
                ]
                logger.info(
                    f"Successfully fetched {len(customers_with_events)} customers with events"
                )
                return customers_with_events, True
            else:
                logger.warning("No customer events data returned")
                return [], False

        except Exception as e:
            logger.error(f"Failed to fetch customer events: {str(e)}")
            return [], False

    async def check_api_permissions(self) -> Dict[str, bool]:
        """Check which APIs have permission access"""
        permissions = {
            "products": False,
            "customers": False,
            "orders": False,
            "collections": False,
            "customer_events": False,
        }

        # Test each API with minimal queries
        test_queries = {
            "products": "query { products(first: 1) { edges { node { id } } } }",
            "customers": "query { customers(first: 1) { edges { node { id } } } }",
            "orders": "query { orders(first: 1) { edges { node { id } } } }",
            "collections": "query { collections(first: 1) { edges { node { id } } } }",
            "customer_events": "query { customers(first: 1) { edges { node { id events(first: 1) { edges { node { id } } } } } } }",
        }

        for api_name, query in test_queries.items():
            try:
                result = await self.execute_graphql_query(query)
                permissions[api_name] = not bool(result.get("errors"))
                logger.info(f"API {api_name} permission check: {permissions[api_name]}")
            except Exception as e:
                logger.warning(f"API {api_name} permission check failed: {str(e)}")
                permissions[api_name] = False

        return permissions


def calculate_since_date(days_back: int = settings.MAX_INITIAL_DAYS) -> str:
    """Calculate date for data collection using ISO format"""
    date = datetime.now() - timedelta(days=days_back)
    return date.isoformat()
