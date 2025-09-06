"""
Order feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class OrderFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify orders"""

    async def generate_features(
        self, order: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for an order

        Args:
            order: The order to generate features for
            context: Additional context data (shop, products, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for order: {order.get('id', 'unknown')}")

            features = {}
            shop = context.get("shop")
            products = context.get("products", [])

            # Basic order features
            features.update(self._compute_basic_order_features(order))

            # Line item features
            features.update(self._compute_line_item_features(order))

            # Customer features
            features.update(self._compute_order_customer_features(order))

            # Product features
            if products:
                features.update(self._compute_order_product_features(order, products))

            # Time features
            features.update(self._compute_order_time_features(order))

            # Financial features
            features.update(self._compute_financial_features(order))

            # Enhanced customer lifetime value features
            features.update(self._compute_customer_lifetime_features(order, context))

            # Basket analysis features
            features.update(self._compute_basket_analysis_features(order, context))

            # Cross-selling and upselling features
            features.update(self._compute_cross_selling_features(order, context))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} features for order: {order.get('id', 'unknown')}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute order features for {order.get('id', 'unknown')}: {str(e)}"
            )
            return {}

    def _compute_basic_order_features(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Compute basic order features"""
        return {
            "order_id": order.get("id", ""),
            "order_number": order.get("orderNumber", ""),
            "total_price": order.get("totalAmount", 0.0),
            "subtotal_price": order.get("subtotalAmount", 0.0),
            "total_tax": order.get("totalTaxAmount", 0.0),
            "currency_encoded": self._encode_categorical_feature(
                order.get("currencyCode", "")
            ),
            "financial_status_encoded": self._encode_categorical_feature(
                order.get("orderStatus", "")
            ),
            "fulfillment_status_encoded": self._encode_categorical_feature(
                order.get("orderStatus", "")
            ),
            "line_items_count": len(order.get("lineItems", [])),
            "has_discount": 1 if order.get("totalRefundedAmount", 0) > 0 else 0,
            "total_discounts": order.get("totalRefundedAmount", 0.0),
        }

    def _compute_line_item_features(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Compute line item features"""
        line_items = order.get("lineItems", [])
        if not line_items:
            return {
                "line_items_count": 0,
                "total_quantity": 0,
                "avg_item_price": 0,
                "price_std": 0,
                "unique_products": 0,
            }

        quantities = [item.get("quantity", 0) for item in line_items]
        prices = [item.get("price", 0.0) for item in line_items]
        product_ids = [
            item.get("productId") for item in line_items if item.get("productId")
        ]

        return {
            "line_items_count": len(line_items),
            "total_quantity": sum(quantities),
            "avg_item_price": statistics.mean(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "unique_products": len(set(product_ids)),
        }

    def _compute_order_customer_features(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Compute customer-related order features"""
        return {
            "customer_id": self._encode_categorical_feature(
                order.get("customerId", "")
            ),
            "has_customer": 1 if order.get("customerId") else 0,
        }

    def _compute_order_product_features(
        self, order: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute product-related order features"""
        line_items = order.get("lineItems", [])
        product_ids = [
            item.get("productId") for item in line_items if item.get("productId")
        ]
        order_products = [p for p in products if p.get("id") in product_ids]

        if not order_products:
            return {
                "avg_product_price": 0,
                "product_categories": 0,
                "product_vendors": 0,
            }

        prices = [
            p.get("variants", [{}])[0].get("price", 0.0)
            for p in order_products
            if p.get("variants")
        ]
        categories = [
            p.get("productType", "") for p in order_products if p.get("productType")
        ]
        vendors = [p.get("vendor", "") for p in order_products if p.get("vendor")]

        return {
            "avg_product_price": statistics.mean(prices) if prices else 0,
            "product_categories": len(set(categories)),
            "product_vendors": len(set(vendors)),
        }

    def _compute_order_time_features(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Compute time-based order features"""
        return self._compute_time_based_features(
            order.get("orderDate"), order.get("updatedAt")
        )

    def _compute_financial_features(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Compute financial features"""
        return {
            "total_price": order.get("totalAmount", 0.0),
            "subtotal_price": order.get("subtotalAmount", 0.0),
            "total_tax": order.get("totalTaxAmount", 0.0),
            "total_discounts": order.get("totalRefundedAmount", 0.0),
            "discount_rate": (
                order.get("totalRefundedAmount", 0.0) / order.get("subtotalAmount", 1.0)
                if order.get("subtotalAmount", 0) > 0
                else 0
            ),
            "tax_rate": (
                order.get("totalTaxAmount", 0.0) / order.get("subtotalAmount", 1.0)
                if order.get("subtotalAmount", 0) > 0
                else 0
            ),
        }

    def _compute_customer_lifetime_features(
        self, order: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute customer lifetime value features"""
        orders = context.get("orders", [])

        if not order.get("customerId"):
            return {
                "customer_lifetime_value": 0.0,
                "customer_order_count": 0,
                "customer_avg_order_value": 0.0,
                "customer_order_frequency": 0.0,
                "customer_retention_score": 0.0,
                "customer_growth_trend": 0.0,
                "is_new_customer": 1,
                "customer_segment": "new",
            }

        # Get all orders for this customer
        customer_orders = [
            o for o in orders if o.get("customerId") == order.get("customerId")
        ]
        customer_orders.sort(key=lambda x: x.get("orderDate", ""))

        if not customer_orders:
            return {}

        # Calculate customer lifetime value
        total_spent = sum(o.total_price for o in customer_orders)

        # Customer order count
        order_count = len(customer_orders)

        # Average order value
        avg_order_value = total_spent / order_count

        # Order frequency (orders per month)
        if order_count > 1:
            time_span = (
                customer_orders[-1].created_at - customer_orders[0].created_at
            ).days
            order_frequency = order_count / max(time_span / 30, 1)  # per month
        else:
            order_frequency = 0.0

        # Customer retention score (based on order consistency)
        if order_count > 1:
            order_intervals = []
            for i in range(1, len(customer_orders)):
                interval = (
                    customer_orders[i].created_at - customer_orders[i - 1].created_at
                ).days
                order_intervals.append(interval)

            if order_intervals:
                avg_interval = statistics.mean(order_intervals)
                interval_consistency = 1 - (
                    statistics.stdev(order_intervals) / max(avg_interval, 1)
                )
                retention_score = min(interval_consistency, 1.0)
            else:
                retention_score = 0.0
        else:
            retention_score = 0.0

        # Customer growth trend (increasing order values over time)
        if order_count >= 3:
            recent_orders = customer_orders[-3:]  # Last 3 orders
            older_orders = customer_orders[:3]  # First 3 orders

            recent_avg = statistics.mean(o.total_price for o in recent_orders)
            older_avg = statistics.mean(o.total_price for o in older_orders)

            if older_avg > 0:
                growth_trend = (recent_avg - older_avg) / older_avg
            else:
                growth_trend = 0.0
        else:
            growth_trend = 0.0

        # Customer segment classification
        if order_count == 1:
            customer_segment = "new"
        elif order_count <= 3:
            customer_segment = "regular"
        elif order_count <= 10:
            customer_segment = "loyal"
        else:
            customer_segment = "vip"

        return {
            "customer_lifetime_value": total_spent,
            "customer_order_count": order_count,
            "customer_avg_order_value": avg_order_value,
            "customer_order_frequency": order_frequency,
            "customer_retention_score": retention_score,
            "customer_growth_trend": growth_trend,
            "is_new_customer": 1 if order_count == 1 else 0,
            "customer_segment": customer_segment,
        }

    def _compute_basket_analysis_features(
        self, order: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basket analysis features"""
        products = context.get("products", [])

        line_items = order.get("lineItems", [])
        if not line_items or not products:
            return {
                "basket_diversity": 0.0,
                "category_diversity": 0.0,
                "price_range": 0.0,
                "bundle_score": 0.0,
                "complementarity_score": 0.0,
                "impulse_buy_ratio": 0.0,
                "planned_purchase_ratio": 0.0,
            }

        # Get product details for line items
        line_item_products = []
        for line_item in line_items:
            if line_item.get("productId"):
                product = next(
                    (p for p in products if p.get("id") == line_item.get("productId")),
                    None,
                )
                if product:
                    line_item_products.append((line_item, product))

        if not line_item_products:
            return {}

        # Basket diversity (number of unique products)
        basket_diversity = len(line_item_products) / 10.0  # Normalize

        # Category diversity
        categories = set()
        for _, product in line_item_products:
            product_type = product.get("productType")
            if product_type:
                categories.add(product_type)
        category_diversity = len(categories) / max(len(line_item_products), 1)

        # Price range in basket
        prices = [li.get("price", 0.0) for li, _ in line_item_products]
        if len(prices) > 1:
            price_range = (max(prices) - min(prices)) / max(prices)
        else:
            price_range = 0.0

        # Bundle score (products that are commonly bought together)
        bundle_score = self._calculate_bundle_score(line_item_products)

        # Complementarity score (how well products go together)
        complementarity_score = self._calculate_complementarity_score(
            line_item_products
        )

        # Impulse vs planned purchase ratio (simplified)
        impulse_ratio = self._calculate_impulse_ratio(line_item_products)
        planned_ratio = 1 - impulse_ratio

        return {
            "basket_diversity": basket_diversity,
            "category_diversity": category_diversity,
            "price_range": price_range,
            "bundle_score": bundle_score,
            "complementarity_score": complementarity_score,
            "impulse_buy_ratio": impulse_ratio,
            "planned_purchase_ratio": planned_ratio,
        }

    def _compute_cross_selling_features(
        self, order: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute cross-selling and upselling features"""
        orders = context.get("orders", [])
        products = context.get("products", [])

        line_items = order.get("lineItems", [])
        if not line_items or not products:
            return {
                "upselling_opportunity": 0.0,
                "cross_selling_opportunity": 0.0,
                "average_item_value": 0.0,
                "premium_item_ratio": 0.0,
                "accessory_ratio": 0.0,
                "replacement_ratio": 0.0,
            }

        # Calculate average item value
        total_value = sum(
            li.get("price", 0.0) * li.get("quantity", 0) for li in line_items
        )
        total_quantity = sum(li.get("quantity", 0) for li in line_items)
        avg_item_value = total_value / max(total_quantity, 1)

        # Premium item ratio (items above average price)
        premium_items = sum(
            1 for li in line_items if li.get("price", 0.0) > avg_item_value
        )
        premium_ratio = premium_items / len(line_items)

        # Accessory ratio (based on product types)
        accessory_types = ["accessories", "add-ons", "extras", "cases", "covers"]
        accessory_items = 0
        for li in line_items:
            product = next(
                (p for p in products if p.get("id") == li.get("productId")), None
            )
            if product and any(
                acc_type in (product.get("productType") or "").lower()
                for acc_type in accessory_types
            ):
                accessory_items += 1
        accessory_ratio = accessory_items / len(line_items)

        # Upselling opportunity (could customer have bought more expensive versions)
        upselling_opportunity = self._calculate_upselling_opportunity(order, products)

        # Cross-selling opportunity (what else could they have bought)
        cross_selling_opportunity = self._calculate_cross_selling_opportunity(
            order, orders, products
        )

        # Replacement ratio (items that might be replacements)
        replacement_ratio = self._calculate_replacement_ratio(order, products)

        return {
            "upselling_opportunity": upselling_opportunity,
            "cross_selling_opportunity": cross_selling_opportunity,
            "average_item_value": avg_item_value,
            "premium_item_ratio": premium_ratio,
            "accessory_ratio": accessory_ratio,
            "replacement_ratio": replacement_ratio,
        }

    def _calculate_bundle_score(self, line_item_products: List) -> float:
        """Calculate how likely these products are to be a bundle"""
        if len(line_item_products) < 2:
            return 0.0

        # Simple bundle detection based on complementary categories
        categories = [
            li[1].get("productType")
            for li in line_item_products
            if li[1].get("productType")
        ]

        # Define complementary category pairs
        complementary_pairs = [
            ("clothing", "accessories"),
            ("electronics", "accessories"),
            ("home", "decor"),
            ("beauty", "skincare"),
        ]

        bundle_indicators = 0
        for cat1, cat2 in complementary_pairs:
            if cat1 in categories and cat2 in categories:
                bundle_indicators += 1

        return bundle_indicators / len(complementary_pairs)

    def _calculate_complementarity_score(self, line_item_products: List) -> float:
        """Calculate how well products complement each other"""
        if len(line_item_products) < 2:
            return 0.0

        # Simple complementarity based on category diversity and price consistency
        categories = [
            li[1].get("productType")
            for li in line_item_products
            if li[1].get("productType")
        ]
        prices = [li.get("price", 0.0) for li, _ in line_item_products]

        # Category diversity (some diversity is good, too much might indicate random selection)
        category_diversity = len(set(categories)) / len(categories)

        # Price consistency (similar price points indicate planned purchase)
        if len(prices) > 1:
            price_consistency = 1 - (
                statistics.stdev(prices) / max(statistics.mean(prices), 1)
            )
        else:
            price_consistency = 1.0

        # Complementarity score combines both factors
        complementarity = category_diversity * 0.3 + price_consistency * 0.7
        return min(complementarity, 1.0)

    def _calculate_impulse_ratio(self, line_item_products: List) -> float:
        """Calculate ratio of impulse purchases (simplified)"""
        if not line_item_products:
            return 0.0

        # Simple heuristic: single items or very different categories might be impulse
        if len(line_item_products) == 1:
            return 0.8  # Single item likely impulse

        # Multiple items with very different categories might be impulse
        categories = [
            li[1].get("productType")
            for li in line_item_products
            if li[1].get("productType")
        ]
        if len(set(categories)) == len(categories):  # All different categories
            return 0.6

        return 0.2  # Planned purchase

    def _calculate_upselling_opportunity(
        self, order: Dict[str, Any], products: List
    ) -> float:
        """Calculate upselling opportunity score"""
        line_items = order.get("lineItems", [])
        if not line_items or not products:
            return 0.0

        # Find products in order that have higher-priced variants
        upselling_opportunities = 0

        for line_item in line_items:
            product = next(
                (p for p in products if p.get("id") == line_item.get("productId")), None
            )
            if product and product.get("variants"):
                # Check if there are higher-priced variants
                current_price = line_item.get("price", 0.0)
                higher_priced_variants = [
                    v
                    for v in product.get("variants", [])
                    if v.get("price", 0.0) > current_price
                ]

                if higher_priced_variants:
                    upselling_opportunities += 1

        return upselling_opportunities / len(line_items)

    def _calculate_cross_selling_opportunity(
        self, order: Dict[str, Any], all_orders: List, products: List
    ) -> float:
        """Calculate cross-selling opportunity score"""
        line_items = order.get("lineItems", [])
        if not line_items or not all_orders or not products:
            return 0.0

        # Find products frequently bought with items in this order
        order_product_ids = [li.get("productId") for li in line_items]

        # Analyze other orders to find co-purchase patterns
        co_purchase_count = 0
        total_other_orders = 0

        for other_order in all_orders:
            if other_order.get("id") == order.get("id"):
                continue

            other_product_ids = [
                li.get("productId") for li in other_order.get("lineItems", [])
            ]

            # Check if any products from this order appear in other orders
            if any(pid in other_product_ids for pid in order_product_ids):
                total_other_orders += 1

                # Count additional products that could be cross-sold
                additional_products = set(other_product_ids) - set(order_product_ids)
                co_purchase_count += len(additional_products)

        if total_other_orders == 0:
            return 0.0

        # Cross-selling opportunity = average additional products per co-purchase
        return co_purchase_count / total_other_orders

    def _calculate_replacement_ratio(
        self, order: Dict[str, Any], products: List
    ) -> float:
        """Calculate ratio of items that might be replacements"""
        line_items = order.get("lineItems", [])
        if not line_items or not products:
            return 0.0

        # Simple heuristic: items with similar categories might be replacements
        replacement_indicators = 0

        for line_item in line_items:
            product = next(
                (p for p in products if p.get("id") == line_item.get("productId")), None
            )
            if product:
                # Check if this is a replacement-type product
                replacement_keywords = [
                    "replacement",
                    "refill",
                    "new",
                    "upgrade",
                    "version",
                ]
                product_text = f"{product.get('title', '')} {product.get('productType', '')}".lower()

                if any(keyword in product_text for keyword in replacement_keywords):
                    replacement_indicators += 1

        return replacement_indicators / len(line_items)
