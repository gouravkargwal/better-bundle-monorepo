"""
User/Customer Feature Generator for Gorse integration
Computes features from orders, customer data, and behavioral events
"""

import datetime
from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta
from prisma import Json

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class UserFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for user/customer features"""

    async def generate_features(
        self,
        shop_id: str,
        customer_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate user features for a customer

        Args:
            shop_id: The shop ID
            customer_id: The customer ID
            context: Additional context data (orders, customer_data, behavioral_events)

        Returns:
            Dictionary matching UserFeatures table schema
        """
        try:
            logger.debug(
                f"Computing user features for shop: {shop_id}, customer: {customer_id}"
            )

            # Get data from context
            orders = context.get("orders", [])
            customer_data = context.get("customer_data", {})
            behavioral_events = context.get("behavioral_events", [])
            products = context.get("products", [])  # For category/vendor analysis

            # Filter customer's orders
            customer_orders = [
                order for order in orders if order.get("customerId") == customer_id
            ]

            # Compute purchase metrics
            purchase_metrics = self._compute_purchase_metrics(customer_orders)

            # Compute time-based metrics
            temporal_metrics = self._compute_temporal_metrics(customer_orders)

            # Compute product preferences
            product_preferences = self._compute_product_preferences(
                customer_orders, products
            )

            # Compute discount behavior
            discount_metrics = self._compute_discount_metrics(customer_orders)

            # Compute enhanced customer features from new order data
            customer_enhancement_features = self._compute_customer_enhancement_features(
                customer_orders
            )

            # NEW: Compute customer demographic features using CustomerData table
            customer_demographic_features = self._compute_customer_demographic_features(
                customer_data
            )

            features = {
                "shopId": shop_id,
                "customerId": customer_id,
                # Purchase Metrics
                "totalPurchases": purchase_metrics["total_purchases"],
                "totalSpent": purchase_metrics["total_spent"],
                "avgOrderValue": purchase_metrics["avg_order_value"],
                "lifetimeValue": purchase_metrics["lifetime_value"],
                # Refund Metrics (NEW)
                "refundedOrders": purchase_metrics["refunded_orders"],
                "refundRate": purchase_metrics["refund_rate"],
                "totalRefundedAmount": purchase_metrics["total_refunded_amount"],
                "netLifetimeValue": purchase_metrics["net_lifetime_value"],
                # Time-based Metrics
                "daysSinceFirstOrder": temporal_metrics["days_since_first_order"],
                "daysSinceLastOrder": temporal_metrics["days_since_last_order"],
                "avgDaysBetweenOrders": temporal_metrics["avg_days_between_orders"],
                "orderFrequencyPerMonth": temporal_metrics["order_frequency_per_month"],
                # Product Preferences
                "distinctProductsPurchased": product_preferences["distinct_products"],
                "distinctCategoriesPurchased": product_preferences[
                    "distinct_categories"
                ],
                "preferredCategory": product_preferences["preferred_category"],
                "preferredVendor": product_preferences["preferred_vendor"],
                "pricePointPreference": product_preferences["price_point_preference"],
                # Discount Behavior
                "ordersWithDiscountCount": discount_metrics["orders_with_discount"],
                "discountSensitivity": discount_metrics["discount_sensitivity"],
                "avgDiscountAmount": discount_metrics["avg_discount_amount"],
                # Enhanced Customer Features (from Order API)
                "customerState": customer_enhancement_features["customer_state"],
                "isVerifiedEmail": customer_enhancement_features["is_verified_email"],
                "customerAge": customer_enhancement_features["customer_age"],
                "hasDefaultAddress": customer_enhancement_features[
                    "has_default_address"
                ],
                "geographicRegion": customer_enhancement_features["geographic_region"],
                "currencyPreference": customer_enhancement_features[
                    "currency_preference"
                ],
                "customerHealthScore": customer_enhancement_features[
                    "customer_health_score"
                ],
                # NEW: Customer demographic features from CustomerData table
                "customerEmail": customer_demographic_features["customer_email"],
                "customerFirstName": customer_demographic_features[
                    "customer_first_name"
                ],
                "customerLastName": customer_demographic_features["customer_last_name"],
                "customerLocation": Json(
                    customer_demographic_features["customer_location"]
                ),
                "customerTags": Json(customer_demographic_features["customer_tags"]),
                "customerCreatedAtShopify": customer_demographic_features[
                    "customer_created_at_shopify"
                ],
                "customerLastOrderId": customer_demographic_features[
                    "customer_last_order_id"
                ],
                "customerMetafields": Json(
                    customer_demographic_features["customer_metafields"]
                ),
                "customerState": customer_demographic_features["customer_state"],
                "customerVerifiedEmail": customer_demographic_features[
                    "customer_verified_email"
                ],
                "customerTaxExempt": customer_demographic_features[
                    "customer_tax_exempt"
                ],
                "customerDefaultAddress": Json(
                    customer_demographic_features["customer_default_address"]
                ),
                "customerAddresses": Json(
                    customer_demographic_features["customer_addresses"]
                ),
                "customerCurrencyCode": customer_demographic_features[
                    "customer_currency_code"
                ],
                "customerLocale": customer_demographic_features["customer_locale"],
                "lastComputedAt": now_utc(),
            }

            logger.debug(
                f"Computed user features for customer: {customer_id} - "
                f"LTV: ${features['lifetimeValue']:.2f}, Orders: {features['totalPurchases']}"
            )

            return features

        except Exception as e:
            logger.error(f"Failed to compute user features: {str(e)}")
            return self._get_default_features(shop_id, customer_id)

    def _compute_purchase_metrics(
        self, customer_orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute purchase-related metrics including refund analysis"""
        if not customer_orders:
            return {
                "total_purchases": 0,
                "total_spent": 0.0,
                "avg_order_value": 0.0,
                "lifetime_value": 0.0,
                "refunded_orders": 0,
                "refund_rate": 0.0,
                "total_refunded_amount": 0.0,
                "net_lifetime_value": 0.0,
            }

        total_purchases = len(customer_orders)

        # Calculate total spent and refund metrics
        total_spent = 0.0
        total_refunded_amount = 0.0
        refunded_orders = 0

        for order in customer_orders:
            order_amount = float(order.get("totalAmount", 0.0))
            total_spent += order_amount

            # Check financial status for refunds
            financial_status = order.get("financialStatus")
            if financial_status == "refunded":
                refunded_orders += 1
                # Use totalRefundedAmount if available, otherwise use totalAmount
                refunded_amount = float(order.get("totalRefundedAmount", order_amount))
                total_refunded_amount += refunded_amount

        # Calculate metrics
        avg_order_value = total_spent / total_purchases if total_purchases > 0 else 0.0
        refund_rate = refunded_orders / total_purchases if total_purchases > 0 else 0.0

        # Net lifetime value (total spent minus refunds)
        net_lifetime_value = total_spent - total_refunded_amount

        return {
            "total_purchases": total_purchases,
            "total_spent": round(total_spent, 2),
            "avg_order_value": round(avg_order_value, 2),
            "lifetime_value": round(total_spent, 2),  # Gross lifetime value
            "refunded_orders": refunded_orders,
            "refund_rate": round(refund_rate, 3),
            "total_refunded_amount": round(total_refunded_amount, 2),
            "net_lifetime_value": round(net_lifetime_value, 2),
        }

    def _compute_temporal_metrics(
        self, customer_orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute time-based metrics"""
        if not customer_orders:
            return {
                "days_since_first_order": None,
                "days_since_last_order": None,
                "avg_days_between_orders": None,
                "order_frequency_per_month": None,
            }

        # Sort orders by date
        sorted_orders = sorted(
            customer_orders, key=lambda x: self._parse_date(x.get("orderDate"))
        )

        first_order_date = self._parse_date(sorted_orders[0].get("orderDate"))
        last_order_date = self._parse_date(sorted_orders[-1].get("orderDate"))

        if not first_order_date or not last_order_date:
            return {
                "days_since_first_order": None,
                "days_since_last_order": None,
                "avg_days_between_orders": None,
                "order_frequency_per_month": None,
            }

        # Days since first and last order
        days_since_first = (now_utc() - first_order_date).days
        days_since_last = (now_utc() - last_order_date).days

        # Average days between orders
        avg_days_between = None
        order_frequency = None

        if len(sorted_orders) > 1:
            # Calculate gaps between consecutive orders
            gaps = []
            for i in range(1, len(sorted_orders)):
                prev_date = self._parse_date(sorted_orders[i - 1].get("orderDate"))
                curr_date = self._parse_date(sorted_orders[i].get("orderDate"))
                if prev_date and curr_date:
                    gap_days = (curr_date - prev_date).days
                    gaps.append(gap_days)

            if gaps:
                avg_days_between = round(statistics.mean(gaps), 1)

            # Order frequency per month
            total_span_days = (last_order_date - first_order_date).days
            if total_span_days > 0:
                order_frequency = round(
                    (len(sorted_orders) - 1) / (total_span_days / 30.0), 2
                )
        else:
            # Single order
            order_frequency = 0.0

        return {
            "days_since_first_order": days_since_first,
            "days_since_last_order": days_since_last,
            "avg_days_between_orders": avg_days_between,
            "order_frequency_per_month": order_frequency,
        }

    def _compute_product_preferences(
        self, customer_orders: List[Dict[str, Any]], products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute product preference metrics"""
        if not customer_orders:
            return {
                "distinct_products": 0,
                "distinct_categories": 0,
                "preferred_category": None,
                "preferred_vendor": None,
                "price_point_preference": None,
            }

        # Track products, categories, vendors, and prices
        purchased_products = set()
        category_counts = {}
        vendor_counts = {}
        all_prices = []

        for order in customer_orders:
            line_items = order.get("lineItems", [])

            for item in line_items:
                # Get product ID
                product_id = self._extract_product_id_from_line_item(item)
                if product_id:
                    purchased_products.add(product_id)

                # Get price
                price = float(item.get("price", 0.0))
                quantity = int(item.get("quantity", 1))
                all_prices.extend([price] * quantity)  # Weight by quantity

                # Find product details to get category and vendor
                product_info = self._find_product_info(product_id, products, item)

                if product_info:
                    # Count categories
                    category = product_info.get("productType") or product_info.get(
                        "category"
                    )
                    if category:
                        category_counts[category] = (
                            category_counts.get(category, 0) + quantity
                        )

                    # Count vendors
                    vendor = product_info.get("vendor")
                    if vendor:
                        vendor_counts[vendor] = vendor_counts.get(vendor, 0) + quantity

        # Determine preferences
        preferred_category = (
            max(category_counts, key=category_counts.get) if category_counts else None
        )
        preferred_vendor = (
            max(vendor_counts, key=vendor_counts.get) if vendor_counts else None
        )

        # Calculate price point preference
        price_point_preference = self._calculate_price_tier(all_prices)

        # Count distinct categories
        distinct_categories = len(set(category_counts.keys()))

        return {
            "distinct_products": len(purchased_products),
            "distinct_categories": distinct_categories,
            "preferred_category": preferred_category,
            "preferred_vendor": preferred_vendor,
            "price_point_preference": price_point_preference,
        }

    def _compute_discount_metrics(
        self, customer_orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute discount-related metrics"""
        if not customer_orders:
            return {
                "orders_with_discount": 0,
                "discount_sensitivity": 0.0,
                "avg_discount_amount": 0.0,
            }

        orders_with_discount = 0
        total_discount_amount = 0.0

        for order in customer_orders:
            # Check for discount applications
            discount_applications = order.get("discountApplications", [])

            # Also check for discount codes in the order
            if discount_applications:
                orders_with_discount += 1

                # Sum discount amounts
                for discount in discount_applications:
                    if isinstance(discount, dict):
                        value = discount.get("value", {})
                        if isinstance(value, dict):
                            amount = float(value.get("amount", 0.0))
                        else:
                            amount = float(value) if value else 0.0
                        total_discount_amount += amount

            # Alternative: check totalDiscounts field if available
            elif order.get("totalDiscounts"):
                total_discounts = float(order.get("totalDiscounts", 0.0))
                if total_discounts > 0:
                    orders_with_discount += 1
                    total_discount_amount += total_discounts

        # Calculate metrics
        total_orders = len(customer_orders)
        discount_sensitivity = (
            orders_with_discount / total_orders if total_orders > 0 else 0.0
        )
        avg_discount_amount = (
            total_discount_amount / orders_with_discount
            if orders_with_discount > 0
            else 0.0
        )

        return {
            "orders_with_discount": orders_with_discount,
            "discount_sensitivity": round(discount_sensitivity, 3),
            "avg_discount_amount": round(avg_discount_amount, 2),
        }

    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        # Direct product ID
        if "productId" in line_item:
            return str(line_item["productId"])

        # From variant
        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            if isinstance(product, dict):
                return product.get("id", "")

        # From product field
        if "product" in line_item and isinstance(line_item["product"], dict):
            return line_item["product"].get("id", "")

        return ""

    def _find_product_info(
        self, product_id: str, products: List[Dict[str, Any]], line_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find product information from products list or line item"""
        # First try to find in products list
        for product in products:
            if product.get("productId") == product_id:
                return product

        # Fallback to line item data
        # Line items might have embedded product data
        if "product" in line_item and isinstance(line_item["product"], dict):
            return line_item["product"]

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            return line_item["variant"].get("product", {})

        return {}

    def _calculate_price_tier(self, prices: List[float]) -> str:
        """Calculate price tier preference based on purchase history"""
        if not prices:
            return None

        avg_price = statistics.mean(prices)

        # Define price tiers (adjust these based on your store's price range)
        if avg_price < 25:
            return "budget"
        elif avg_price < 75:
            return "mid"
        elif avg_price < 200:
            return "premium"
        else:
            return "luxury"

    def _parse_date(self, date_value: Any) -> Optional[datetime.datetime]:
        """Parse date from various formats"""
        if not date_value:
            return None

        if isinstance(date_value, datetime.datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                return datetime.datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
            except:
                return None

        return None

    def _get_default_features(self, shop_id: str, customer_id: str) -> Dict[str, Any]:
        """Return default features when computation fails"""
        return {
            "shopId": shop_id,
            "customerId": customer_id,
            "totalPurchases": 0,
            "totalSpent": 0.0,
            "avgOrderValue": 0.0,
            "lifetimeValue": 0.0,
            # Refund Metrics (NEW)
            "refundedOrders": 0,
            "refundRate": 0.0,
            "totalRefundedAmount": 0.0,
            "netLifetimeValue": 0.0,
            "daysSinceFirstOrder": None,
            "daysSinceLastOrder": None,
            "avgDaysBetweenOrders": None,
            "orderFrequencyPerMonth": None,
            "distinctProductsPurchased": 0,
            "distinctCategoriesPurchased": 0,
            "preferredCategory": None,
            "preferredVendor": None,
            "pricePointPreference": None,
            "ordersWithDiscountCount": 0,
            "discountSensitivity": 0.0,
            "avgDiscountAmount": 0.0,
            "customerState": None,
            "isVerifiedEmail": False,
            "customerAge": None,
            "hasDefaultAddress": False,
            "geographicRegion": None,
            "currencyPreference": "USD",
            "customerHealthScore": 0,
            # NEW: Customer demographic features from CustomerData table
            "customerEmail": "",
            "customerFirstName": "",
            "customerLastName": "",
            "customerLocation": Json({}),
            "customerTags": Json([]),
            "customerCreatedAtShopify": None,
            "customerLastOrderId": "",
            "customerMetafields": Json([]),
            "customerState": "",
            "customerVerifiedEmail": False,
            "customerTaxExempt": False,
            "customerDefaultAddress": Json({}),
            "customerAddresses": Json([]),
            "customerCurrencyCode": "USD",
            "customerLocale": "en",
            "lastComputedAt": now_utc(),
        }

    def _compute_customer_enhancement_features(
        self, customer_orders: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute enhanced customer features from new order data"""
        try:
            if not customer_orders:
                return {
                    "customer_state": None,
                    "is_verified_email": False,
                    "customer_age": None,
                    "has_default_address": False,
                    "geographic_region": None,
                    "currency_preference": None,
                    "customer_health_score": 0,
                }

            # Get the most recent order for customer data
            latest_order = max(customer_orders, key=lambda x: x.get("orderDate", ""))

            # Extract customer data from order
            customer_state = latest_order.get("customerState")
            is_verified_email = latest_order.get("customerVerifiedEmail", False)
            customer_created_at = latest_order.get("customerCreatedAt")
            customer_default_address = latest_order.get("customerDefaultAddress", {})
            currency_preference = latest_order.get("currencyCode", "USD")

            # Calculate customer age (days since creation)
            customer_age = None
            if customer_created_at:
                from datetime import datetime

                try:
                    if isinstance(customer_created_at, str):
                        customer_created_at = datetime.fromisoformat(
                            customer_created_at.replace("Z", "+00:00")
                        )
                    customer_age = (datetime.now() - customer_created_at).days
                except:
                    customer_age = None

            # Extract geographic region from default address
            geographic_region = None
            has_default_address = bool(customer_default_address)
            if customer_default_address:
                country = customer_default_address.get("country")
                province = customer_default_address.get("province")
                if country:
                    geographic_region = (
                        f"{province}, {country}" if province else country
                    )

            # Calculate customer health score (0-100) including refund metrics
            customer_health_score = 0
            if customer_state == "ENABLED":
                customer_health_score += 40
            elif customer_state == "DISABLED":
                customer_health_score += 10

            if is_verified_email:
                customer_health_score += 30

            if has_default_address:
                customer_health_score += 20

            if customer_age and customer_age > 30:  # Customer for more than 30 days
                customer_health_score += 10

            # Apply refund penalty to health score
            total_orders = len(customer_orders)
            if total_orders > 0:
                refunded_orders = sum(
                    1
                    for order in customer_orders
                    if order.get("financialStatus") == "refunded"
                )
                refund_rate = refunded_orders / total_orders

                # Penalize high refund rates (reduce health score)
                if refund_rate > 0.5:  # More than 50% refund rate
                    customer_health_score -= 30
                elif refund_rate > 0.25:  # More than 25% refund rate
                    customer_health_score -= 15
                elif refund_rate > 0.1:  # More than 10% refund rate
                    customer_health_score -= 5

            return {
                "customer_state": customer_state,
                "is_verified_email": is_verified_email,
                "customer_age": customer_age,
                "has_default_address": has_default_address,
                "geographic_region": geographic_region,
                "currency_preference": currency_preference,
                "customer_health_score": min(100, customer_health_score),
            }
        except Exception as e:
            logger.error(f"Error computing customer enhancement features: {str(e)}")
            return {
                "customer_state": None,
                "is_verified_email": False,
                "customer_age": None,
                "has_default_address": False,
                "geographic_region": None,
                "currency_preference": None,
                "customer_health_score": 0,
            }

    def _compute_customer_demographic_features(
        self, customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute customer demographic features using CustomerData table"""
        try:
            # Extract all customer data fields (previously unused)
            return {
                "customer_email": customer_data.get("email", ""),
                "customer_first_name": customer_data.get("firstName", ""),
                "customer_last_name": customer_data.get("lastName", ""),
                "customer_location": customer_data.get("location", {}),
                "customer_tags": customer_data.get("tags", []),
                "customer_created_at_shopify": customer_data.get("createdAtShopify"),
                "customer_last_order_id": customer_data.get("lastOrderId", ""),
                "customer_metafields": customer_data.get("metafields", []),
                "customer_state": customer_data.get("state", ""),
                "customer_verified_email": customer_data.get("verifiedEmail", False),
                "customer_tax_exempt": customer_data.get("taxExempt", False),
                "customer_default_address": customer_data.get("defaultAddress", {}),
                "customer_addresses": customer_data.get("addresses", []),
                "customer_currency_code": customer_data.get("currencyCode", "USD"),
                "customer_locale": customer_data.get("customerLocale", "en"),
                "customer_is_active": customer_data.get("isActive", True),
            }
        except Exception as e:
            logger.error(f"Error computing customer demographic features: {str(e)}")
            return {
                "customer_email": "",
                "customer_first_name": "",
                "customer_last_name": "",
                "customer_location": Json({}),
                "customer_tags": Json([]),
                "customer_created_at_shopify": None,
                "customer_last_order_id": "",
                "customer_metafields": Json([]),
                "customer_state": "",
                "customer_verified_email": False,
                "customer_tax_exempt": False,
                "customer_default_address": Json({}),
                "customer_addresses": Json([]),
                "customer_currency_code": "USD",
                "customer_locale": "en",
            }
