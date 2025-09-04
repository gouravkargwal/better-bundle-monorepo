"""
Main Table Storage Service for BetterBundle Python Worker

This service efficiently extracts key fields from raw JSON data and stores them
in structured main tables for fast querying and feature computation.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.core.database.connection_pool import get_connection_pool
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


@dataclass
class StorageResult:
    """Result of main table storage operation"""

    success: bool
    processed_count: int
    error_count: int
    errors: List[str]
    duration_ms: int


class MainTableStorageService:
    """Service for storing structured data in main tables"""

    def __init__(self):
        self.logger = logger
        self._connection_pool = None

    async def _get_connection_pool(self):
        """Get or initialize the connection pool"""
        if self._connection_pool is None:
            self._connection_pool = await get_connection_pool()
        return self._connection_pool

    async def store_all_data(self, shop_id: str) -> StorageResult:
        """Store all raw data for a shop to main tables"""
        start_time = now_utc()
        total_processed = 0
        total_errors = 0
        all_errors = []

        try:
            # Store each data type
            storage_operations = [
                ("orders", self.store_orders),
                ("products", self.store_products),
                ("customers", self.store_customers),
                ("collections", self.store_collections),
                ("customer_events", self.store_customer_events),
            ]

            for data_type, store_func in storage_operations:
                try:
                    self.logger.info(f"Starting {data_type} storage for shop {shop_id}")
                    result = await store_func(shop_id)
                    total_processed += result.processed_count
                    total_errors += result.error_count
                    all_errors.extend(result.errors)
                    self.logger.info(
                        f"Completed {data_type} storage: {result.processed_count} processed, {result.error_count} errors"
                    )
                except Exception as e:
                    error_msg = f"Failed to store {data_type}: {str(e)}"
                    self.logger.error(error_msg)
                    all_errors.append(error_msg)
                    total_errors += 1

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)

            return StorageResult(
                success=total_errors == 0,
                processed_count=total_processed,
                error_count=total_errors,
                errors=all_errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store all data: {str(e)}"
            self.logger.error(error_msg)

            return StorageResult(
                success=False,
                processed_count=total_processed,
                error_count=total_errors + 1,
                errors=all_errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_orders(self, shop_id: str) -> StorageResult:
        """Store orders from raw table to OrderData table"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get all raw orders for the shop using Prisma
            connection_pool = await self._get_connection_pool()

            async with connection_pool.get_connection() as db:
                raw_orders = await db.raworder.find_many(where={"shopId": shop_id})

            for raw_order in raw_orders:
                try:
                    # Parse the JSON payload
                    payload = raw_order.payload
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    # Extract order data
                    order_data = self._extract_order_fields(payload, shop_id)

                    if order_data:
                        # Use Prisma upsert instead of raw SQL
                        await db.orderdata.upsert(
                            where={
                                "shopId_orderId": {
                                    "shopId": shop_id,
                                    "orderId": order_data["orderId"],
                                }
                            },
                            data={
                                "shopId": shop_id,
                                "orderId": order_data["orderId"],
                                "orderName": order_data["orderName"],
                                "customerId": order_data["customerId"],
                                "customerEmail": order_data["customerEmail"],
                                "customerPhone": order_data["customerPhone"],
                                "totalAmount": order_data["totalAmount"],
                                "subtotalAmount": order_data["subtotalAmount"],
                                "totalTaxAmount": order_data["totalTaxAmount"],
                                "totalShippingAmount": order_data[
                                    "totalShippingAmount"
                                ],
                                "totalRefundedAmount": order_data[
                                    "totalRefundedAmount"
                                ],
                                "totalOutstandingAmount": order_data[
                                    "totalOutstandingAmount"
                                ],
                                "orderDate": order_data["orderDate"],
                                "processedAt": order_data["processedAt"],
                                "cancelledAt": order_data["cancelledAt"],
                                "cancelReason": order_data["cancelReason"],
                                "orderStatus": order_data["orderStatus"],
                                "orderLocale": order_data["orderLocale"],
                                "currencyCode": order_data["currencyCode"],
                                "presentmentCurrencyCode": order_data[
                                    "presentmentCurrencyCode"
                                ],
                                "confirmed": order_data["confirmed"],
                                "test": order_data["test"],
                                "tags": order_data["tags"],
                                "note": order_data["note"],
                                "lineItems": order_data["lineItems"],
                                "shippingAddress": order_data["shippingAddress"],
                                "billingAddress": order_data["billingAddress"],
                                "discountApplications": order_data[
                                    "discountApplications"
                                ],
                                "metafields": order_data["metafields"],
                            },
                        )
                        processed_count += 1
                    else:
                        self.logger.warning(
                            f"Could not extract order data from raw order {raw_order.id}"
                        )

                except Exception as e:
                    error_msg = f"Failed to process order {raw_order.id}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    error_count += 1

            self.logger.info(f"Successfully processed {processed_count} orders")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store orders: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_products(self, shop_id: str) -> StorageResult:
        """Store products from raw table to ProductData table"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get all raw products for the shop using Prisma
            connection_pool = await self._get_connection_pool()

            async with connection_pool.get_connection() as db:
                raw_products = await db.rawproduct.find_many(where={"shopId": shop_id})

                # Process each product using Prisma upsert
                for raw_product in raw_products:
                    try:
                        # Parse the JSON payload
                        payload = raw_product.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract product data
                        product_data = self._extract_product_fields(payload, shop_id)

                        if product_data:
                            # Use Prisma upsert instead of raw SQL
                            await db.productdata.upsert(
                                where={
                                    "shopId_productId": {
                                        "shopId": shop_id,
                                        "productId": product_data["productId"],
                                    }
                                },
                                data={
                                    "shopId": shop_id,
                                    "productId": product_data["productId"],
                                    "title": product_data["title"],
                                    "handle": product_data["handle"],
                                    "description": product_data["description"],
                                    "descriptionHtml": product_data["descriptionHtml"],
                                    "productType": product_data["productType"],
                                    "vendor": product_data["vendor"],
                                    "tags": product_data["tags"],
                                    "status": product_data["status"],
                                    "totalInventory": product_data["totalInventory"],
                                    "price": product_data["price"],
                                    "compareAtPrice": product_data["compareAtPrice"],
                                    "inventory": product_data["inventory"],
                                    "imageUrl": product_data["imageUrl"],
                                    "imageAlt": product_data["imageAlt"],
                                    "productCreatedAt": product_data[
                                        "productCreatedAt"
                                    ],
                                    "productUpdatedAt": product_data[
                                        "productUpdatedAt"
                                    ],
                                    "variants": product_data["variants"],
                                    "images": product_data["images"],
                                    "options": product_data["options"],
                                    "collections": product_data["collections"],
                                    "metafields": product_data["metafields"],
                                    "isActive": product_data["isActive"],
                                },
                            )
                            processed_count += 1
                        else:
                            self.logger.warning(
                                f"Could not extract product data from raw product {raw_product.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process product {raw_product.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

            self.logger.info(f"Successfully processed {processed_count} products")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store products: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_customers(self, shop_id: str) -> StorageResult:
        """Store customers from raw table to CustomerData table"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get all raw customers for the shop using Prisma
            connection_pool = await self._get_connection_pool()

            async with connection_pool.get_connection() as db:
                raw_customers = await db.rawcustomer.find_many(
                    where={"shopId": shop_id}
                )

                # Process each customer using Prisma upsert
                for raw_customer in raw_customers:
                    try:
                        # Parse the JSON payload
                        payload = raw_customer.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract customer data
                        customer_data = self._extract_customer_fields(payload, shop_id)

                        if customer_data:
                            # Use Prisma upsert instead of raw SQL
                            await db.customerdata.upsert(
                                where={
                                    "shopId_customerId": {
                                        "shopId": shop_id,
                                        "customerId": customer_data["customerId"],
                                    }
                                },
                                data={
                                    "shopId": shop_id,
                                    "customerId": customer_data["customerId"],
                                    "email": customer_data["email"],
                                    "firstName": customer_data["firstName"],
                                    "lastName": customer_data["lastName"],
                                    "totalSpent": customer_data["totalSpent"],
                                    "orderCount": customer_data["orderCount"],
                                    "lastOrderDate": customer_data["lastOrderDate"],
                                    "tags": customer_data["tags"],
                                    "createdAtShopify": customer_data[
                                        "createdAtShopify"
                                    ],
                                    "lastOrderId": customer_data["lastOrderId"],
                                    "location": customer_data["location"],
                                    "metafields": customer_data["metafields"],
                                    "state": customer_data["state"],
                                    "verifiedEmail": customer_data["verifiedEmail"],
                                    "taxExempt": customer_data["taxExempt"],
                                    "defaultAddress": customer_data["defaultAddress"],
                                    "addresses": customer_data["addresses"],
                                    "currencyCode": customer_data["currencyCode"],
                                    "customerLocale": customer_data["customerLocale"],
                                },
                            )
                            processed_count += 1
                        else:
                            self.logger.warning(
                                f"Could not extract customer data from raw customer {raw_customer.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process customer {raw_customer.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

            self.logger.info(f"Successfully processed {processed_count} customers")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store customers: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_collections(self, shop_id: str) -> StorageResult:
        """Store collections from raw table to CollectionData table"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get all raw collections for the shop using Prisma
            connection_pool = await self._get_connection_pool()

            async with connection_pool.get_connection() as db:
                raw_collections = await db.rawcollection.find_many(
                    where={"shopId": shop_id}
                )

                for raw_collection in raw_collections:
                    try:
                        # Parse the JSON payload
                        payload = raw_collection.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract collection data
                        collection_data = self._extract_collection_fields(
                            payload, shop_id
                        )

                        if collection_data:
                            # Use Prisma upsert instead of raw SQL
                            await db.collectiondata.upsert(
                                where={
                                    "shopId_collectionId": {
                                        "shopId": shop_id,
                                        "collectionId": collection_data["collectionId"],
                                    }
                                },
                                data={
                                    "shopId": shop_id,
                                    "collectionId": collection_data["collectionId"],
                                    "title": collection_data["title"],
                                    "handle": collection_data["handle"],
                                    "description": collection_data["description"],
                                    "sortOrder": collection_data["sortOrder"],
                                    "templateSuffix": collection_data["templateSuffix"],
                                    "seoTitle": collection_data["seoTitle"],
                                    "seoDescription": collection_data["seoDescription"],
                                    "imageUrl": collection_data["imageUrl"],
                                    "imageAlt": collection_data["imageAlt"],
                                    "productCount": collection_data["productCount"],
                                    "isAutomated": collection_data["isAutomated"],
                                    "metafields": collection_data["metafields"],
                                },
                            )
                            processed_count += 1
                        else:
                            self.logger.warning(
                                f"Could not extract collection data from raw collection {raw_collection.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to store collection {raw_collection.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store collections: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_customer_events(self, shop_id: str) -> StorageResult:
        """Store customer events from raw table to CustomerEventData table"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            # Get all raw customer events for the shop using Prisma
            connection_pool = await self._get_connection_pool()

            async with connection_pool.get_connection() as db:
                raw_events = await db.rawcustomerevent.find_many(
                    where={"shopId": shop_id}
                )

                for raw_event in raw_events:
                    try:
                        # Parse the JSON payload
                        payload = raw_event.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract customer event data
                        event_data_list = self._extract_customer_event_fields(
                            payload, shop_id
                        )

                        if event_data_list:
                            # Process each event using Prisma upsert
                            for event_data in event_data_list:
                                await db.customereventdata.upsert(
                                    where={
                                        "shopId_eventId": {
                                            "shopId": shop_id,
                                            "eventId": event_data["eventId"],
                                        }
                                    },
                                    data={
                                        "shopId": shop_id,
                                        "eventId": event_data["eventId"],
                                        "customerId": event_data["customerId"],
                                        "eventType": event_data["eventType"],
                                        "customerEmail": event_data["customerEmail"],
                                        "customerFirstName": event_data[
                                            "customerFirstName"
                                        ],
                                        "customerLastName": event_data[
                                            "customerLastName"
                                        ],
                                        "customerTags": event_data["customerTags"],
                                        "customerState": event_data["customerState"],
                                        "customerOrdersCount": event_data[
                                            "customerOrdersCount"
                                        ],
                                        "customerAmountSpent": event_data[
                                            "customerAmountSpent"
                                        ],
                                        "customerCurrency": event_data[
                                            "customerCurrency"
                                        ],
                                        "eventTimestamp": event_data["eventTimestamp"],
                                        "rawEventData": event_data["rawEventData"],
                                    },
                                )
                            processed_count += len(event_data_list)
                        else:
                            self.logger.warning(
                                f"Could not extract customer event data from raw event {raw_event.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process customer event {raw_event.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

            self.logger.info(
                f"Successfully processed {processed_count} customer events"
            )

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store customer events: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    def _extract_order_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key order fields from payload"""
        try:
            # Handle different payload structures
            if isinstance(payload, list):
                # If payload is a list, take the first item
                order_data = payload[0] if payload else {}
            elif isinstance(payload, dict):
                order_data = (
                    payload.get("order")
                    or payload.get("data", {}).get("order")
                    or payload
                )
            else:
                return None

            if (
                not order_data
                or not isinstance(order_data, dict)
                or not order_data.get("id")
            ):
                return None

            # Extract order ID
            order_id = self._extract_shopify_id(order_data.get("id", ""))
            if not order_id:
                return None

            # Extract customer information
            customer = order_data.get("customer", {})

            # Extract line items (keep as JSON for complex data)
            line_items = order_data.get("lineItems", {})
            if isinstance(line_items, dict) and "edges" in line_items:
                line_items = [
                    edge.get("node", {}) for edge in line_items.get("edges", [])
                ]

            return {
                "shopId": shop_id,
                "orderId": order_id,
                "orderName": order_data.get("name"),
                "customerId": (
                    self._extract_shopify_id(customer.get("id", ""))
                    if customer
                    else None
                ),
                "customerEmail": order_data.get("email") or customer.get("email"),
                "customerPhone": order_data.get("phone"),
                "totalAmount": float(
                    order_data.get("totalPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "subtotalAmount": float(
                    order_data.get("subtotalPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalTaxAmount": float(
                    order_data.get("totalTaxSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalShippingAmount": float(
                    order_data.get("totalShippingPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalRefundedAmount": float(
                    order_data.get("totalRefundedSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalOutstandingAmount": float(
                    order_data.get("totalOutstandingSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "orderDate": self._parse_datetime(order_data.get("createdAt")),
                "processedAt": self._parse_datetime(order_data.get("processedAt")),
                "cancelledAt": self._parse_datetime(order_data.get("cancelledAt")),
                "cancelReason": order_data.get("cancelReason"),
                "orderStatus": (
                    "cancelled" if order_data.get("cancelledAt") else "active"
                ),
                "orderLocale": order_data.get("customerLocale"),
                "currencyCode": order_data.get("currencyCode", "USD"),
                "presentmentCurrencyCode": order_data.get("presentmentCurrencyCode"),
                "confirmed": order_data.get("confirmed", False),
                "test": order_data.get("test", False),
                "tags": order_data.get("tags", []),
                "note": order_data.get("note"),
                "lineItems": line_items,
                "shippingAddress": order_data.get("shippingAddress"),
                "billingAddress": order_data.get("billingAddress"),
                "discountApplications": order_data.get("discountApplications", {}).get(
                    "edges", []
                ),
                "metafields": order_data.get("metafields", {}).get("edges", []),
            }

        except Exception as e:
            self.logger.error(f"Failed to extract order fields: {str(e)}")
            return None

    def _extract_product_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key product fields from payload"""
        try:
            # Handle different payload structures
            if isinstance(payload, list):
                # If payload is a list, take the first item
                product_data = payload[0] if payload else {}
            elif isinstance(payload, dict):
                product_data = (
                    payload.get("product")
                    or payload.get("data", {}).get("product")
                    or payload
                )
            else:
                return None

            if (
                not product_data
                or not isinstance(product_data, dict)
                or not product_data.get("id")
            ):
                return None

            # Extract product ID
            product_id = self._extract_shopify_id(product_data.get("id", ""))
            if not product_id:
                return None

            # Extract variants (keep as JSON for complex data)
            variants = product_data.get("variants", {})
            if isinstance(variants, dict) and "edges" in variants:
                variants = [edge.get("node", {}) for edge in variants.get("edges", [])]

            # Extract images (keep as JSON for complex data)
            images = product_data.get("images", {})
            if isinstance(images, dict) and "edges" in images:
                images = [edge.get("node", {}) for edge in images.get("edges", [])]

            # Extract options (keep as JSON for complex data)
            options = product_data.get("options", [])

            # Extract collections (keep as JSON for complex data)
            collections = product_data.get("collections", {})
            if isinstance(collections, dict) and "edges" in collections:
                collections = [
                    edge.get("node", {}) for edge in collections.get("edges", [])
                ]

            # Extract metafields (keep as JSON for complex data)
            metafields = product_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Get main image URL for fast access
            main_image_url = None
            if images:
                main_image = images[0]
                main_image_url = main_image.get("url")

            # Process tags - convert string to array if needed
            tags = product_data.get("tags", [])
            if isinstance(tags, str):
                # Split comma-separated tags and clean them
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif not isinstance(tags, list):
                tags = []

            return {
                "shopId": shop_id,
                "productId": product_id,
                "title": product_data.get("title", ""),
                "handle": product_data.get("handle", ""),
                "description": product_data.get("description"),
                "descriptionHtml": product_data.get("bodyHtml"),
                "productType": product_data.get("productType"),
                "vendor": product_data.get("vendor"),
                "tags": tags,
                "status": product_data.get("status", "active"),
                "totalInventory": product_data.get("totalInventory"),
                "price": self._get_product_price(variants),
                "compareAtPrice": self._get_product_compare_price(variants),
                "inventory": self._get_total_inventory(variants),
                "imageUrl": main_image_url,
                "imageAlt": images[0].get("altText") if images else None,
                "productCreatedAt": self._parse_datetime(product_data.get("createdAt")),
                "productUpdatedAt": self._parse_datetime(product_data.get("updatedAt")),
                "variants": variants,
                "images": images,
                "options": options,
                "collections": collections,
                "metafields": metafields,
                "isActive": product_data.get("status", "active") == "active",
            }

        except Exception as e:
            self.logger.error(f"Failed to extract product fields: {str(e)}")
            return None

    def _extract_customer_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key customer fields from payload"""
        try:
            # Handle different payload structures
            if isinstance(payload, list):
                # If payload is a list, take the first item
                customer_data = payload[0] if payload else {}
            elif isinstance(payload, dict):
                customer_data = (
                    payload.get("customer")
                    or payload.get("data", {}).get("customer")
                    or payload
                )
            else:
                return None

            if (
                not customer_data
                or not isinstance(customer_data, dict)
                or not customer_data.get("id")
            ):
                return None

            # Extract customer ID
            customer_id = self._extract_shopify_id(customer_data.get("id", ""))
            if not customer_id:
                return None

            # Extract default address
            default_address = customer_data.get("defaultAddress", {})

            # Extract addresses (keep as JSON for complex data)
            addresses = customer_data.get("addresses", {})
            if isinstance(addresses, dict) and "edges" in addresses:
                addresses = [
                    edge.get("node", {}) for edge in addresses.get("edges", [])
                ]

            # Extract metafields (keep as JSON for complex data)
            metafields = customer_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Process tags - convert string to array if needed
            tags = customer_data.get("tags", [])
            if isinstance(tags, str):
                # Split comma-separated tags and clean them
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif not isinstance(tags, list):
                tags = []

            return {
                "shopId": shop_id,
                "customerId": customer_id,
                "email": customer_data.get("email") or "",  # Ensure email is never None
                "firstName": customer_data.get("firstName")
                or "",  # Ensure firstName is never None
                "lastName": customer_data.get("lastName")
                or "",  # Ensure lastName is never None
                "totalSpent": float(customer_data.get("totalSpent", 0)),
                "orderCount": int(customer_data.get("ordersCount", 0)),
                "lastOrderDate": self._parse_datetime(
                    customer_data.get("lastOrderDate")
                ),
                "tags": tags,
                "createdAtShopify": self._parse_datetime(
                    customer_data.get("createdAt")
                ),
                "lastOrderId": customer_data.get("lastOrderId") or "",
                "location": (
                    {
                        "city": default_address.get("city"),
                        "province": default_address.get("province"),
                        "country": default_address.get("country"),
                        "zip": default_address.get("zip"),
                    }
                    if default_address
                    else None
                ),
                "metafields": metafields,
                "state": customer_data.get("state") or "",
                "verifiedEmail": customer_data.get("verifiedEmail", False),
                "taxExempt": customer_data.get("taxExempt", False),
                "defaultAddress": default_address,
                "addresses": addresses,
                "currencyCode": customer_data.get("currency") or "USD",
                "customerLocale": customer_data.get("locale") or "",
            }

        except Exception as e:
            self.logger.error(f"Failed to extract customer fields: {str(e)}")
            return None

    def _extract_collection_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key collection fields from payload"""
        try:
            # Handle different payload structures
            if isinstance(payload, list):
                # If payload is a list, take the first item
                collection_data = payload[0] if payload else {}
            elif isinstance(payload, dict):
                collection_data = (
                    payload.get("collection")
                    or payload.get("data", {}).get("collection")
                    or payload
                )
            else:
                return None

            if (
                not collection_data
                or not isinstance(collection_data, dict)
                or not collection_data.get("id")
            ):
                return None

            # Extract collection ID
            collection_id = self._extract_shopify_id(collection_data.get("id", ""))
            if not collection_id:
                return None

            # Extract image information
            image = collection_data.get("image", {})
            image_url = image.get("url") if image else None
            image_alt = image.get("altText") if image else None

            # Extract SEO information
            seo = collection_data.get("seo", {})

            # Extract metafields (keep as JSON for complex data)
            metafields = collection_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            return {
                "shopId": shop_id,
                "collectionId": collection_id,
                "title": collection_data.get("title", ""),
                "handle": collection_data.get("handle", ""),
                "description": collection_data.get("description"),
                "sortOrder": collection_data.get("sortOrder"),
                "templateSuffix": collection_data.get("templateSuffix"),
                "seoTitle": seo.get("title"),
                "seoDescription": seo.get("description"),
                "imageUrl": image_url,
                "imageAlt": image_alt,
                "productCount": int(collection_data.get("productsCount", 0)),
                "isAutomated": collection_data.get("ruleSet", {}).get("rules", [])
                != [],
                "metafields": metafields,
            }

        except Exception as e:
            self.logger.error(f"Failed to extract collection fields: {str(e)}")
            return None

    def _extract_customer_event_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract key customer event fields from payload"""
        try:
            # Handle different payload structures - customer events come from customers with events
            if isinstance(payload, list):
                # If payload is a list, take the first item
                customer_data = payload[0] if payload else {}
            elif isinstance(payload, dict):
                customer_data = (
                    payload.get("customer")
                    or payload.get("data", {}).get("customer")
                    or payload
                )
            else:
                return None

            if (
                not customer_data
                or not isinstance(customer_data, dict)
                or not customer_data.get("id")
            ):
                return None

            # Extract customer ID
            customer_id = self._extract_shopify_id(customer_data.get("id", ""))
            if not customer_id:
                return None

            # Extract events
            events = customer_data.get("events", {})
            if isinstance(events, dict) and "edges" in events:
                events = [edge.get("node", {}) for edge in events.get("edges", [])]
            elif not isinstance(events, list):
                events = []

            # Process each event
            event_data_list = []
            for event in events:
                event_id = self._extract_shopify_id(event.get("id", ""))
                if event_id:
                    event_data_list.append(
                        {
                            "shopId": shop_id,
                            "customerId": customer_id,
                            "eventId": event_id,
                            "eventType": event.get("type", "unknown"),
                            "customerEmail": customer_data.get("email"),
                            "customerFirstName": customer_data.get("firstName"),
                            "customerLastName": customer_data.get("lastName"),
                            "customerTags": customer_data.get("tags", []),
                            "customerState": customer_data.get("state"),
                            "customerOrdersCount": int(
                                customer_data.get("ordersCount", 0)
                            ),
                            "customerAmountSpent": float(
                                customer_data.get("totalSpent", 0)
                            ),
                            "customerCurrency": customer_data.get("currency", "USD"),
                            "eventTimestamp": self._parse_datetime(
                                event.get("createdAt")
                            ),
                            "rawEventData": event,
                        }
                    )

            return event_data_list

        except Exception as e:
            self.logger.error(f"Failed to extract customer event fields: {str(e)}")
            return None

    def _extract_shopify_id(self, gid: str) -> Optional[str]:
        """Extract numeric ID from Shopify GraphQL GID"""
        if not gid:
            return None
        try:
            # Handle GID format: gid://shopify/Order/123456789
            if gid.startswith("gid://shopify/"):
                return gid.split("/")[-1]
            return gid
        except Exception:
            return None

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not date_str:
            return None
        try:
            # Handle ISO format with timezone
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _get_product_price(self, variants: List[Dict[str, Any]]) -> float:
        """Get the minimum price from product variants"""
        if not variants:
            return 0.0
        prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
        return min(prices) if prices else 0.0

    def _get_product_compare_price(
        self, variants: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Get the minimum compare at price from product variants"""
        if not variants:
            return None
        compare_prices = [
            float(v.get("compareAtPrice", 0))
            for v in variants
            if v.get("compareAtPrice")
        ]
        return min(compare_prices) if compare_prices else None

    def _get_total_inventory(self, variants: List[Dict[str, Any]]) -> int:
        """Get total inventory across all variants"""
        if not variants:
            return 0
        return sum(int(v.get("inventoryQuantity", 0)) for v in variants)

    async def _upsert_order_data(self, order_data: Dict[str, Any]) -> None:
        """Upsert order data to OrderData table"""
        query = """
        INSERT INTO "OrderData" (
            "shopId", "orderId", "orderName", "customerId", "customerEmail", "customerPhone",
            "totalAmount", "subtotalAmount", "totalTaxAmount", "totalShippingAmount",
            "totalRefundedAmount", "totalOutstandingAmount", "orderDate", "processedAt",
            "cancelledAt", "cancelReason", "orderStatus", "orderLocale", "currencyCode",
            "presentmentCurrencyCode", "confirmed", "test", "tags", "note", "lineItems",
            "shippingAddress", "billingAddress", "discountApplications", "metafields"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28
        )
        ON CONFLICT ("shopId", "orderId") DO UPDATE SET
            "orderName" = EXCLUDED."orderName",
            "customerId" = EXCLUDED."customerId",
            "customerEmail" = EXCLUDED."customerEmail",
            "customerPhone" = EXCLUDED."customerPhone",
            "totalAmount" = EXCLUDED."totalAmount",
            "subtotalAmount" = EXCLUDED."subtotalAmount",
            "totalTaxAmount" = EXCLUDED."totalTaxAmount",
            "totalShippingAmount" = EXCLUDED."totalShippingAmount",
            "totalRefundedAmount" = EXCLUDED."totalRefundedAmount",
            "totalOutstandingAmount" = EXCLUDED."totalOutstandingAmount",
            "orderDate" = EXCLUDED."orderDate",
            "processedAt" = EXCLUDED."processedAt",
            "cancelledAt" = EXCLUDED."cancelledAt",
            "cancelReason" = EXCLUDED."cancelReason",
            "orderStatus" = EXCLUDED."orderStatus",
            "orderLocale" = EXCLUDED."orderLocale",
            "currencyCode" = EXCLUDED."currencyCode",
            "presentmentCurrencyCode" = EXCLUDED."presentmentCurrencyCode",
            "confirmed" = EXCLUDED."confirmed",
            "test" = EXCLUDED."test",
            "tags" = EXCLUDED."tags",
            "note" = EXCLUDED."note",
            "lineItems" = EXCLUDED."lineItems",
            "shippingAddress" = EXCLUDED."shippingAddress",
            "billingAddress" = EXCLUDED."billingAddress",
            "discountApplications" = EXCLUDED."discountApplications",
            "metafields" = EXCLUDED."metafields",
            "updatedAt" = NOW()
        """

        await self.db_client.execute(
            query,
            [
                order_data["shopId"],
                order_data["orderId"],
                order_data["orderName"],
                order_data["customerId"],
                order_data["customerEmail"],
                order_data["customerPhone"],
                order_data["totalAmount"],
                order_data["subtotalAmount"],
                order_data["totalTaxAmount"],
                order_data["totalShippingAmount"],
                order_data["totalRefundedAmount"],
                order_data["totalOutstandingAmount"],
                order_data["orderDate"],
                order_data["processedAt"],
                order_data["cancelledAt"],
                order_data["cancelReason"],
                order_data["orderStatus"],
                order_data["orderLocale"],
                order_data["currencyCode"],
                order_data["presentmentCurrencyCode"],
                order_data["confirmed"],
                order_data["test"],
                json.dumps(order_data["tags"]),
                order_data["note"],
                json.dumps(order_data["lineItems"]),
                json.dumps(order_data["shippingAddress"]),
                json.dumps(order_data["billingAddress"]),
                json.dumps(order_data["discountApplications"]),
                json.dumps(order_data["metafields"]),
            ],
        )

    async def _upsert_product_data(self, product_data: Dict[str, Any]) -> None:
        """Upsert product data to ProductData table"""
        query = """
        INSERT INTO "ProductData" (
            "shopId", "productId", "title", "handle", "description", "descriptionHtml",
            "productType", "vendor", "tags", "status", "totalInventory", "price",
            "compareAtPrice", "inventory", "imageUrl", "imageAlt", "productCreatedAt",
            "productUpdatedAt", "variants", "images", "options", "collections", "metafields", "isActive"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24
        )
        ON CONFLICT ("shopId", "productId") DO UPDATE SET
            "title" = EXCLUDED."title",
            "handle" = EXCLUDED."handle",
            "description" = EXCLUDED."description",
            "descriptionHtml" = EXCLUDED."descriptionHtml",
            "productType" = EXCLUDED."productType",
            "vendor" = EXCLUDED."vendor",
            "tags" = EXCLUDED."tags",
            "status" = EXCLUDED."status",
            "totalInventory" = EXCLUDED."totalInventory",
            "price" = EXCLUDED."price",
            "compareAtPrice" = EXCLUDED."compareAtPrice",
            "inventory" = EXCLUDED."inventory",
            "imageUrl" = EXCLUDED."imageUrl",
            "imageAlt" = EXCLUDED."imageAlt",
            "productCreatedAt" = EXCLUDED."productCreatedAt",
            "productUpdatedAt" = EXCLUDED."productUpdatedAt",
            "variants" = EXCLUDED."variants",
            "images" = EXCLUDED."images",
            "options" = EXCLUDED."options",
            "collections" = EXCLUDED."collections",
            "metafields" = EXCLUDED."metafields",
            "isActive" = EXCLUDED."isActive",
            "updatedAt" = NOW()
        """

        await self.db_client.execute(
            query,
            [
                product_data["shopId"],
                product_data["productId"],
                product_data["title"],
                product_data["handle"],
                product_data["description"],
                product_data["descriptionHtml"],
                product_data["productType"],
                product_data["vendor"],
                json.dumps(product_data["tags"]),
                product_data["status"],
                product_data["totalInventory"],
                product_data["price"],
                product_data["compareAtPrice"],
                product_data["inventory"],
                product_data["imageUrl"],
                product_data["imageAlt"],
                product_data["productCreatedAt"],
                product_data["productUpdatedAt"],
                json.dumps(product_data["variants"]),
                json.dumps(product_data["images"]),
                json.dumps(product_data["options"]),
                json.dumps(product_data["collections"]),
                json.dumps(product_data["metafields"]),
                product_data["isActive"],
            ],
        )

    async def _batch_upsert_product_data(
        self, product_data_list: List[Dict[str, Any]]
    ) -> None:
        """Batch upsert product data to ProductData table"""
        if not product_data_list:
            return

        # Prepare batch data
        batch_values = []
        for product_data in product_data_list:
            batch_values.append(
                [
                    product_data["shopId"],
                    product_data["productId"],
                    product_data["title"],
                    product_data["handle"],
                    product_data["description"],
                    product_data["descriptionHtml"],
                    product_data["productType"],
                    product_data["vendor"],
                    json.dumps(product_data["tags"]),
                    product_data["status"],
                    product_data["totalInventory"],
                    product_data["price"],
                    product_data["compareAtPrice"],
                    product_data["inventory"],
                    product_data["imageUrl"],
                    product_data["imageAlt"],
                    product_data["productCreatedAt"],
                    product_data["productUpdatedAt"],
                    json.dumps(product_data["variants"]),
                    json.dumps(product_data["images"]),
                    json.dumps(product_data["options"]),
                    json.dumps(product_data["collections"]),
                    json.dumps(product_data["metafields"]),
                    product_data["isActive"],
                ]
            )

        # Use batch insert with ON CONFLICT
        query = """
        INSERT INTO "ProductData" (
            "shopId", "productId", "title", "handle", "description", "descriptionHtml",
            "productType", "vendor", "tags", "status", "totalInventory", "price",
            "compareAtPrice", "inventory", "imageUrl", "imageAlt", "productCreatedAt",
            "productUpdatedAt", "variants", "images", "options", "collections", "metafields", "isActive"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24
        )
        ON CONFLICT ("shopId", "productId") DO UPDATE SET
            "title" = EXCLUDED."title",
            "handle" = EXCLUDED."handle",
            "description" = EXCLUDED."description",
            "descriptionHtml" = EXCLUDED."descriptionHtml",
            "productType" = EXCLUDED."productType",
            "vendor" = EXCLUDED."vendor",
            "tags" = EXCLUDED."tags",
            "status" = EXCLUDED."status",
            "totalInventory" = EXCLUDED."totalInventory",
            "price" = EXCLUDED."price",
            "compareAtPrice" = EXCLUDED."compareAtPrice",
            "inventory" = EXCLUDED."inventory",
            "imageUrl" = EXCLUDED."imageUrl",
            "imageAlt" = EXCLUDED."imageAlt",
            "productCreatedAt" = EXCLUDED."productCreatedAt",
            "productUpdatedAt" = EXCLUDED."productUpdatedAt",
            "variants" = EXCLUDED."variants",
            "images" = EXCLUDED."images",
            "options" = EXCLUDED."options",
            "collections" = EXCLUDED."collections",
            "metafields" = EXCLUDED."metafields",
            "isActive" = EXCLUDED."isActive",
            "updatedAt" = NOW()
        """

        # Execute individual inserts (executemany not available in SimpleDatabaseClient)
        for values in batch_values:
            await self.db_client.execute(query, values)

    async def _upsert_customer_data(self, customer_data: Dict[str, Any]) -> None:
        """Upsert customer data to CustomerData table"""
        query = """
        INSERT INTO "CustomerData" (
            "shopId", "customerId", "email", "firstName", "lastName", "totalSpent",
            "orderCount", "lastOrderDate", "tags", "createdAtShopify", "lastOrderId",
            "location", "metafields", "state", "verifiedEmail", "taxExempt",
            "defaultAddress", "addresses", "currencyCode", "customerLocale"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
        ON CONFLICT ("shopId", "customerId") DO UPDATE SET
            "email" = EXCLUDED."email",
            "firstName" = EXCLUDED."firstName",
            "lastName" = EXCLUDED."lastName",
            "totalSpent" = EXCLUDED."totalSpent",
            "orderCount" = EXCLUDED."orderCount",
            "lastOrderDate" = EXCLUDED."lastOrderDate",
            "tags" = EXCLUDED."tags",
            "createdAtShopify" = EXCLUDED."createdAtShopify",
            "lastOrderId" = EXCLUDED."lastOrderId",
            "location" = EXCLUDED."location",
            "metafields" = EXCLUDED."metafields",
            "state" = EXCLUDED."state",
            "verifiedEmail" = EXCLUDED."verifiedEmail",
            "taxExempt" = EXCLUDED."taxExempt",
            "defaultAddress" = EXCLUDED."defaultAddress",
            "addresses" = EXCLUDED."addresses",
            "currencyCode" = EXCLUDED."currencyCode",
            "customerLocale" = EXCLUDED."customerLocale",
            "updatedAt" = NOW()
        """

        await self.db_client.execute(
            query,
            [
                customer_data["shopId"],
                customer_data["customerId"],
                customer_data["email"],
                customer_data["firstName"],
                customer_data["lastName"],
                customer_data["totalSpent"],
                customer_data["orderCount"],
                customer_data["lastOrderDate"],
                json.dumps(customer_data["tags"]),
                customer_data["createdAtShopify"],
                customer_data["lastOrderId"],
                json.dumps(customer_data["location"]),
                json.dumps(customer_data["metafields"]),
                customer_data["state"],
                customer_data["verifiedEmail"],
                customer_data["taxExempt"],
                json.dumps(customer_data["defaultAddress"]),
                json.dumps(customer_data["addresses"]),
                customer_data["currencyCode"],
                customer_data["customerLocale"],
            ],
        )

    async def _batch_upsert_customer_data(
        self, customer_data_list: List[Dict[str, Any]]
    ) -> None:
        """Batch upsert customer data to CustomerData table"""
        if not customer_data_list:
            return

        # Prepare batch data
        batch_values = []
        for customer_data in customer_data_list:
            batch_values.append(
                [
                    customer_data["shopId"],
                    customer_data["customerId"],
                    customer_data["email"],
                    customer_data["firstName"],
                    customer_data["lastName"],
                    customer_data["totalSpent"],
                    customer_data["orderCount"],
                    customer_data["lastOrderDate"],
                    json.dumps(customer_data["tags"]),
                    customer_data["createdAtShopify"],
                    customer_data["lastOrderId"],
                    json.dumps(customer_data["location"]),
                    json.dumps(customer_data["metafields"]),
                    customer_data["state"],
                    customer_data["verifiedEmail"],
                    customer_data["taxExempt"],
                    json.dumps(customer_data["defaultAddress"]),
                    json.dumps(customer_data["addresses"]),
                    customer_data["currencyCode"],
                    customer_data["customerLocale"],
                ]
            )

        # Use batch insert with ON CONFLICT
        query = """
        INSERT INTO "CustomerData" (
            "shopId", "customerId", "email", "firstName", "lastName", "totalSpent",
            "orderCount", "lastOrderDate", "tags", "createdAtShopify", "lastOrderId",
            "location", "metafields", "state", "verifiedEmail", "taxExempt",
            "defaultAddress", "addresses", "currencyCode", "customerLocale"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
        )
        ON CONFLICT ("shopId", "customerId") DO UPDATE SET
            "email" = EXCLUDED."email",
            "firstName" = EXCLUDED."firstName",
            "lastName" = EXCLUDED."lastName",
            "totalSpent" = EXCLUDED."totalSpent",
            "orderCount" = EXCLUDED."orderCount",
            "lastOrderDate" = EXCLUDED."lastOrderDate",
            "tags" = EXCLUDED."tags",
            "createdAtShopify" = EXCLUDED."createdAtShopify",
            "lastOrderId" = EXCLUDED."lastOrderId",
            "location" = EXCLUDED."location",
            "metafields" = EXCLUDED."metafields",
            "state" = EXCLUDED."state",
            "verifiedEmail" = EXCLUDED."verifiedEmail",
            "taxExempt" = EXCLUDED."taxExempt",
            "defaultAddress" = EXCLUDED."defaultAddress",
            "addresses" = EXCLUDED."addresses",
            "currencyCode" = EXCLUDED."currencyCode",
            "customerLocale" = EXCLUDED."customerLocale",
            "updatedAt" = NOW()
        """

        # Execute individual inserts (executemany not available in SimpleDatabaseClient)
        for values in batch_values:
            await self.db_client.execute(query, values)

    async def _upsert_collection_data(self, collection_data: Dict[str, Any]) -> None:
        """Upsert collection data to CollectionData table"""
        query = """
        INSERT INTO "CollectionData" (
            "shopId", "collectionId", "title", "handle", "description", "sortOrder",
            "templateSuffix", "seoTitle", "seoDescription", "imageUrl", "imageAlt",
            "productCount", "isAutomated", "metafields"
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
        )
        ON CONFLICT ("shopId", "collectionId") DO UPDATE SET
            "title" = EXCLUDED."title",
            "handle" = EXCLUDED."handle",
            "description" = EXCLUDED."description",
            "sortOrder" = EXCLUDED."sortOrder",
            "templateSuffix" = EXCLUDED."templateSuffix",
            "seoTitle" = EXCLUDED."seoTitle",
            "seoDescription" = EXCLUDED."seoDescription",
            "imageUrl" = EXCLUDED."imageUrl",
            "imageAlt" = EXCLUDED."imageAlt",
            "productCount" = EXCLUDED."productCount",
            "isAutomated" = EXCLUDED."isAutomated",
            "metafields" = EXCLUDED."metafields",
            "updatedAt" = NOW()
        """

        await self.db_client.execute(
            query,
            [
                collection_data["shopId"],
                collection_data["collectionId"],
                collection_data["title"],
                collection_data["handle"],
                collection_data["description"],
                collection_data["sortOrder"],
                collection_data["templateSuffix"],
                collection_data["seoTitle"],
                collection_data["seoDescription"],
                collection_data["imageUrl"],
                collection_data["imageAlt"],
                collection_data["productCount"],
                collection_data["isAutomated"],
                json.dumps(collection_data["metafields"]),
            ],
        )

    async def _upsert_customer_event_data(
        self, event_data_list: List[Dict[str, Any]]
    ) -> None:
        """Upsert customer event data to CustomerEventData table"""
        if not event_data_list:
            return

        for event_data in event_data_list:
            query = """
            INSERT INTO "CustomerEventData" (
                "shopId", "customerId", "eventId", "eventType", "customerEmail",
                "customerFirstName", "customerLastName", "customerTags", "customerState",
                "customerOrdersCount", "customerAmountSpent", "customerCurrency",
                "eventTimestamp", "rawEventData"
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            ON CONFLICT ("shopId", "eventId") DO UPDATE SET
                "customerId" = EXCLUDED."customerId",
                "eventType" = EXCLUDED."eventType",
                "customerEmail" = EXCLUDED."customerEmail",
                "customerFirstName" = EXCLUDED."customerFirstName",
                "customerLastName" = EXCLUDED."customerLastName",
                "customerTags" = EXCLUDED."customerTags",
                "customerState" = EXCLUDED."customerState",
                "customerOrdersCount" = EXCLUDED."customerOrdersCount",
                "customerAmountSpent" = EXCLUDED."customerAmountSpent",
                "customerCurrency" = EXCLUDED."customerCurrency",
                "eventTimestamp" = EXCLUDED."eventTimestamp",
                "rawEventData" = EXCLUDED."rawEventData",
                "updatedAt" = NOW()
            """

            await self.db_client.execute(
                query,
                [
                    event_data["shopId"],
                    event_data["customerId"],
                    event_data["eventId"],
                    event_data["eventType"],
                    event_data["customerEmail"],
                    event_data["customerFirstName"],
                    event_data["customerLastName"],
                    json.dumps(event_data["customerTags"]),
                    event_data["customerState"],
                    event_data["customerOrdersCount"],
                    event_data["customerAmountSpent"],
                    event_data["customerCurrency"],
                    event_data["eventTimestamp"],
                    json.dumps(event_data["rawEventData"]),
                ],
            )
