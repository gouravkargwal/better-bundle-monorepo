"""
Field Extraction Service for BetterBundle Python Worker

This service handles the extraction of structured fields from raw Shopify API data
for storage in main tables.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class FieldExtractorService:
    """Service for extracting structured fields from raw Shopify data"""

    def __init__(self):
        self.logger = logger
        # Simple cache for GID normalization to avoid repeated processing
        self._gid_cache = {}

    def extract_fields_generic(
        self, data_type: str, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generic field extraction method that delegates to specific extraction methods"""
        try:
            if data_type == "orders":
                return self.extract_order_fields(payload, shop_id)
            elif data_type == "products":
                return self.extract_product_fields(payload, shop_id)
            elif data_type == "customers":
                return self.extract_customer_fields(payload, shop_id)
            elif data_type == "collections":
                return self.extract_collection_fields(payload, shop_id)
            else:
                self.logger.error(f"Unknown data type for extraction: {data_type}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to extract {data_type} fields: {str(e)}")
            return None

    def extract_order_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key order fields from nested JSON payload"""
        try:
            # Extract order data using generic method
            order_data = self._extract_payload_data(payload, "order")

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

            # Extract GraphQL edge data using generic method
            line_items = self._extract_graphql_edges(order_data.get("lineItems", {}))
            discount_applications = self._extract_graphql_edges(
                order_data.get("discountApplications", {})
            )
            metafields = self._extract_graphql_edges(order_data.get("metafields", {}))
            fulfillments = order_data.get("fulfillments", [])
            transactions = order_data.get("transactions", [])

            # Extract simple fields
            shipping_address = order_data.get("shippingAddress")
            billing_address = order_data.get("billingAddress")

            # Process tags using generic method
            tags = self._process_tags(order_data.get("tags", []))

            return {
                "shopId": shop_id,
                "orderId": order_id,
                "orderName": order_data.get("name"),
                "customerId": (
                    self._extract_shopify_id(customer.get("id", ""))
                    if customer
                    else None
                ),
                "customerEmail": order_data.get("email")
                or (customer.get("email") if customer else None),
                "customerPhone": order_data.get("phone"),
                "customerDisplayName": (
                    customer.get("displayName") if customer else None
                ),
                "customerState": customer.get("state") if customer else None,
                "customerVerifiedEmail": (
                    customer.get("verifiedEmail") if customer else None
                ),
                "customerCreatedAt": (
                    self._parse_datetime(customer.get("createdAt"))
                    if customer
                    else None
                ),
                "customerUpdatedAt": (
                    self._parse_datetime(customer.get("updatedAt"))
                    if customer
                    else None
                ),
                "customerDefaultAddress": (
                    customer.get("defaultAddress") if customer else None
                ),
                "totalAmount": self._extract_money_amount(
                    order_data.get("totalPriceSet", {})
                ),
                "subtotalAmount": self._extract_money_amount(
                    order_data.get("subtotalPriceSet", {})
                ),
                "totalTaxAmount": self._extract_money_amount(
                    order_data.get("totalTaxSet", {})
                ),
                "totalShippingAmount": self._extract_money_amount(
                    order_data.get("totalShippingPriceSet", {})
                ),
                "totalRefundedAmount": self._extract_money_amount(
                    order_data.get("totalRefundedSet", {})
                ),
                "totalOutstandingAmount": self._extract_money_amount(
                    order_data.get("totalOutstandingSet", {})
                ),
                "orderDate": self._parse_datetime(order_data.get("createdAt"))
                or now_utc(),
                "processedAt": self._parse_datetime(order_data.get("processedAt")),
                "cancelledAt": self._parse_datetime(order_data.get("cancelledAt")),
                "cancelReason": order_data.get("cancelReason"),
                "orderLocale": order_data.get("customerLocale"),
                "currencyCode": order_data.get("currencyCode", "USD"),
                "presentmentCurrencyCode": order_data.get("presentmentCurrencyCode"),
                "confirmed": order_data.get("confirmed", False),
                "test": order_data.get("test", False),
                "tags": tags,
                "note": order_data.get("note"),
                "lineItems": line_items,
                "shippingAddress": self._normalize_gid_in_dict(shipping_address),
                "billingAddress": self._normalize_gid_in_dict(billing_address),
                "discountApplications": discount_applications,
                "metafields": metafields,
                "fulfillments": self._normalize_gid_in_dict(fulfillments),
                "transactions": self._normalize_gid_in_dict(transactions),
            }

        except Exception as e:
            import traceback

            self.logger.error(f"Failed to extract order fields: {str(e)}")
            self.logger.error(f"Exception type: {type(e).__name__}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Payload that caused error: {payload}")
            self.logger.error(f"Shop ID: {shop_id}")
            return None

    def extract_product_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key product fields from nested JSON payload"""
        try:
            # Extract product data using generic method
            product_data = self._extract_payload_data(payload, "product")

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

            # Extract GraphQL edge data using generic method
            variants = self._extract_graphql_edges(product_data.get("variants", {}))
            images = self._extract_graphql_edges(product_data.get("images", {}))
            collections = self._extract_graphql_edges(
                product_data.get("collections", {})
            )
            metafields = self._extract_graphql_edges(product_data.get("metafields", {}))

            # Extract simple fields
            options = product_data.get("options", [])

            # Get main image URL for fast access
            main_image_url = None
            if images:
                main_image = images[0]
                main_image_url = main_image.get("url")

            # Process tags using generic method
            tags = self._process_tags(product_data.get("tags", []))

            # Ensure required fields have proper values
            title = product_data.get("title", "").strip()
            handle = product_data.get("handle", "").strip()
            price = self._get_product_price(variants)

            # Skip products with missing required fields
            if not title or not handle or price is None:
                self.logger.warning(
                    f"Skipping product {product_id} - missing required fields: title='{title}', handle='{handle}', price={price}"
                )
                return None

            # Calculate inventory from variants
            calculated_inventory = self._get_total_inventory(variants)

            return {
                "shopId": shop_id,
                "productId": product_id,
                "title": title,
                "handle": handle,
                "description": product_data.get("description"),
                "descriptionHtml": product_data.get("bodyHtml"),
                "productType": product_data.get("productType"),
                "vendor": product_data.get("vendor"),
                "tags": tags,
                "status": product_data.get("status", "ACTIVE"),
                "totalInventory": product_data.get("totalInventory")
                or calculated_inventory,  # Use calculated as fallback
                "price": price,
                "compareAtPrice": self._get_product_compare_price(variants),
                "inventory": calculated_inventory,
                "imageUrl": main_image_url,
                "imageAlt": images[0].get("altText") if images else None,
                "productCreatedAt": self._parse_datetime(product_data.get("createdAt")),
                "productUpdatedAt": self._parse_datetime(product_data.get("updatedAt")),
                "onlineStoreUrl": product_data.get("onlineStoreUrl"),
                "onlineStorePreviewUrl": product_data.get("onlineStorePreviewUrl"),
                "seoTitle": (
                    product_data.get("seo", {}).get("title")
                    if product_data.get("seo")
                    else None
                ),
                "seoDescription": (
                    product_data.get("seo", {}).get("description")
                    if product_data.get("seo")
                    else None
                ),
                "templateSuffix": product_data.get("templateSuffix"),
                "variants": variants,
                "images": images,
                "media": self._normalize_gid_in_dict(
                    product_data.get("media", {}).get("edges", [])
                ),
                "options": options,
                "collections": collections,
                "metafields": metafields,
                "isActive": product_data.get("status", "active") == "active",
            }

        except Exception as e:
            self.logger.error(f"Failed to extract product fields: {str(e)}")
            return None

    def extract_customer_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key customer fields from nested JSON payload"""
        try:
            # Extract customer data using generic method
            customer_data = self._extract_payload_data(payload, "customer")

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

            # Extract GraphQL edge data using generic method
            addresses = self._extract_graphql_edges(customer_data.get("addresses", {}))
            metafields = self._extract_graphql_edges(
                customer_data.get("metafields", {})
            )

            # Process tags using generic method
            tags = self._process_tags(customer_data.get("tags", []))

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
                "createdAt": self._parse_datetime(customer_data.get("createdAt")),
                "lastOrderId": customer_data.get("lastOrderId"),
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
                "state": customer_data.get("state"),
                "verifiedEmail": customer_data.get("verifiedEmail", False),
                "taxExempt": customer_data.get("taxExempt", False),
                "defaultAddress": default_address,
                "addresses": addresses,
                "currencyCode": customer_data.get("currency") or "USD",
                "customerLocale": customer_data.get("locale"),
            }

        except Exception as e:
            self.logger.error(f"Failed to extract customer fields: {str(e)}")
            return None

    def extract_collection_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key collection fields from nested JSON payload"""
        try:
            if payload is None:
                return None

            # Extract collection data using generic method
            collection_data = self._extract_payload_data(payload, "collection")

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
            image = collection_data.get("image")
            image_url = image.get("url") if image and isinstance(image, dict) else None
            image_alt = (
                image.get("altText") if image and isinstance(image, dict) else None
            )

            # Extract SEO information
            seo = collection_data.get("seo", {})

            # Extract GraphQL edge data using generic method
            metafields = self._extract_graphql_edges(
                collection_data.get("metafields", {})
            )

            # Ensure required fields have proper values
            title = collection_data.get("title", "").strip()
            handle = collection_data.get("handle", "").strip()

            # Skip collections with missing required fields
            if not title or not handle:
                return None

            return {
                "shopId": shop_id,
                "collectionId": collection_id,
                "title": title,
                "handle": handle,
                "description": collection_data.get("description"),
                "templateSuffix": collection_data.get("templateSuffix"),
                "seoTitle": seo.get("title"),
                "seoDescription": seo.get("description"),
                "imageUrl": image_url,
                "imageAlt": image_alt,
                "productCount": int(collection_data.get("productsCount", 0)),
                "isAutomated": (
                    collection_data.get("ruleSet", {}).get("rules", []) != []
                    if collection_data.get("ruleSet")
                    and isinstance(collection_data.get("ruleSet"), dict)
                    else False
                ),
                "createdAt": collection_data.get("createdAt"),
                "updatedAt": collection_data.get("updatedAt"),
                "metafields": metafields,
            }

        except Exception as e:
            self.logger.error(f"Failed to extract collection fields: {str(e)}")
            return None

    # Helper methods for field extraction
    def _extract_payload_data(
        self, payload: Dict[str, Any], data_type: str
    ) -> Optional[Dict[str, Any]]:
        """Generic method to extract data from nested payload structure"""
        if payload is None or not isinstance(payload, dict):
            return None

        # Try nested structure first: payload.raw_data.{data_type}
        if "raw_data" in payload and isinstance(payload["raw_data"], dict):
            raw_data = payload["raw_data"]
            if raw_data is not None and data_type in raw_data:
                return raw_data[data_type]

        # Fallback to direct data or nested data structure
        return (
            payload.get(data_type) or payload.get("data", {}).get(data_type) or payload
        )

    def _extract_graphql_edges(
        self, data: Any, field_name: str = "edges"
    ) -> List[Dict[str, Any]]:
        """Generic method to extract GraphQL edges structure and normalize GID IDs"""
        if not isinstance(data, dict):
            return []

        if field_name in data and isinstance(data[field_name], list):
            edges = [edge.get("node", {}) for edge in data[field_name]]
            # Normalize GID IDs in the extracted edges
            return [self._normalize_gid_in_dict(edge) for edge in edges]

        return []

    def _extract_shopify_id(self, gid: str) -> Optional[str]:
        """Extract numeric ID from Shopify GraphQL GID with caching"""
        if not gid:
            return None

        # Check cache first
        if gid in self._gid_cache:
            return self._gid_cache[gid]

        try:
            # Handle GID format: gid://shopify/Order/123456789
            if gid.startswith("gid://shopify/"):
                result = gid.split("/")[-1]
            else:
                result = gid

            # Cache the result
            self._gid_cache[gid] = result
            return result
        except Exception:
            return None

    def _normalize_gid_in_dict(self, data: Any) -> Any:
        """Recursively normalize GID IDs in nested dictionaries and lists"""
        if isinstance(data, dict):
            normalized = {}
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("gid://shopify/"):
                    # Normalize any GID field (not just 'id')
                    normalized[key] = self._extract_shopify_id(value)
                elif isinstance(value, (dict, list)):
                    # Recursively normalize nested structures
                    normalized[key] = self._normalize_gid_in_dict(value)
                else:
                    normalized[key] = value
            return normalized
        elif isinstance(data, list):
            return [self._normalize_gid_in_dict(item) for item in data]
        else:
            return data

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

    def _process_tags(self, tags: Any) -> List[str]:
        """Generic method to process tags (string to array conversion)"""
        if isinstance(tags, str):
            # Split comma-separated tags and clean them
            return [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif isinstance(tags, list):
            return tags
        else:
            return []

    def _extract_money_amount(self, price_set: Dict[str, Any]) -> float:
        """Generic method to extract money amount from Shopify price set structure"""
        try:
            if isinstance(price_set, dict):
                return float(price_set.get("shopMoney", {}).get("amount", 0))
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    def _get_total_inventory(self, variants: List[Dict[str, Any]]) -> int:
        """Get total inventory across all variants"""
        if not variants:
            return 0
        return sum(int(v.get("inventoryQuantity", 0)) for v in variants)

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

    # ID extraction methods for specific data types
    def extract_order_id(self, order_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify order ID from order data"""
        try:
            return str(order_data.get("id", ""))
        except Exception:
            return None

    def extract_product_id(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify product ID from product data"""
        try:
            return str(product_data.get("id", ""))
        except Exception:
            return None

    def extract_customer_id(self, customer_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify customer ID from customer data"""
        try:
            return str(customer_data.get("id", ""))
        except Exception:
            return None

    def extract_collection_id(self, collection_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify collection ID from collection data"""
        try:
            return str(collection_data.get("id", ""))
        except Exception:
            return None
